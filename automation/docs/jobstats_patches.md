# Jobstats Patches for BCM Environment

This document describes the patches applied to the jobstats code to make it work correctly in a BCM (Bright Cluster Manager) environment.

## Issues Discovered

During deployment testing, several issues were identified that prevented jobstats from working correctly:

### 1. Prometheus Query Cluster Label Requirement
**Issue**: Jobstats hardcodes a requirement for a `cluster` label in Prometheus queries, but our BCM setup doesn't use cluster labels.

**Error**: Queries like `cgroup_memory_total_bytes{cluster='slurm',jobid='123'}` fail because no metrics have cluster labels.

**Solution**: Remove cluster label from all Prometheus queries.

### 2. sacct Command Not Found
**Issue**: The `sacct` command is not in the PATH for non-root users, causing jobstats to fail when trying to look up job information.

**Error**: `FileNotFoundError: [Errno 2] No such file or directory: 'sacct'`

**Solution**: Use the full path to sacct: `/cm/shared/apps/slurm/current/bin/sacct`

### 3. Missing SLURM_CONF Environment Variable
**Issue**: Slurm commands need the `SLURM_CONF` environment variable to find the configuration file.

**Error**: `sacct: error: resolve_ctls_from_dns_srv: res_nsearch error: Unknown host`

**Solution**: Set `SLURM_CONF=/cm/shared/apps/slurm/var/etc/slurm/slurm.conf`

### 4. Query Format String Parameter Mismatch
**Issue**: After removing cluster labels, the query format strings still expect 3 parameters but only receive 2.

**Error**: `TypeError: %d format: a real number is required, not str`

**Solution**: Update format string calls to match the new parameter count.

### 5. GPU Query Syntax Errors
**Issue**: GPU queries use invalid PromQL syntax with `==` instead of `=` and missing quotes.

**Error**: `parse error: unexpected "=" in label matching, expected string`

**Solution**: Change `nvidia_gpu_jobId == %s` to `nvidia_gpu_jobId="%s"`

## Patches Applied

The `jobstats_patch.py` script applies the following patches:

1. **Environment Variables**: Adds `SLURM_CONF` environment variable
2. **Command Paths**: Changes `sacct` to use full path
3. **CPU/Memory Queries**: Removes cluster labels from cgroup queries
4. **Query Format**: Fixes parameter count in format strings
5. **GPU Queries**: Fixes PromQL syntax for GPU metrics

## Usage

To apply patches to jobstats:

```bash
python3 automation/tools/jobstats_patch.py /usr/local/jobstats/jobstats.py
```

The script will:
- Create a timestamped backup of the original file
- Apply all necessary patches
- Report success/failure

## Testing

After applying patches, test jobstats with:

```bash
# Submit a test job
sbatch --partition=defq --time=2:00 --wrap='sleep 60 && echo Job completed'

# Check job status
squeue

# Test jobstats (replace JOBID with actual job ID)
jobstats JOBID -c slurm
```

## Integration with Guided Setup

These patches should be integrated into the `guided_setup.py` script in the jobstats command section to ensure they are applied during deployment.

## Files Modified

- `automation/tools/jobstats_patch.py` - Patch application script
- `automation/docs/jobstats_patches.md` - This documentation
- `/usr/local/jobstats/jobstats.py` - Target file for patches (when applied)

## Backup Files

The patch script creates timestamped backups:
- `/usr/local/jobstats/jobstats.py.backup.YYYYMMDD_HHMMSS`

## Notes

- Patches are designed to be idempotent (safe to run multiple times)
- The script validates file existence before applying patches
- All changes are documented and reversible via backup files
