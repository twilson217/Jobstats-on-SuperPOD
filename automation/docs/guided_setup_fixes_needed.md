# Guided Setup Script Fixes Needed

## Issues in guided_setup.py That Need to be Fixed

This document lists issues discovered during testing that were caused by the `guided_setup.py` script and need to be corrected in the automation.

### 1. Jobstats Installation Path Issue

**Problem**: Jobstats files are installed in `/usr/local/bin/` instead of `/usr/local/jobstats/` as documented.

**Expected Structure** (from jobstats documentation):
```
/usr/local/jobstats/
├── config.py
├── jobstats
├── jobstats.py
└── output_formatters.py

/usr/local/bin/jobstats -> /usr/local/jobstats/jobstats
```

**Current Structure** (what guided_setup.py creates):
```
/usr/local/bin/
├── config.py
├── jobstats
├── jobstats.py
└── output_formatters.py
```

**Fix Needed**: Update `section_jobstats_command` in `guided_setup.py` to:
1. Create `/usr/local/jobstats/` directory
2. Install files in `/usr/local/jobstats/` instead of `/usr/local/bin/`
3. Create symbolic link from `/usr/local/bin/jobstats` to `/usr/local/jobstats/jobstats`

### 2. Cgroup Exporter Configuration Paths

**Problem**: cgroup_exporter configured with incorrect paths that don't exist in BCM environment.

**Current Configuration** (what guided_setup.py creates):
```bash
--config.paths=/user.slice,/system.slice,/slurm
```

**Correct Configuration** (what we had to manually fix):
```bash
--config.paths=/sys/fs/cgroup/cpu,cpuacct/slurm,/sys/fs/cgroup/memory/slurm,/sys/fs/cgroup/freezer/slurm,/sys/fs/cgroup/devices/slurm
```

**Fix Needed**: Update `section_cpu_job_stats` in `guided_setup.py` to use the correct cgroup paths for BCM environment.

### 3. Jobstats Config.py Prometheus Server Address

**Problem**: config.py created with wrong Prometheus server address.

**Current Configuration** (what guided_setup.py creates):
```python
PROM_SERVER = "http://cluster-stats:8480"
```

**Correct Configuration** (what we had to manually fix):
```python
PROM_SERVER = "http://statsrv:9090"
```

**Fix Needed**: Update `section_jobstats_command` in `guided_setup.py` to use the correct Prometheus server address from config.json.

### 4. Cgroup Exporter Service File Location

**Problem**: cgroup_exporter service file created in wrong location.

**Current Location** (what guided_setup.py creates):
```
/etc/systemd/system/cgroup_exporter.service
```

**Note**: This is actually correct, but the content was wrong (see issue #2 above).

**Fix Needed**: Ensure the service file content uses correct cgroup paths (already covered in issue #2).

## Files That Need Updates

### guided_setup.py

1. **`section_cpu_job_stats`**:
   - ✅ **FIXED**: cgroup_exporter service configuration paths
   - ✅ **FIXED**: Use correct cgroup paths for BCM environment

2. **`section_jobstats_command`**:
   - ✅ **FIXED**: Create `/usr/local/jobstats/` directory
   - ✅ **FIXED**: Install jobstats files in correct location
   - ✅ **FIXED**: Create symbolic link
   - ✅ **FIXED**: Use correct Prometheus server address from config.json

### guided_setup_document.md

The generated documentation will also be updated to reflect these corrections when the script runs.

## Testing Required

After implementing these fixes, test:
1. ✅ Jobstats files are in correct location with proper symlink
2. ⚠️ Cgroup exporter collects job-specific metrics (depends on Slurm cgroup configuration)
3. ⚠️ Jobstats command works with correct Prometheus server (depends on job metrics collection)
4. ✅ Generated documentation shows correct paths and configurations

## Status: ✅ **FIXES IMPLEMENTED**

All three critical issues have been fixed in `guided_setup.py`:
- Jobstats installation now uses correct directory structure with symlink
- Cgroup exporter now uses correct BCM cgroup paths
- Config.py now automatically updated with correct Prometheus server address
