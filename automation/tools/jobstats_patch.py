#!/usr/bin/env python3
"""
Jobstats Patch Script

This script applies necessary patches to the jobstats code to make it work
in a BCM environment. The patches address several issues discovered during
deployment testing.

Issues Fixed:
1. Prometheus queries require cluster label but our setup doesn't use it
2. sacct command not found in PATH for non-root users
3. SLURM_CONF environment variable not set
4. GPU query syntax errors in PromQL
5. Query format string parameter count mismatch

Usage:
    python3 jobstats_patch.py /path/to/jobstats.py

The script will create a backup and apply all necessary patches.
"""

import os
import sys
import shutil
import re
from datetime import datetime

def create_backup(filepath):
    """Create a timestamped backup of the original file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.backup.{timestamp}"
    shutil.copy2(filepath, backup_path)
    print(f"Created backup: {backup_path}")
    return backup_path

def patch_jobstats(filepath):
    """Apply all necessary patches to jobstats.py"""
    
    if not os.path.exists(filepath):
        print(f"Error: File {filepath} does not exist")
        return False
    
    # Create backup
    backup_path = create_backup(filepath)
    
    # Read the file
    with open(filepath, 'r') as f:
        content = f.read()
    
    print("Applying patches to jobstats.py...")
    
    # Patch 1: Set SLURM_CONF environment variable
    print("  - Setting SLURM_CONF environment variable")
    content = re.sub(
        r"os\.environ\['SLURM_TIME_FORMAT'\] = \"%s\"",
        'os.environ["SLURM_TIME_FORMAT"] = "%s"\nos.environ["SLURM_CONF"] = "/cm/shared/apps/slurm/var/etc/slurm/slurm.conf"',
        content
    )
    
    # Patch 2: Use full path to sacct command
    print("  - Using full path to sacct command")
    content = re.sub(
        r'cmd = \["sacct"',
        'cmd = ["/cm/shared/apps/slurm/current/bin/sacct"',
        content
    )
    
    # Patch 3: Remove cluster label from CPU/memory queries
    print("  - Removing cluster label from CPU/memory queries")
    content = re.sub(
        r"cgroup_memory_total_bytes\{cluster='%s',jobid='%s',step='',task=''\}",
        "cgroup_memory_total_bytes{jobid='%s',step='',task=''}",
        content
    )
    content = re.sub(
        r"cgroup_memory_rss_bytes\{cluster='%s',jobid='%s',step='',task=''\}",
        "cgroup_memory_rss_bytes{jobid='%s',step='',task=''}",
        content
    )
    content = re.sub(
        r"cgroup_cpu_total_seconds\{cluster='%s',jobid='%s',step='',task=''\}",
        "cgroup_cpu_total_seconds{jobid='%s',step='',task=''}",
        content
    )
    content = re.sub(
        r"cgroup_cpus\{cluster='%s',jobid='%s',step='',task=''\}",
        "cgroup_cpus{jobid='%s',step='',task=''}",
        content
    )
    
    # Patch 4: Fix query format strings to match parameter count
    print("  - Fixing query format strings")
    content = re.sub(
        r"expanded_query = query % \(self\.cluster, self\.jobidraw, self\.diff\)",
        "expanded_query = query % (self.jobidraw, self.diff)",
        content
    )
    
    # Patch 5: Fix GPU query syntax (use = instead of == and proper quotes)
    print("  - Fixing GPU query syntax")
    content = re.sub(
        r"nvidia_gpu_memory_total_bytes\{nvidia_gpu_jobId == %s\}",
        'nvidia_gpu_memory_total_bytes{nvidia_gpu_jobId=\\"%s\\"}',
        content
    )
    content = re.sub(
        r"nvidia_gpu_memory_used_bytes\{nvidia_gpu_jobId == %s\}",
        'nvidia_gpu_memory_used_bytes{nvidia_gpu_jobId=\\"%s\\"}',
        content
    )
    content = re.sub(
        r"nvidia_gpu_duty_cycle\{nvidia_gpu_jobId == %s\}",
        'nvidia_gpu_duty_cycle{nvidia_gpu_jobId=\\"%s\\"}',
        content
    )
    
    # Write the patched file
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Successfully patched {filepath}")
    print(f"Backup saved as: {backup_path}")
    return True

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 jobstats_patch.py /path/to/jobstats.py")
        print("Example: python3 jobstats_patch.py /usr/local/jobstats/jobstats.py")
        sys.exit(1)
    
    jobstats_path = sys.argv[1]
    
    if patch_jobstats(jobstats_path):
        print("\nPatch applied successfully!")
        print("\nChanges made:")
        print("1. Added SLURM_CONF environment variable")
        print("2. Changed sacct command to use full path")
        print("3. Removed cluster label from CPU/memory Prometheus queries")
        print("4. Fixed query format strings to match parameter count")
        print("5. Fixed GPU query syntax for proper PromQL")
        print("\nThe jobstats command should now work correctly in BCM environments.")
    else:
        print("Failed to apply patches")
        sys.exit(1)

if __name__ == "__main__":
    main()
