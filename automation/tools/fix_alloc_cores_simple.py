#!/usr/bin/env python3
"""
Simple fix for jobstats alloc/cores division error
"""

import os
import shutil
from datetime import datetime

def fix_alloc_cores():
    jobstats_file = "/usr/local/jobstats/output_formatters.py"
    backup_file = f"/usr/local/jobstats/output_formatters.py.backup.alloc.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create backup
    shutil.copy2(jobstats_file, backup_file)
    print(f"Backup created: {backup_file}")
    
    # Read file
    with open(jobstats_file, 'r') as f:
        lines = f.readlines()
    
    # Find and replace the problematic line
    for i, line in enumerate(lines):
        if 'hb_alloc = self.human_bytes(alloc / cores).replace(".0GB", "GB")' in line:
            # Replace with safe version
            lines[i] = '            hb_alloc = self.human_bytes(float(alloc) / cores).replace(".0GB", "GB") if isinstance(alloc, str) else self.human_bytes(alloc / cores).replace(".0GB", "GB")\n'
            print(f"Fixed line {i+1}")
            break
    else:
        print("Could not find the problematic line")
        return False
    
    # Write back
    with open(jobstats_file, 'w') as f:
        f.writelines(lines)
    
    print("Fix applied successfully")
    return True

if __name__ == "__main__":
    fix_alloc_cores()
