# BCM Jobstats Deployment Automation

This project provides automated deployment of Princeton University's jobstats monitoring platform on BCM-managed DGX systems.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Guided Setup Script](#guided-setup-script)
  - [What it does](#what-it-does)
  - [Input Files](#input-files)
  - [Output Files](#output-files)
  - [Usage](#usage)
- [BCM Role Monitor Service](#bcm-role-monitor-service)
  - [Overview](#overview)
  - [Key Features](#key-features)
  - [Architecture](#architecture)
  - [Components](#components)
  - [Deployment](#deployment)
  - [Prometheus Integration](#prometheus-integration)
  - [Configuration](#configuration)
  - [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
  - [Integration with BCM Imaging](#integration-with-bcm-imaging)
- [Additional Automation Tools](#additional-automation-tools)

---

## Prerequisites

**Note**: The `setup.sh` script in the main README should have already handled these prerequisites:

- BCM head node with passwordless SSH access to all target systems
- `uv` package manager installed
- `cmsh` access for BCM configuration verification
- Internet access for downloading components

## Guided Setup Script

The `automation/guided_setup.py` script provides step-by-step interactive deployment:

### What it does:
- **Interactive Deployment**: Follows Princeton University's documentation flow
- **Progress Tracking**: Saves progress and allows resumption if interrupted
- **Documentation Generation**: Creates comprehensive deployment documentation
- **Dry-Run Mode**: Preview all commands before execution
- **BCM Integration**: Proper BCM configuration and validation
- **10 Comprehensive Sections**: Covers all aspects of jobstats deployment

### Input Files:
The script uses configuration files from the `automation/configs/` directory:

**Default Configuration:**
- `config.json` - Main configuration file (used by default)

**Template Configurations:**
- `config-shared-hosts.json` - Template for shared host environments
- `config-existing-monitoring.json` - Template for existing Prometheus/Grafana

### Output Files:
The script generates files in the `automation/logs/` directory:
- `guided_setup_document.md` - Complete deployment documentation
- `guided_setup_progress.json` - Progress tracking for resumption

### Usage:
```bash
# Full automated deployment
uv run python automation/guided_setup.py --config automation/configs/config.json

# Dry-run with documentation generation
uv run python automation/guided_setup.py --config automation/configs/config.json --dry-run

# Resume interrupted deployment
uv run python automation/guided_setup.py --config automation/configs/config.json --resume
```

## BCM Role Monitor Service

The BCM role monitor is an automated service management system that runs on DGX nodes to monitor BCM role assignments and automatically manage jobstats exporter services based on configuration overlays.

### Overview

The BCM role monitor solves the problem where jobstats exporter services (cgroup_exporter, node_exporter, nvidia_gpu_exporter) need to be automatically started/stopped when nodes switch between different BCM categories or role assignments.

### Key Features

- **Automatic Service Management**: Starts/stops jobstats exporters based on `slurmclient` role assignment
- **BCM REST API Integration**: Uses BCM's `/rest/v1/device` endpoint for real-time role monitoring
- **Distributed Architecture**: Runs on each DGX node independently
- **Retry Logic**: Intelligent retry mechanism for failed service starts (3 attempts over 30 minutes)
- **Secure Configuration**: Certificates stored in `/etc/bcm-role-monitor/` with minimal permissions
- **BCM Imaging Compatible**: Uses dynamic hostname lookup for seamless image deployment

### Architecture

```
BCM Headnode(s) ←─── REST API (port 8081) ←─── DGX Node (bcm-role-monitor service)
                                                      ↓
                                              Manages Local Services:
                                              • cgroup_exporter
                                              • node_exporter  
                                              • nvidia_gpu_exporter
```

### Components

The BCM role monitor consists of three main components:

#### 1. bcm_role_monitor.py
- **Location**: `/usr/local/bin/bcm_role_monitor.py` on DGX nodes
- **Purpose**: Main monitoring service script
- **Features**:
  - Monitors BCM REST API every 60 seconds
  - Manages systemd services based on role changes
  - Automatically manages Prometheus target files for dynamic service discovery
  - Handles retry logic for failed service starts
  - Comprehensive logging and error handling
  - Supports custom Prometheus targets directory via command-line argument

#### 2. bcm-role-monitor.service
- **Location**: `/etc/systemd/system/bcm-role-monitor.service` on DGX nodes
- **Purpose**: Systemd service unit file
- **Features**:
  - Runs as root with security restrictions
  - Automatic restart on failure
  - Proper dependency management

#### 3. deploy_bcm_role_monitor.py
- **Location**: `automation/role-monitor/deploy_bcm_role_monitor.py`
- **Purpose**: Deployment script for BCM headnode
- **Features**:
  - Automatic BCM headnode discovery using `cmsh`
  - Secure certificate deployment
  - Service configuration and startup

### Deployment

The BCM role monitor is automatically deployed as part of the guided setup process (Section 10), but can also be deployed independently:

#### Automatic Deployment (Recommended)
```bash
# Deploy via guided setup
uv run python automation/guided_setup.py --config automation/configs/config.json

# The BCM role monitor is deployed in Section 10
```

#### Manual Deployment
```bash
# Deploy to specific DGX nodes
python3 automation/role-monitor/deploy_bcm_role_monitor.py --dgx-nodes dgx-01 dgx-02

# Deploy to all DGX nodes from config
python3 automation/role-monitor/deploy_bcm_role_monitor.py --config automation/configs/config.json
```

### Prometheus Integration

The BCM role monitor automatically manages Prometheus service discovery, eliminating the need for manual target configuration:

- **Automatic Target Management**: When a node receives the `slurmclient` role, it creates a JSON file containing all three exporters (node_exporter, cgroup_exporter, gpu_exporter)
- **Dynamic Updates**: Target files are automatically created/removed based on role assignment changes
- **Single File Per Node**: Each node manages one JSON file: `/cm/shared/apps/jobstats/prometheus-targets/<hostname>.json`
- **Custom Directory Support**: Use `--prometheus-targets-dir` to specify a different shared storage location for existing Prometheus deployments
- **Hostname Change Resilient**: Automatically handles hostname changes via BCM imaging

**For comprehensive documentation**, see [automation/role-monitor/README.md](role-monitor/README.md)

### Configuration

The service is configured via `/etc/bcm-role-monitor/config.json` on each DGX node:

```json
{
  "bcm_headnodes": ["bcm-headnode-01", "bcm-headnode-02"],
  "bcm_port": 8081,
  "cert_path": "/etc/bcm-role-monitor/admin.pem",
  "key_path": "/etc/bcm-role-monitor/admin.key",
  "check_interval": 60,
  "retry_interval": 600,
  "max_retries": 3
}
```

### Monitoring and Troubleshooting

#### Service Status
```bash
# Check service status
systemctl status bcm-role-monitor.service

# View recent logs
journalctl -u bcm-role-monitor.service -n 20

# Follow logs in real-time
journalctl -u bcm-role-monitor.service -f
```

#### Manual Testing
```bash
# Test the script manually
python3 /usr/local/bin/bcm_role_monitor.py

# Test BCM API connectivity
curl -s --cert /etc/bcm-role-monitor/admin.pem --key /etc/bcm-role-monitor/admin.key --insecure https://bcm-headnode:8081/rest/v1/device
```

### Integration with BCM Imaging

The BCM role monitor is designed to work seamlessly with BCM's imaging workflow:

1. **Deploy to representative nodes** using the deployment script
2. **Test the service** to ensure proper operation
3. **Capture BCM images** using `cmsh -c 'device;use <node>;grabimage -w'`
4. **Deploy images** to additional nodes of the same type

The service automatically discovers its own hostname and BCM headnodes, making it fully compatible with BCM imaging processes.

## Additional Automation Tools

For detailed information about additional automation tools including validation scripts, deployment utilities, and testing frameworks, see [automation/tools/README.md](tools/README.md).

