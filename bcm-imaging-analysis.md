# BCM Imaging Analysis for Jobstats Deployment

## Overview

BCM uses a node imaging system where software is installed on one representative node of each type, then captured using `grabimage` and deployed to all nodes of that type. This analysis examines what files our jobstats deployment creates and whether they need to be excluded from imaging.

## BCM Imaging Process

1. **Install on representative node**: Deploy jobstats on one DGX node, one Slurm controller, etc.
2. **Capture image**: `cmsh -c "device;use <hostname>;grabimage -w"`
3. **Deploy to all nodes**: BCM automatically deploys the image to all nodes of the same type

## Files Created by Jobstats Deployment

### 1. Shared Storage Files (Safe for Imaging)
- `/cm/shared/apps/slurm/var/cm/prolog-jobstats.sh`
- `/cm/shared/apps/slurm/var/cm/epilog-jobstats.sh`

**Analysis**: ✅ **SAFE** - These are in shared storage and should be identical across all nodes.

### 2. Symlinks (Safe for Imaging)
- `/cm/local/apps/slurm/var/prologs/60-prolog-jobstats.sh` → `/cm/shared/apps/slurm/var/cm/prolog-jobstats.sh`
- `/cm/local/apps/slurm/var/epilogs/60-epilog-jobstats.sh` → `/cm/shared/apps/slurm/var/cm/epilog-jobstats.sh`

**Analysis**: ✅ **SAFE** - Symlinks point to shared storage and should be identical across all nodes.

### 3. Binary Files (Safe for Imaging)
- `/usr/local/bin/jobstats`
- `/usr/local/bin/jobstats.py`
- `/usr/local/bin/output_formatters.py`
- `/usr/local/bin/config.py`
- `/usr/local/bin/cgroup_exporter`
- `/usr/local/bin/nvidia_gpu_prometheus_exporter`
- `/usr/local/bin/node_exporter`
- `/usr/local/bin/prometheus`
- `/usr/local/bin/promtool`

**Analysis**: ✅ **SAFE** - Binary files are identical across all nodes.

### 4. Systemd Service Files (Safe for Imaging)
- `/etc/systemd/system/cgroup_exporter.service`
- `/etc/systemd/system/node_exporter.service`
- `/etc/systemd/system/nvidia_gpu_prometheus_exporter.service`
- `/etc/systemd/system/prometheus.service`

**Analysis**: ✅ **SAFE** - Service files are identical across all nodes.

### 5. Prometheus Configuration (Safe for Imaging)
- `/etc/prometheus/prometheus.yml`

**Analysis**: ✅ **SAFE** - Configuration contains node hostnames but they're templated and will be correct for each node.

### 6. Prometheus Data Directory (Safe for Imaging)
- `/var/lib/prometheus/`

**Analysis**: ✅ **SAFE** - Data directory will be empty on new nodes and will populate correctly.

### 7. User Creation (Safe for Imaging)
- `prometheus` user creation

**Analysis**: ✅ **SAFE** - User creation is idempotent and safe to replicate.

## Files That Are NOT Created

Our deployment does NOT create any host-specific files such as:
- `/etc/hostname`
- `/etc/hosts`
- `/etc/machine-id`
- `/var/lib/systemd/random-seed`
- Network configuration files
- SSH host keys

## Conclusion

**✅ NO EXCLUDE LIST CHANGES NEEDED**

All files created by the jobstats deployment are safe for BCM imaging:

1. **Shared storage files** are meant to be identical across nodes
2. **Binary files** are identical across all nodes
3. **Configuration files** use hostname templating that works correctly on each node
4. **Systemd services** are identical across all nodes
5. **No host-specific files** are created that would cause conflicts

## BCM Imaging Workflow for Jobstats

### For DGX Nodes:
1. Deploy jobstats on one DGX node
2. `cmsh -c "device;use dgx-node-01;grabimage -w"`
3. BCM deploys image to all DGX nodes

### For Slurm Controllers:
1. Deploy jobstats on one Slurm controller
2. `cmsh -c "device;use slurm-controller-01;grabimage -w"`
3. BCM deploys image to all Slurm controllers

### For Login Nodes:
1. Deploy jobstats on one login node
2. `cmsh -c "device;use login-node-01;grabimage -w"`
3. BCM deploys image to all login nodes

## Recommendations

1. **No exclude list modifications needed** - All jobstats files are safe for imaging
2. **Follow standard BCM imaging workflow** - Install on one node per type, then grabimage
3. **Test on one node first** - Verify jobstats works correctly before imaging
4. **Monitor after imaging** - Ensure all nodes start services correctly after image deployment

## BCM Exclude Lists (Reference)

The standard BCM exclude lists already handle host-specific files:
- `/etc/hostname`
- `/etc/hosts`
- `/etc/machine-id`
- Network configuration
- SSH keys
- System-specific logs

Our jobstats deployment does not create any files that would conflict with these exclusions.
