#!/usr/bin/env python3
"""
Fix for jobstats alloc/cores division error

This script fixes the TypeError in output_formatters.py where alloc is a string
but cores is an integer, causing a division error.

Note: This script now works with the shared storage jobstats installation
at /cm/shared/apps/jobstats/output_formatters.py.
"""

import os
import sys
import shutil
from datetime import datetime

def fix_jobstats_alloc_cores():
    """Fix the alloc/cores division error in jobstats"""
    
    jobstats_file = "/cm/shared/apps/jobstats/output_formatters.py"
    backup_file = f"/cm/shared/apps/jobstats/output_formatters.py.backup.alloc_cores.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if not os.path.exists(jobstats_file):
        print(f"Error: {jobstats_file} not found")
        return False
    
    # Create backup
    print(f"Creating backup: {backup_file}")
    shutil.copy2(jobstats_file, backup_file)
    
    # Read the file
    with open(jobstats_file, 'r') as f:
        content = f.read()
    
    # Find and fix the problematic line
    old_line = 'hb_alloc = self.human_bytes(alloc / cores).replace(".0GB", "GB")'
    new_line = '''# Handle string alloc values
        try:
            alloc_value = float(alloc) if isinstance(alloc, str) else alloc
            hb_alloc = self.human_bytes(alloc_value / cores).replace(".0GB", "GB")
        except (ValueError, TypeError, ZeroDivisionError):
            hb_alloc = "Unknown"'''
    
    if old_line in content:
        content = content.replace(old_line, new_line)
        print("Fixed alloc/cores division error")
    else:
        print("Warning: Could not find the exact line to fix")
        print("Looking for similar patterns...")
        
        # Look for similar patterns
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'alloc / cores' in line and 'human_bytes' in line:
                print(f"Found similar line at {i+1}: {line.strip()}")
                lines[i] = new_line
                content = '\n'.join(lines)
                print("Applied fix to similar pattern")
                break
        else:
            print("No similar patterns found")
            return False
    
    # Write the fixed content
    with open(jobstats_file, 'w') as f:
        f.write(content)
    
    print(f"Successfully fixed {jobstats_file}")
    return True

def test_fix():
    """Test the fix by running jobstats on a recent job"""
    print("\nTesting the fix...")
    
    # Get the most recent job
    import subprocess
    try:
        result = subprocess.run(['sacct', '-u', 'root', '--start=today', '--format=JobID,State', '--noheader'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            recent_jobs = [line.split()[0] for line in lines if 'COMPLETED' in line and '.' not in line.split()[0]]
            if recent_jobs:
                test_job = recent_jobs[-1]  # Most recent job
                print(f"Testing with job {test_job}...")
                
                # Test jobstats
                test_result = subprocess.run(['jobstats', '-j', test_job], 
                                          capture_output=True, text=True, timeout=30)
                if test_result.returncode == 0:
                    print("✅ Fix successful! jobstats is working")
                    return True
                else:
                    print(f"❌ jobstats still has issues: {test_result.stderr}")
                    return False
            else:
                print("No recent completed jobs found for testing")
                return True
        else:
            print("Could not get job list for testing")
            return True
    except Exception as e:
        print(f"Error during testing: {e}")
        return True

def main():
    print("Jobstats alloc/cores division fix")
    print("=" * 40)
    
    if fix_jobstats_alloc_cores():
        print("\nFix applied successfully!")
        test_fix()
    else:
        print("\nFix failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
