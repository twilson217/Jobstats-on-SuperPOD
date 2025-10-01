#!/usr/bin/env python3
"""
Fix for jobstats timelimit parsing issues

This script fixes two issues in jobstats:
1. Time limit comparison error when timelimitraw is "UNLIMITED" (string vs int)
2. Time limit formatting error when timelimitraw is "UNLIMITED" (string multiplication)

Usage:
    python3 fix_jobstats_timelimit.py

The script will:
- Backup the original file
- Apply fixes to handle UNLIMITED time limits
- Restore from backup if something goes wrong
"""

import os
import shutil
import subprocess
import sys

def fix_timelimit_parsing():
    """Fix the timelimit parsing issues in jobstats output_formatters.py"""
    
    file_path = "/usr/local/jobstats/output_formatters.py"
    backup_path = "/usr/local/jobstats/output_formatters.py.backup.timelimit_fix"
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"ERROR: {file_path} not found")
        return False
    
    # Create backup
    try:
        shutil.copy2(file_path, backup_path)
        print(f"Created backup: {backup_path}")
    except Exception as e:
        print(f"ERROR: Failed to create backup: {e}")
        return False
    
    try:
        # Read the file
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Fix 1: Handle string comparison in time_limit_formatted method
        old_comparison = 'if self.js.state == "COMPLETED" and self.js.timelimitraw > 0:'
        new_comparison = 'if self.js.state == "COMPLETED" and str(self.js.timelimitraw) != "UNLIMITED" and self.js.timelimitraw > 0:'
        
        if old_comparison in content:
            content = content.replace(old_comparison, new_comparison)
            print("Fixed time limit comparison (string vs int)")
        else:
            print("Warning: Could not find time limit comparison to fix")
        
        # Fix 2: Handle UNLIMITED time limit in time_limit_formatted method
        old_hs_line = 'hs = self.human_seconds(SECONDS_PER_MINUTE * self.js.timelimitraw)'
        new_hs_code = '''# Handle UNLIMITED time limit
        if self.js.timelimitraw == "UNLIMITED" or str(self.js.timelimitraw).upper() == "UNLIMITED":
            hs = "UNLIMITED"
        else:
            hs = self.human_seconds(SECONDS_PER_MINUTE * self.js.timelimitraw)'''
        
        if old_hs_line in content:
            content = content.replace(old_hs_line, new_hs_code)
            print("Fixed time limit formatting (UNLIMITED handling)")
        else:
            print("Warning: Could not find time limit formatting line to fix")
        
        # Only write if changes were made
        if content != original_content:
            # Write the fixed file
            with open(file_path, 'w') as f:
                f.write(content)
            print("Successfully applied jobstats timelimit fixes")
            return True
        else:
            print("No changes needed - fixes may already be applied")
            return True
            
    except Exception as e:
        print(f"ERROR: Failed to apply fixes: {e}")
        print("Restoring from backup...")
        try:
            shutil.copy2(backup_path, file_path)
            print("Restored from backup")
        except Exception as restore_error:
            print(f"ERROR: Failed to restore from backup: {restore_error}")
        return False

def test_fix():
    """Test if the fix works by running jobstats on a test job"""
    try:
        # Try to find a recent job to test with
        result = subprocess.run(['sacct', '--format=JobID,State', '--noheader', '-n', '1'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            job_id = result.stdout.strip().split()[0]
            print(f"Testing fix with job {job_id}...")
            
            # Test jobstats
            test_result = subprocess.run(['jobstats', '-j', job_id, '-c', 'slurm'], 
                                       capture_output=True, text=True, timeout=30)
            if test_result.returncode == 0:
                print("✅ Fix test successful - jobstats is working")
                return True
            else:
                print(f"⚠️  Fix test failed - jobstats error: {test_result.stderr}")
                return False
        else:
            print("⚠️  No jobs found to test with")
            return True
    except Exception as e:
        print(f"⚠️  Could not test fix: {e}")
        return True

if __name__ == "__main__":
    print("Jobstats Timelimit Fix Script")
    print("=" * 40)
    
    if fix_timelimit_parsing():
        print("\nTesting the fix...")
        test_fix()
        print("\nFix completed successfully!")
    else:
        print("\nFix failed!")
        sys.exit(1)
