# DGX Jobstats Deployment

This repository contains resources for deploying Princeton University's jobstats monitoring platform on NVIDIA DGX SuperPOD systems managed by Base Command Manager (BCM).

## Overview

Jobstats is a comprehensive job monitoring platform designed for CPU and GPU clusters using Slurm. It provides:
- Real-time job utilization metrics
- GPU and CPU performance monitoring
- Automated efficiency reports
- Web-based dashboards via Grafana
- Command-line tools for job analysis

## Deployment Options

This repository provides three approaches for deploying jobstats on your DGX SuperPOD:

### 1. Quick Setup with Guided Installation

For the easiest deployment experience with interactive configuration:

🚀 **[Quick Setup](setup.sh)** - Interactive setup script with guided configuration

The quick setup provides:
- Automatic `uv` installation and configuration
- Interactive `config.json` generation
- Guided setup script integration
- One-command deployment with full automation or dry-run options

**Usage:**
```bash
chmod +x setup.sh
./setup.sh
```

### 2. Interactive Guided Setup

For step-by-step guided deployment with full control and documentation:

📋 **[Guided Setup](automation/guided_setup.py)** - Interactive guided deployment with progress tracking

The guided setup provides:
- Step-by-step interactive deployment following Princeton University's documentation
- Progress tracking and resumption capabilities
- Comprehensive documentation generation
- Full automation or dry-run modes
- BCM-specific configuration and validation

**Usage:**
```bash
# Full automated deployment
uv run python automation/guided_setup.py --config automation/configs/config.json

# Dry-run with documentation generation
uv run python automation/guided_setup.py --config automation/configs/config.json --dry-run
```

### 3. Manual Step-by-Step Deployment

For complete control over each step of the deployment process, follow the comprehensive manual guide:

📖 **[How-to Guide](how-to.md)** - Complete step-by-step instructions for manual deployment

This guide covers:
- System architecture and component distribution
- Prerequisites and repository setup
- BCM-specific configuration requirements
- Manual installation on each system type
- Network and firewall configuration
- Verification and troubleshooting

### 4. Automated Deployment

For streamlined deployment using Python automation scripts:

🤖 **[Automation Guide](automation/README.md)** - Automated deployment with Python scripts

The automation provides:
- Automated dependency installation
- BCM configuration verification
- Shared host support
- Existing monitoring infrastructure support
- BCM imaging guidance
- Dry-run mode for testing

## Quick Start

### For Quick Setup (Recommended)
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd jobstats-on-superpod
   ```
2. Run the interactive setup:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
3. Follow the prompts to configure and deploy jobstats

### For Guided Setup
1. Clone the repository and install dependencies:
   ```bash
   git clone <repository-url>
   cd jobstats-on-superpod
   uv sync
   ```
2. Run the guided setup:
   ```bash
   # Full automated deployment
   uv run python automation/guided_setup.py --config automation/configs/config.json
   
   # Or dry-run with documentation generation
   uv run python automation/guided_setup.py --config automation/configs/config.json --dry-run
   ```

### For Manual Deployment
1. Read the [How-to Guide](how-to.md)
2. Follow the step-by-step instructions for your environment

### For Automated Deployment
1. Review the [Automation Guide](automation/README.md)
2. Choose an appropriate configuration file from `automation/configs/`
3. Run the deployment script:
   ```bash
   cd automation
   python deploy_jobstats.py --config config.json
   ```

## New Features

### 🚀 Quick Setup Script (`setup.sh`)
- **Interactive Configuration**: Guides you through setting up `uv` and generating `config.json`
- **Smart Detection**: Checks for existing installations and configurations
- **Guided Integration**: Optionally runs the guided setup script after configuration
- **One-Command Deployment**: Complete setup from zero to deployed jobstats

### 📋 Guided Setup Script (`automation/guided_setup.py`)
- **Interactive Deployment**: Step-by-step guided deployment following Princeton University's documentation
- **Progress Tracking**: Saves progress and allows resumption if interrupted
- **Documentation Generation**: Creates comprehensive deployment documentation at `automation/logs/guided_setup_document.md`
- **Dry-Run Mode**: Preview all commands before execution
- **BCM Integration**: Proper BCM configuration and validation

### 📄 Generated Documentation
- **Comprehensive Guide**: `automation/logs/guided_setup_document.md` contains complete deployment instructions
- **Manual Reference**: Perfect for manual deployment or troubleshooting
- **Command Reference**: All commands grouped by host and section
- **BCM-Specific**: Includes BCM imaging instructions and category management

### 🔍 Validation Script (`automation/tools/validate_jobstats_deployment.py`)
- **Comprehensive Testing**: Validates all components and configurations
- **BCM-Aware**: Checks BCM-specific configurations and paths
- **Service Validation**: Verifies all services are running correctly
- **Metrics Testing**: Tests all metrics endpoints and Prometheus targets

## Configuration Files

The `automation/configs/` directory contains example configurations for different deployment scenarios:

- `config.json.template` - Template for custom configurations
- `config-shared-hosts.json` - For environments with shared hosts
- `config-existing-monitoring.json` - For existing Prometheus/Grafana setups
- `config-category-management.json` - For BCM category-based service management

## System Requirements

- DGX system with BCM management
- Slurm workload manager with cgroup support
- NVIDIA GPUs with nvidia-smi
- Go compiler (for building exporters)
- Python 3.6+ with requests and blessed libraries
- Git (for cloning repositories)
- Internet access (for downloading components)

## Architecture

The jobstats platform consists of several components distributed across different systems:

- **BCM Head Node**: Cluster management (no jobstats components required)
- **Slurm Controller Node**: Slurm controller, accounting database, and prolog/epilog scripts
- **Slurm Login Nodes**: jobstats command-line tool and Python dependencies
- **DGX Compute Nodes**: Exporters for CPU, GPU, and system metrics
- **Prometheus Server**: Time-series database for metrics collection
- **Grafana Server**: Web interface for visualization and dashboards

## Support

For issues specific to this DGX deployment:
1. Check service logs using `journalctl`
2. Verify BCM configuration changes
3. Test individual components (exporters, Prometheus, Grafana)
4. Consult the original Princeton jobstats documentation

## Additional Resources

- [Princeton Jobstats Repository](https://github.com/PrincetonUniversity/jobstats)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Slurm Cgroup Configuration](https://slurm.schedmd.com/cgroups.html)

## License

This deployment guide and automation scripts are provided as-is for deploying Princeton University's jobstats platform. Please refer to the original jobstats repository for licensing information.
