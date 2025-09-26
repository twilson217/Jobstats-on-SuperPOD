# BCM Jobstats Deployment Automation

This project provides automated deployment of Princeton University's jobstats monitoring platform on BCM-managed DGX systems.

## Features

- **BCM Integration**: Uses `cmsh` to verify configurations and follows BCM best practices
- **Symlink Pattern**: Implements BCM's shared storage symlink pattern for script management
- **Shared Host Support**: Intelligently handles shared systems (e.g., same node for Slurm controller and login)
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

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and setup the project**:
   ```bash
   git clone <repository-url>
   cd jobstats-on-superpod
   uv sync
   ```

3. **Configure your systems**:
   ```bash
   cp config.json.template config.json
   # Edit config.json with your actual system hostnames
   ```

4. **Run a dry-run to preview commands**:
   ```bash
   uv run python deploy_jobstats.py --dry-run
   ```

5. **Deploy jobstats**:
   ```bash
   uv run python deploy_jobstats.py --config config.json
   ```

## Configuration

The `config.json` file defines your cluster topology and settings:

### Shared Host Support

The deployment script intelligently handles shared hosts (common in lab environments):
- **Same host for multiple roles**: Automatically detects and deploys all required components
- **Dependency optimization**: Avoids duplicate package installations
- **Role-based deployment**: Each role's components are deployed in the correct order

### Lab Environment Example

For lab environments where the Slurm controller and login node are the same, and Prometheus and Grafana share a server:

```json
{
  "cluster_name": "slurm",
  "prometheus_server": "lab-monitoring",
  "grafana_server": "lab-monitoring",
  "systems": {
    "slurm_controller": ["lab-slurm-controller"],
    "login_nodes": ["lab-slurm-controller"],
    "dgx_nodes": ["dgx-node-01", "dgx-node-02"],
    "prometheus_server": ["lab-monitoring"],
    "grafana_server": ["lab-monitoring"]
  }
}
```

This configuration will:
- Deploy both Slurm controller and login node components on `lab-slurm-controller`
- Deploy both Prometheus and Grafana on `lab-monitoring`
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

## Usage Examples

### Dry Run
```bash
uv run python deploy_jobstats.py --dry-run
```
This creates a `dry-run-output.txt` file with all commands that would be executed.

### Custom Configuration
```bash
uv run python deploy_jobstats.py --config my_cluster_config.json
```

### Default Configuration
```bash
uv run python deploy_jobstats.py
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
uv run black deploy_jobstats.py
uv run flake8 deploy_jobstats.py
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
