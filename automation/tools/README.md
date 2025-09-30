# Jobstats Automation Tools

This directory contains various tools for testing, validating, and managing the jobstats deployment on BCM (Bright Cluster Manager) systems. These tools are designed to work with the jobstats monitoring platform for Slurm clusters.

## Table of Contents

- [Overview](#overview)
- [Tools](#tools)
  - [validate_jobstats_deployment.py](#validate_jobstats_deploymentpy)
  - [convert_pdfs.sh](#convert_pdfssh)
  - [fix_jobstats_timelimit.py](#fix_jobstats_timelimitpy)
- [Usage Examples](#usage-examples)
- [Prerequisites](#prerequisites)
- [Troubleshooting](#troubleshooting)

## Overview

The jobstats platform provides comprehensive monitoring and statistics for Slurm job execution, including CPU usage, GPU utilization, memory consumption, and other resource metrics. These tools help validate that the deployment is working correctly and provide test workloads to generate meaningful data.

## Tools

### validate_jobstats_deployment.py

**Purpose**: Comprehensive validation script that tests all components of the jobstats deployment.

**Use Case**: 
- Verify that all services are running correctly
- Check that exporters are collecting metrics
- Validate Prometheus configuration
- Test Grafana connectivity
- Ensure BCM configuration is correct

**Usage**:
```bash
# Run with default config file
python3 validate_jobstats_deployment.py

# Run with specific config file
python3 validate_jobstats_deployment.py --config /path/to/config.json

# Run specific test sections
python3 validate_jobstats_deployment.py --sections "1,2,3"
```

**Features**:
- 35 comprehensive validation tests
- Tests all exporters (node, cgroup, GPU)
- Validates Prometheus and Grafana
- Checks BCM configuration
- Provides detailed pass/fail reporting

### convert_pdfs.sh

**Purpose**: Utility script for converting PDF files (legacy tool).

**Use Case**:
- Convert PDF documentation
- Batch PDF processing
- Documentation management

**Usage**:
```bash
# Convert single PDF
./convert_pdfs.sh input.pdf

# Convert multiple PDFs
./convert_pdfs.sh *.pdf
```

### fix_jobstats_timelimit.py

**Purpose**: Fix for jobstats timelimit parsing issues with UNLIMITED time limits.

**Use Case**:
- Fix TypeError when jobstats encounters UNLIMITED time limits
- Resolve string vs integer comparison errors
- Fix repeated "UNLIMITED" display in time limit field

**Usage**:
```bash
# Run the fix (must be run on login node where jobstats is installed)
python3 fix_jobstats_timelimit.py

# The script will:
# - Create a backup of the original file
# - Apply fixes to handle UNLIMITED time limits
# - Test the fix with a recent job
# - Restore from backup if something goes wrong
```

**Features**:
- Automatic backup creation
- Safe error handling with rollback
- Built-in testing to verify fix works
- Handles both string comparison and formatting issues

## Usage Examples

### Complete Deployment Validation

```bash
# 1. Validate the entire deployment
python3 validate_jobstats_deployment.py

# 2. Check jobstats output for existing jobs
jobstats -j <job_id>
```

### Jobstats Fix Workflow

```bash
# 1. Fix jobstats UNLIMITED time limit issues
python3 fix_jobstats_timelimit.py

# 2. Test the fix
python3 fix_jobstats_timelimit.py --test

# 3. Verify jobstats works correctly
jobstats -j <job_id>
```

## Prerequisites

### System Requirements
- BCM (Bright Cluster Manager) system
- Slurm workload manager
- Python 3.6+
- CUDA (for GPU tests)
- Access to jobstats deployment

### Required Modules
- `slurm` - Slurm commands
- `cuda` - CUDA toolkit
- `python` - Python environment

### Required Packages
- `torch` - PyTorch (auto-installed by test scripts)
- `numpy` - Numerical computing (auto-installed)
- `requests` - HTTP library (for validation)

### Permissions
- Ability to submit Slurm jobs
- Access to target partitions and nodes
- Read access to jobstats configuration

## Troubleshooting

### Common Issues

#### 1. "sbatch not found" Error
```bash
# Load Slurm module
module load slurm

# Or set PATH
export PATH=/cm/shared/apps/slurm/bin:$PATH
```

#### 2. "CUDA not available" Error
```bash
# Load CUDA module
module load cuda

# Check CUDA availability
nvidia-smi
```

#### 3. "jobstats command not found"
```bash
# Check if jobstats is installed
which jobstats

# Check symlink
ls -la /usr/local/bin/jobstats
```

#### 4. Dry-run Output Truncated
The dry-run functionality works correctly but may appear truncated in some terminals. The complete output is generated and can be redirected to a file:

```bash
./test_jobstats_pytorch.sh --dry-run --duration 2 > dry_run_output.txt
cat dry_run_output.txt
```

#### 5. Permission Denied
```bash
# Make scripts executable
chmod +x *.sh

# Check file permissions
ls -la *.sh
```

### Validation Failures

If validation tests fail, check:

1. **Services Status**:
   ```bash
   systemctl status prometheus
   systemctl status grafana-server
   systemctl status cgroup_exporter
   systemctl status nvidia_gpu_prometheus_exporter
   ```

2. **Port Accessibility**:
   ```bash
   netstat -tlnp | grep -E "(9090|3000|9100|9306|9445)"
   ```

3. **Configuration Files**:
   ```bash
   ls -la /etc/prometheus/prometheus.yml
   ls -la /etc/grafana/grafana.ini
   ```

4. **Log Files**:
   ```bash
   journalctl -u prometheus -f
   journalctl -u grafana-server -f
   ```

### Getting Help

1. **Check Logs**: All tools provide detailed error messages
2. **Dry-run Mode**: Use `--dry-run` to see what would be executed
3. **Validation Script**: Run `validate_jobstats_deployment.py` for comprehensive diagnostics
4. **Manual Testing**: Use individual tools to isolate issues

## Contributing

When adding new tools to this directory:

1. Follow the naming convention: `test_jobstats_*.py` or `test_jobstats_*.sh`
2. Include comprehensive help text (`--help`)
3. Support both interactive and non-interactive modes
4. Include dry-run functionality where appropriate
5. Update this README.md with tool documentation
6. Test thoroughly on BCM systems

## Related Documentation

- [Jobstats Setup Guide](../../docs/setup/)
- [BCM Configuration Guide](../../docs/bcm/)
- [Troubleshooting Guide](../../docs/troubleshooting/)
- [Main README](../../README.md)
