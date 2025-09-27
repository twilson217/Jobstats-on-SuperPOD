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

This repository provides two approaches for deploying jobstats on your DGX SuperPOD:

### 1. Manual Step-by-Step Deployment

For complete control over each step of the deployment process, follow the comprehensive manual guide:

📖 **[How-to Guide](how-to.md)** - Complete step-by-step instructions for manual deployment

This guide covers:
- System architecture and component distribution
- Prerequisites and repository setup
- BCM-specific configuration requirements
- Manual installation on each system type
- Network and firewall configuration
- Verification and troubleshooting

### 2. Automated Deployment

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
