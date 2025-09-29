# BCM Jobstats Deployment Automation

This project provides automated deployment of Princeton University's jobstats monitoring platform on BCM-managed DGX systems.

## Features

- **🚀 Quick Setup**: Interactive `setup.sh` script for one-command deployment
- **📋 Guided Setup**: Step-by-step interactive deployment with progress tracking
- **📄 Documentation Generation**: Creates comprehensive deployment documentation
- **🔍 Validation Script**: Comprehensive testing and validation of all components
- **BCM Integration**: Uses `cmsh` to verify configurations and follows BCM best practices
- **Symlink Pattern**: Implements BCM's shared storage symlink pattern for script management
- **Shared Host Support**: Intelligently handles shared systems (e.g., same node for Slurm controller and login)
- **BCM Category-Based Service Management**: Automatically manages jobstats services based on BCM categories (Slurm vs Kubernetes)
- **Dry Run Mode**: Preview all commands before execution
- **Multi-System Support**: Deploys across Slurm controllers, login nodes, DGX nodes, and monitoring servers
- **Dependency Management**: Uses `uv` for Python project management
- **SSH Automation**: Leverages passwordless SSH for remote deployment

## Prerequisites

- BCM head node with passwordless SSH access to all target systems
- `uv` package manager installed
- `cmsh` access for BCM configuration verification
- Internet access for downloading components

## Quick Start

### Option 1: Quick Setup (Recommended)

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd jobstats-on-superpod
   ```

2. **Run the interactive setup**:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Follow the prompts** to configure and deploy jobstats automatically

### Option 2: Guided Setup

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Make uv available in your current shell**:
   ```bash
   source ~/.bashrc
   ```
   
   **Verify uv is working**:
   ```bash
   uv --version
   ```

3. **Clone and setup the project**:
   ```bash
   git clone <repository-url>
   cd jobstats-on-superpod
   uv sync
   ```

4. **Run the guided setup**:
   ```bash
   # Full automated deployment
   uv run python automation/guided_setup.py --config automation/configs/config.json
   
   # Or dry-run with documentation generation
   uv run python automation/guided_setup.py --config automation/configs/config.json --dry-run
   ```

### Option 3: Traditional Automation

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Make uv available in your current shell**:
   ```bash
   source ~/.bashrc
   ```
   
   **Verify uv is working**:
   ```bash
   uv --version
   ```

3. **Clone and setup the project**:
   ```bash
   git clone <repository-url>
   cd jobstats-on-superpod
   uv sync
   ```
   
   **Note**: All subsequent commands should be run from the project root directory (`jobstats-on-superpod/`).

4. **Configure your systems**:
   ```bash
   cp automation/configs/config.json.template automation/configs/config.json
   # Edit automation/configs/config.json with your actual system hostnames
   ```
   
   **Note**: The script will look for config files in `automation/configs/` directory. You can also use any of the example configs:
   - `config-shared-hosts.json` - For shared host environments
   - `config-existing-monitoring.json` - For existing Prometheus/Grafana
   - `config-category-management.json` - For BCM category management

5. **Run a dry-run to preview commands**:
   ```bash
   uv run python automation/deploy_jobstats.py --config config.json --dry-run
   ```

6. **Deploy jobstats**:
   ```bash
   uv run python automation/deploy_jobstats.py --config config.json
   ```

## New Features

### 🚀 Quick Setup Script (`setup.sh`)

The quick setup script provides the easiest way to get started:

- **Interactive Configuration**: Guides you through setting up `uv` and generating `config.json`
- **Smart Detection**: Checks for existing installations and configurations
- **Guided Integration**: Optionally runs the guided setup script after configuration
- **One-Command Deployment**: Complete setup from zero to deployed jobstats

**Usage:**
```bash
chmod +x setup.sh
./setup.sh
```

### 📋 Guided Setup Script (`automation/guided_setup.py`)

The guided setup script provides step-by-step interactive deployment:

- **Interactive Deployment**: Follows Princeton University's documentation flow
- **Progress Tracking**: Saves progress and allows resumption if interrupted
- **Documentation Generation**: Creates comprehensive deployment documentation
- **Dry-Run Mode**: Preview all commands before execution
- **BCM Integration**: Proper BCM configuration and validation

**Usage:**
```bash
# Full automated deployment
uv run python automation/guided_setup.py --config automation/configs/config.json

# Dry-run with documentation generation
uv run python automation/guided_setup.py --config automation/configs/config.json --dry-run

# Resume interrupted deployment
uv run python automation/guided_setup.py --config automation/configs/config.json --resume
```

**Features:**
- **10 Comprehensive Sections**: Covers all aspects of jobstats deployment
- **Progress Persistence**: Saves progress to `automation/logs/guided_setup_progress.json`
- **Documentation Output**: Generates `automation/logs/guided_setup_document.md`
- **BCM-Specific**: Includes BCM imaging instructions and category management
- **Error Recovery**: Can resume from any point if interrupted

### 📄 Generated Documentation

The guided setup creates comprehensive documentation at `automation/logs/guided_setup_document.md`:

- **Complete Deployment Guide**: All commands grouped by host and section
- **Manual Reference**: Perfect for manual deployment or troubleshooting
- **BCM-Specific Instructions**: Includes BCM imaging and category management
- **Command Reference**: All commands with proper formatting and comments

### 🔍 Validation Script (`automation/tools/validate_jobstats_deployment.py`)

The validation script provides comprehensive testing and validation:

- **Service Validation**: Checks all systemd services are running
- **Port Testing**: Verifies all required ports are listening
- **Metrics Testing**: Tests all metrics endpoints and Prometheus targets
- **BCM Configuration**: Validates BCM-specific configurations
- **Slurm Integration**: Checks prolog/epilog scripts and jobstats command
- **Comprehensive Reporting**: Detailed test results with pass/fail status

**Usage:**
```bash
# Validate deployment
uv run python automation/tools/validate_jobstats_deployment.py

# Validate with custom config
uv run python automation/tools/validate_jobstats_deployment.py --config my_config.json
```

**Test Coverage:**
- ✅ Systemd Services (5 tests)
- ✅ Service Ports (5 tests)
- ✅ Metrics Endpoints (3 tests)
- ✅ Prometheus Targets (1 test)
- ✅ Slurm Integration (3 tests)
- ✅ BCM Configuration (8 tests)
- ✅ Jobstats Command (1 test)
- ✅ BCM Requirements (9 tests)

**Total: 35 comprehensive tests**

### 📋 Guided Setup Sections

The guided setup script follows Princeton University's documentation and includes 10 comprehensive sections:

1. **Setup Overview** - Introduction and system requirements
2. **CPU Job Statistics** - Slurm cgroup configuration and cgroup_exporter
3. **GPU Job Statistics** - NVIDIA GPU exporter and prolog/epilog scripts
4. **Node Statistics** - Node exporter for system metrics
5. **Job Summaries** - Slurmctld epilog and BCM configuration
6. **Prometheus** - Time series database installation and configuration
7. **Grafana** - Web interface installation and setup
8. **Open OnDemand Jobstats Helper** - OOD integration (optional)
9. **The jobstats Command** - Command-line tool installation
10. **Additional BCM Configurations** - BCM imaging and category management

Each section includes:
- **Interactive Prompts**: User confirmation before each step
- **Progress Tracking**: Saves progress for resumption
- **Documentation Generation**: Creates comprehensive deployment guide
- **BCM Integration**: Proper BCM configuration and validation
- **Error Handling**: Graceful error recovery and reporting

## Configuration

The `config.json` file defines your cluster topology and settings:

### Shared Host Support

The deployment script intelligently handles shared hosts (common in production environments):
- **Same host for multiple roles**: Automatically detects and deploys all required components
- **Dependency optimization**: Avoids duplicate package installations
- **Role-based deployment**: Each role's components are deployed in the correct order

### Shared Host Example

For environments where the Slurm controller and login node are the same (commonly called "slogin" nodes), and Prometheus and Grafana share a server:

```json
{
  "cluster_name": "slurm",
  "prometheus_server": "monitoring-01",
  "grafana_server": "monitoring-01",
  "systems": {
    "slurm_controller": ["slogin-01"],
    "login_nodes": ["slogin-01"],
    "dgx_nodes": ["dgx-node-01", "dgx-node-02"],
    "prometheus_server": ["monitoring-01"],
    "grafana_server": ["monitoring-01"]
  }
}
```

This configuration will:
- Deploy both Slurm controller and login node components on `slogin-01`
- Deploy both Prometheus and Grafana on `monitoring-01`
- Handle dependency installation efficiently without conflicts

### Existing Monitoring Infrastructure

For environments with existing Prometheus and/or Grafana installations:

```json
{
  "cluster_name": "slurm",
  "prometheus_server": "existing-prometheus.company.com",
  "grafana_server": "existing-grafana.company.com",
  "use_existing_prometheus": true,
  "use_existing_grafana": true,
  "systems": {
    "slurm_controller": ["slurm-controller-01"],
    "login_nodes": ["login-node-01"],
    "dgx_nodes": ["dgx-node-01", "dgx-node-02"],
    "prometheus_server": [],
    "grafana_server": []
  }
}
```

**Important**: When using existing installations:
- Set `use_existing_prometheus: true` and/or `use_existing_grafana: true`
- Leave `prometheus_server` and `grafana_server` arrays empty in systems
- The script will provide detailed configuration guidance instead of installing
- You'll need to manually configure your existing systems (see below)

### BCM Category-Based Service Management

For customers with mixed DGX environments (Slurm and Kubernetes categories), jobstats services can be tied to the Slurm category so they automatically start/stop when nodes switch between categories:

```json
{
  "cluster_name": "slurm",
  "bcm_category_management": true,
  "slurm_category": "slurm-category",
  "kubernetes_category": "kubernetes-category",
  "systems": {
    "dgx_nodes": ["dgx-node-01", "dgx-node-02", "dgx-node-03"],
    "slurm_dgx_nodes": ["dgx-node-01", "dgx-node-02"],
    "kubernetes_dgx_nodes": ["dgx-node-03"]
  }
}
```

**Benefits**:
- **Same software image** for all DGX nodes
- **Automatic service management** based on category assignment
- **No manual intervention** when switching between Slurm and Kubernetes
- **Clean separation** of services by workload type
- **No reboots required** when changing categories

**How it works**:
1. Services are defined at the BCM category level
2. When a node changes category, BCM automatically starts/stops services
3. Jobstats services are tied to the Slurm category
4. Kubernetes nodes automatically stop jobstats services
5. Slurm nodes automatically start jobstats services

```json
{
  "cluster_name": "slurm",
  "prometheus_server": "prometheus-server",
  "grafana_server": "grafana-server",
  "prometheus_port": 9090,
  "grafana_port": 3000,
  "node_exporter_port": 9100,
  "cgroup_exporter_port": 9306,
  "nvidia_gpu_exporter_port": 9445,
  "prometheus_retention_days": 365,
  "systems": {
    "slurm_controller": ["slurm-controller-01"],
    "login_nodes": ["login-node-01", "login-node-02"],
    "dgx_nodes": ["dgx-node-01", "dgx-node-02"],
    "prometheus_server": ["monitoring-server"],
    "grafana_server": ["monitoring-server"]
  }
}
```

## System Roles

### Slurm Controller
- Installs jobstats prolog/epilog scripts using BCM symlink pattern
- Configures BCM-managed Slurm settings
- Deploys slurmctld epilog for job summaries

### Login Nodes
- Installs jobstats command-line tool
- Configures Python dependencies
- Sets up Prometheus connection

### DGX Compute Nodes
- Builds and installs exporters (cgroup, nvidia-gpu, node)
- Creates systemd services
- Configures firewall rules

### Prometheus Server
- Downloads and installs Prometheus
- Creates configuration with DGX node targets
- Sets up systemd service

### Grafana Server
- Installs Grafana via package manager
- Configures Prometheus data source
- Starts web interface

## BCM Integration

The deployment script follows BCM best practices:

- **Script Management**: Uses symlinks from `/cm/local/apps/slurm/var/prologs/` to `/cm/shared/apps/slurm/var/cm/`
- **Configuration Verification**: Uses `cmsh` to verify current BCM settings
- **Service Management**: Respects BCM's service management patterns
- **Cluster Detection**: Automatically detects cluster name from BCM
- **Node Imaging**: Compatible with BCM's `grabimage` process for deploying to multiple nodes

### BCM Node Imaging Workflow

For BCM-managed systems, deploy jobstats on one representative node of each type, then capture and deploy the image:

#### 1. Deploy on Representative Nodes
```bash
# Deploy on one DGX node
uv run python automation/deploy_jobstats.py --config config.json

# Deploy on one Slurm controller  
uv run python automation/deploy_jobstats.py --config config.json

# Deploy on one login node
uv run python automation/deploy_jobstats.py --config config.json
```

#### 2. Capture Images
```bash
# Capture DGX node image
cmsh -c "device;use dgx-node-01;grabimage -w"

# Capture Slurm controller image
cmsh -c "device;use slurm-controller-01;grabimage -w"

# Capture login node image
cmsh -c "device;use login-node-01;grabimage -w"
```

#### 3. Deploy to All Nodes
BCM will automatically deploy the captured images to all nodes of the same type.

**Important**: All jobstats files are safe for BCM imaging - no exclude list modifications are needed.

## Usage Examples

### Dry Run
```bash
uv run python automation/deploy_jobstats.py --config config.json --dry-run
```
This creates a `dry-run-output.txt` file with all commands that would be executed.

### Custom Configuration
```bash
uv run python automation/deploy_jobstats.py --config my_cluster_config.json
```

### Using Example Configurations
```bash
# For shared host environments
uv run python automation/deploy_jobstats.py --config config-shared-hosts.json

# For existing monitoring infrastructure
uv run python automation/deploy_jobstats.py --config config-existing-monitoring.json

# For BCM category management
uv run python automation/deploy_jobstats.py --config config-category-management.json
```

## Development

### Setup Development Environment
```bash
uv sync --extra dev
```

### Run Tests
```bash
uv run pytest
```

### Code Formatting
```bash
uv run black automation/deploy_jobstats.py
uv run flake8 automation/deploy_jobstats.py
```

## Manual Configuration for Existing Installations

When using existing Prometheus and/or Grafana installations, the script will provide detailed configuration guidance instead of installing new software.

### Existing Prometheus Configuration

The script will output a configuration block to add to your existing `prometheus.yml`:

```yaml
# Add this job to your existing prometheus.yml scrape_configs:
  - job_name: 'jobstats-dgx-nodes'
    scrape_interval: 30s
    scrape_timeout: 30s
    static_configs:
      - targets: 
        - 'dgx-node-01:9100'  # node_exporter
        - 'dgx-node-01:9306'  # cgroup_exporter
        - 'dgx-node-01:9445'  # nvidia_gpu_exporter
        - 'dgx-node-02:9100'  # node_exporter
        - 'dgx-node-02:9306'  # cgroup_exporter
        - 'dgx-node-02:9445'  # nvidia_gpu_exporter
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: '^go_.*'
        action: drop
      - source_labels: [__name__]
        regex: '^slurm_.*'
        target_label: 'cluster'
        replacement: 'slurm'
```

**Steps:**
1. Add the configuration to your existing `prometheus.yml`
2. Reload Prometheus: `curl -X POST http://localhost:9090/-/reload`
3. Verify targets: http://localhost:9090/targets

### Existing Grafana Configuration

**Add Prometheus Data Source:**
- URL: `http://your-prometheus-server:9090`
- Access: Server (default)
- Basic Auth: Disabled (unless required)
- Skip TLS Verify: Yes (unless using HTTPS)

**Import Dashboards:**
- Dashboard ID: 1860 (Node Exporter Full)
- Dashboard ID: 1443 (NVIDIA GPU Metrics)
- Or create custom dashboards using jobstats metrics

**Key Metrics to Monitor:**
- `slurm_job_*` (job statistics)
- `nvidia_*` (GPU metrics)
- `node_*` (system metrics)
- `cgroup_*` (resource usage)

## Troubleshooting

### Common Issues

1. **SSH Access**: Ensure passwordless SSH is configured to all target systems
2. **BCM Access**: Verify `cmsh` is available and you have appropriate permissions
3. **Repository Access**: Ensure internet access for cloning GitHub repositories
4. **Permissions**: Run from BCM head node with administrative access
5. **Existing Installations**: Ensure you have admin access to configure existing Prometheus/Grafana

### Verification Commands

```bash
# Check BCM configuration
cmsh -c "wlm;get prolog;get epilog;get epilogslurmctld"

# Verify script symlinks
ls -la /cm/local/apps/slurm/var/prologs/
ls -la /cm/local/apps/slurm/var/epilogs/

# Check exporter services
systemctl status cgroup_exporter node_exporter nvidia_gpu_prometheus_exporter

# Test Prometheus targets
curl -s http://prometheus-server:9090/api/v1/targets
```

## Architecture

The deployment creates a comprehensive monitoring stack:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   BCM Head      │    │ Slurm Controller│    │   Login Nodes   │
│                 │    │                 │    │                 │
│ - No components │    │ - Prolog/Epilog │    │ - jobstats cmd  │
│ - BCM mgmt only │    │ - BCM scripts   │    │ - Python deps   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   DGX Nodes     │    │ Prometheus      │    │   Grafana       │
│                 │    │                 │    │                 │
│ - Exporters     │    │ - Time series   │    │ - Web interface │
│ - Systemd svcs  │    │ - Scraping      │    │ - Dashboards    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## License

This project is part of the BCM jobstats deployment for NVIDIA DGX systems.

## Support

For issues specific to this deployment:
1. Check the dry-run output for command preview
2. Verify BCM configuration with `cmsh`
3. Test individual components (exporters, Prometheus, Grafana)
4. Consult the original Princeton jobstats documentation
