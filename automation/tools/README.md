# Jobstats Automation Tools

This directory contains various tools for testing, validating, and managing the jobstats deployment on BCM (Bright Cluster Manager) systems. These tools are designed to work with the jobstats monitoring platform for Slurm clusters.

## Table of Contents

- [Deployment Testing](#deployment-testing)
- [Deployment Fixes/Patches](#deployment-fixespatches)
- [Workload Testing](#workload-testing)
- [Misc](#misc)

## Deployment Testing

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

## Deployment Fixes/Patches

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

### fix_jobstats_alloc_cores.py

**Purpose**: Fix for jobstats alloc/cores division error where alloc is a string but cores is an integer.

**Use Case**:
- Fix TypeError in output_formatters.py where alloc/cores division fails
- Handle string vs integer type mismatches
- Resolve division errors in memory allocation calculations

**Usage**:
```bash
# Run the fix (must be run on login node where jobstats is installed)
python3 fix_jobstats_alloc_cores.py

# The script will:
# - Create a backup of the original file
# - Apply fixes to handle string alloc values
# - Test the fix with a recent job
# - Provide detailed error handling and recovery
```

**Features**:
- Comprehensive error handling (ValueError, TypeError, ZeroDivisionError)
- Pattern matching fallback if exact line not found
- Built-in testing functionality
- Automatic backup creation with rollback capability

## Workload Testing

### cpu_load_test.py

**Purpose**: CPU load test script for jobstats validation that generates sustained CPU load.

**Use Case**:
- Generate realistic CPU utilization patterns for testing
- Validate jobstats CPU metrics collection
- Create multi-process CPU workloads
- Test jobstats under various CPU loads

**Usage**:
```bash
# Run with default settings (4 processes, 60 seconds)
python3 cpu_load_test.py

# Run with custom parameters
python3 cpu_load_test.py --processes 8 --duration 120 --intensity 80

# Dry-run mode to see what would be executed
python3 cpu_load_test.py --dry-run
```

**Features**:
- Multi-process CPU intensive tasks
- Configurable duration and intensity
- Dry-run mode for testing
- Real-time progress reporting
- Automatic cleanup on completion

### cpu_test_job.sh

**Purpose**: Slurm job script for running CPU load tests in a cluster environment.

**Use Case**:
- Submit CPU load tests as Slurm jobs
- Test jobstats with actual job execution
- Generate job statistics for validation
- Run CPU tests on specific partitions/nodes

**Usage**:
```bash
# Submit the job
sbatch cpu_test_job.sh

# Check job status
squeue -u $USER

# View job output
cat cpu_test_<job_id>.out
```

**Features**:
- Pre-configured Slurm job parameters
- Automatic module loading
- CPU load generation with multiple processes
- Job output and error logging
- Integration with jobstats monitoring

## Misc

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

## Prerequisites

### System Requirements
- BCM (Bright Cluster Manager) system
- Slurm workload manager
- Python 3.6+
- Access to jobstats deployment

### Required Modules
- `slurm` - Slurm commands
- `python` - Python environment

### Required Packages
- `requests` - HTTP library (for validation)
- `multiprocessing` - Built-in Python module (for CPU tests)

### Permissions
- Ability to submit Slurm jobs
- Access to target partitions and nodes
- Read access to jobstats configuration

## Related Documentation

- [Main README](../../README.md)
- [Automation README](../README.md)
- [Troubleshooting Guide](../../Troubleshooting.md)
