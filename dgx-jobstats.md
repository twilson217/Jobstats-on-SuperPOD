# DGX Jobstats Deployment Guide

This document provides step-by-step instructions for deploying Princeton University's jobstats monitoring platform on a DGX system managed by BCM (Base Command Manager).

## Overview

Jobstats is a comprehensive job monitoring platform designed for CPU and GPU clusters using Slurm. It provides:
- Real-time job utilization metrics
- GPU and CPU performance monitoring
- Automated efficiency reports
- Web-based dashboards via Grafana
- Command-line tools for job analysis

**BCM Integration**: This deployment guide is specifically tailored for NVIDIA Base Command Manager (BCM) environments, leveraging BCM's built-in Slurm management, cgroup support, and configuration overlay system for seamless integration.

## Architecture

The jobstats platform consists of several components distributed across different systems in production:

### Production System Architecture

**BCM Head Node:**
- BCM cluster management (no jobstats components required)

**Slurm Controller Node:**
- Slurm controller and accounting database
- Slurm prolog/epilog scripts for job tracking

**Slurm Login Nodes:**
- jobstats command-line tool (where users run job analysis)
- Python dependencies for jobstats

**DGX Compute Nodes (workload nodes):**
- cgroup_exporter (collects CPU job metrics from /slurm cgroup filesystem)
- nvidia_gpu_prometheus_exporter (collects GPU metrics via nvidia-smi)
- prometheus node_exporter (collects system metrics)

**Prometheus Server:**
- Prometheus time-series database
- Scrapes metrics from all DGX nodes
- May be co-located with Grafana server

**Grafana Server:**
- Web interface for visualization and dashboards
- May be co-located with Prometheus server

### Component Distribution

| Component | BCM Head | Slurm Controller | Login Nodes | DGX Nodes | Prometheus Server | Grafana Server |
|-----------|----------|------------------|-------------|-----------|-------------------|----------------|
| cgroup_exporter | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| nvidia_gpu_exporter | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| node_exporter | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| prometheus | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| grafana | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| jobstats command | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| slurm prolog/epilog | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |

## Prerequisites

- DGX system with BCM management
- Slurm workload manager with cgroup support
- NVIDIA GPUs with nvidia-smi
- Go compiler (for building exporters)
- Python 3.6+ with requests and blessed libraries
- Git (for cloning repositories)
- Internet access (for downloading components)

## Obtaining Required Components

Before deployment, you need to obtain the following components from their respective repositories:

### 1. Clone Required Repositories

**Create a working directory and clone all repositories:**
```bash
# Create working directory
mkdir -p /opt/jobstats-deployment
cd /opt/jobstats-deployment

# Clone Princeton Jobstats (main monitoring platform)
git clone https://github.com/PrincetonUniversity/jobstats.git

# Clone Cgroup Exporter (CPU job metrics)
git clone https://github.com/PrincetonUniversity/cgroup_exporter.git

# Clone NVIDIA GPU Prometheus Exporter (GPU metrics)
git clone https://github.com/PrincetonUniversity/nvidia_gpu_prometheus_exporter.git

# Clone Prometheus Node Exporter (system metrics)
git clone https://github.com/prometheus/node_exporter.git
```

### 2. Verify Repository Contents

**Check that all repositories were cloned successfully:**
```bash
# List all cloned repositories
ls -la /opt/jobstats-deployment/

# Verify key files exist
ls -la /opt/jobstats-deployment/jobstats/jobstats/slurm/
ls -la /opt/jobstats-deployment/cgroup_exporter/
ls -la /opt/jobstats-deployment/nvidia_gpu_prometheus_exporter/
ls -la /opt/jobstats-deployment/node_exporter/
```

### 3. Component Overview

| Component | Repository | Purpose | Used On |
|-----------|------------|---------|---------|
| **jobstats** | PrincetonUniversity/jobstats | Main monitoring platform, prolog/epilog scripts, command-line tool | Slurm Controller, Login Nodes |
| **cgroup_exporter** | PrincetonUniversity/cgroup_exporter | Collects CPU job metrics from cgroups | DGX Compute Nodes |
| **nvidia_gpu_prometheus_exporter** | PrincetonUniversity/nvidia_gpu_prometheus_exporter | Collects GPU metrics via nvidia-smi | DGX Compute Nodes |
| **node_exporter** | prometheus/node_exporter | Collects system metrics | DGX Compute Nodes |

### 4. Repository Distribution

**IMPORTANT**: The repositories need to be available on the systems where they will be used:

- **Slurm Controller Node**: Needs `jobstats` repository for prolog/epilog scripts
- **Login Nodes**: Needs `jobstats` repository for command-line tool
- **DGX Compute Nodes**: Needs all exporter repositories for building binaries
- **Prometheus Server**: No repositories needed (uses pre-built binaries)

**Options for making repositories available:**
1. **Clone on each system**: Run the git clone commands on each system that needs the repositories
2. **Shared storage**: Clone to shared storage (e.g., `/cm/shared/`) accessible by all nodes
3. **Copy from head node**: Clone on head node, then copy to other systems as needed

**Recommended approach**: Clone repositories on each system that needs them, as this ensures each system has the latest code and doesn't depend on shared storage availability.

## Production Deployment by System

### Prerequisites

Before deployment, ensure the following are available:
- BCM-managed DGX cluster with Slurm
- Network connectivity between all systems
- Go compiler on systems building exporters
- Python 3.6+ on login nodes for jobstats command
- Administrative access to all target systems
- All required repositories cloned to `/opt/jobstats-deployment/`

### 1. BCM Head Node

**No jobstats components required.** This system only manages the cluster through BCM.

### 2. Slurm Controller Node

**Components to install:**
- Slurm prolog/epilog scripts for job tracking (BCM-managed)

#### 2.1 Install Slurm Integration Scripts (BCM Method)

**IMPORTANT**: BCM uses a generic prolog/epilog system that automatically calls all scripts in `/cm/local/apps/slurm/var/prologs/` and `/cm/local/apps/slurm/var/epilogs/`. We need to preserve existing scripts and add jobstats scripts.

**Step 1: Check Current BCM Configuration**
```bash
# Check current BCM prolog/epilog settings
cmsh -c "wlm;get prolog;get epilog;get epilogslurmctld"

# Check existing scripts in BCM directories
ls -la /cm/local/apps/slurm/var/prologs/
ls -la /cm/local/apps/slurm/var/epilogs/
```

**Step 2: Create BCM-Compatible Directories (if needed)**
```bash
# Create BCM-compatible prolog/epilog directories (if they don't exist)
mkdir -p /cm/local/apps/slurm/var/prologs
mkdir -p /cm/local/apps/slurm/var/epilogs
```

**Step 3: Install Jobstats Scripts Using BCM Symlink Pattern**
```bash
# Create shared storage directory for jobstats scripts (following BCM pattern)
mkdir -p /cm/shared/apps/slurm/var/cm

# Copy GPU tracking scripts to shared storage (following Enroot pattern)
cp /opt/jobstats-deployment/jobstats/jobstats/slurm/prolog.d/gpustats_helper.sh /cm/shared/apps/slurm/var/cm/prolog-jobstats.sh
cp /opt/jobstats-deployment/jobstats/jobstats/slurm/epilog.d/gpustats_helper.sh /cm/shared/apps/slurm/var/cm/epilog-jobstats.sh
chmod +x /cm/shared/apps/slurm/var/cm/prolog-jobstats.sh
chmod +x /cm/shared/apps/slurm/var/cm/epilog-jobstats.sh

# Create symlinks in BCM prolog/epilog directories (following Enroot pattern)
# Use 60- prefix to run after existing BCM scripts (like 50-prolog-enroot.sh)
ln -sf /cm/shared/apps/slurm/var/cm/prolog-jobstats.sh /cm/local/apps/slurm/var/prologs/60-prolog-jobstats.sh
ln -sf /cm/shared/apps/slurm/var/cm/epilog-jobstats.sh /cm/local/apps/slurm/var/epilogs/60-epilog-jobstats.sh

# Copy job summary script for slurmctld
cp /opt/jobstats-deployment/jobstats/jobstats/slurm/slurmctldepilog.sh /usr/local/sbin/
chmod +x /usr/local/sbin/slurmctldepilog.sh
```

**Step 4: Verify Script Integration**
```bash
# Verify symlinks are created correctly
ls -la /cm/local/apps/slurm/var/prologs/
ls -la /cm/local/apps/slurm/var/epilogs/

# Verify shared storage scripts exist and are executable
ls -la /cm/shared/apps/slurm/var/cm/prolog-jobstats.sh
ls -la /cm/shared/apps/slurm/var/cm/epilog-jobstats.sh

# Test script execution (optional)
/cm/shared/apps/slurm/var/cm/prolog-jobstats.sh --help
/cm/shared/apps/slurm/var/cm/epilog-jobstats.sh --help
```

#### 2.2 Configure Slurm via BCM

**BCM Configuration Method**: BCM already points to the generic prolog/epilog scripts that automatically call all scripts in the prologs/epilogs directories. We only need to configure the slurmctld epilog.

**Option A: Using cmsh (Command Line)**
```bash
# Access BCM cluster management shell
cmsh

# Navigate to Slurm WLM configuration
[basecm10]% wlm
[basecm10->wlm]% use slurm

# Check current configuration (should show generic scripts)
[basecm10->wlm[slurm]]% get prolog
[basecm10->wlm[slurm]]% get epilog

# Only configure the slurmctld epilog for job summary
[basecm10->wlm[slurm]]% set epilogslurmctld /usr/local/sbin/slurmctldepilog.sh
[basecm10->wlm[slurm]]% commit
```

**Option B: Using Base View GUI**
1. Open Base View web interface
2. Navigate to Workload Management → Slurm
3. Configure only the EpilogSlurmctld path: `/usr/local/sbin/slurmctldepilog.sh`
4. Apply changes

**Note**: The generic prolog/epilog scripts (`/cm/local/apps/cmd/scripts/prolog` and `/cm/local/apps/cmd/scripts/epilog`) automatically discover and execute all scripts in `/cm/local/apps/slurm/var/prologs/` and `/cm/local/apps/slurm/var/epilogs/` respectively, so no changes are needed to those settings.

**Key BCM Configuration Files:**
- Slurm config: `/cm/shared/apps/slurm/var/etc/<cluster_name>/slurm.conf`
- Cgroup config: `/cm/shared/apps/slurm/var/etc/<cluster_name>/cgroup.conf`
- GRES config: `/cm/shared/apps/slurm/var/etc/<cluster_name>/gres.conf`

### 3. Slurm Login Nodes

**Components to install:**
- jobstats command-line tool
- Python dependencies

#### 3.1 Install Dependencies

```bash
apt install -y python3-requests python3-blessed
```

#### 3.2 Install Jobstats Command

```bash
# Copy jobstats files
cp /opt/jobstats-deployment/jobstats/jobstats/jobstats /usr/local/bin/
cp /opt/jobstats-deployment/jobstats/jobstats/jobstats.py /usr/local/bin/
cp /opt/jobstats-deployment/jobstats/jobstats/output_formatters.py /usr/local/bin/
cp /opt/jobstats-deployment/jobstats/jobstats/config.py /usr/local/bin/
chmod +x /usr/local/bin/jobstats
```

#### 3.3 Configure Jobstats

Update `/usr/local/bin/config.py` to point to your Prometheus server:

```python
# prometheus server address, port, and retention period
PROM_SERVER = "http://prometheus-server:9090"  # Replace with actual hostname/IP
PROM_RETENTION_DAYS = 365
```

### 4. DGX Compute Nodes

**Components to install:**
- cgroup_exporter
- nvidia_gpu_prometheus_exporter  
- prometheus node_exporter

#### 4.1 System Preparation

Ensure the system has:
- ✅ **BCM-managed Slurm with cgroup support** (already configured by BCM)
- ✅ **BCM cgroup configuration** in `/cm/shared/apps/slurm/var/etc/<cluster_name>/cgroup.conf`
- ✅ NVIDIA drivers and nvidia-smi available
- ✅ Go compiler installed

**BCM Cgroup Integration**: BCM automatically configures cgroup support for Slurm. The `cgroup_exporter` will work with BCM's existing cgroup setup without additional configuration.

#### 4.2 Build and Install Exporters

**Cgroup Exporter:**
```bash
cd /opt/jobstats-deployment/cgroup_exporter
go build -o cgroup_exporter
cp cgroup_exporter /usr/local/bin/
```

**Node Exporter:**
```bash
cd /opt/jobstats-deployment/node_exporter
make build
cp node_exporter /usr/local/bin/
```

**NVIDIA GPU Exporter:**
```bash
cd /opt/jobstats-deployment/nvidia_gpu_prometheus_exporter
go build -o nvidia_gpu_prometheus_exporter
cp nvidia_gpu_prometheus_exporter /usr/local/bin/
```

#### 4.3 Create Systemd Services

**Cgroup Exporter Service:** `/etc/systemd/system/cgroup_exporter.service`
```ini
[Unit]
Description=Cgroup Exporter for Jobstats
After=network.target

[Service]
Type=simple
User=prometheus
Group=prometheus
ExecStart=/usr/local/bin/cgroup_exporter --config.paths /slurm --collect.fullslurm --web.listen-address=:9306
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Node Exporter Service:** `/etc/systemd/system/node_exporter.service`
```ini
[Unit]
Description=Node Exporter for Jobstats
After=network.target

[Service]
Type=simple
User=prometheus
Group=prometheus
ExecStart=/usr/local/bin/node_exporter --web.listen-address=:9100
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**NVIDIA GPU Exporter Service:** `/etc/systemd/system/nvidia_gpu_prometheus_exporter.service`
```ini
[Unit]
Description=NVIDIA GPU Prometheus Exporter for Jobstats
After=network.target

[Service]
Type=simple
User=prometheus
Group=prometheus
ExecStart=/usr/local/bin/nvidia_gpu_prometheus_exporter --web.listen-address=:9445
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### 4.4 Enable and Start Services

```bash
# Create prometheus user if it doesn't exist
useradd --no-create-home --shell /bin/false prometheus

# Enable and start all exporters
systemctl daemon-reload
systemctl enable cgroup_exporter node_exporter nvidia_gpu_prometheus_exporter
systemctl start cgroup_exporter node_exporter nvidia_gpu_prometheus_exporter
```

### 5. Prometheus Server

**Components to install:**
- Prometheus time-series database

#### 5.1 Install Prometheus

```bash
# Download and install Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xzf prometheus-2.45.0.linux-amd64.tar.gz
cp prometheus-2.45.0.linux-amd64/prometheus /usr/local/bin/
cp prometheus-2.45.0.linux-amd64/promtool /usr/local/bin/
mkdir -p /etc/prometheus /var/lib/prometheus
```

#### 5.2 Create Prometheus User

```bash
useradd --no-create-home --shell /bin/false prometheus
chown prometheus:prometheus /var/lib/prometheus
```

#### 5.3 Configure Prometheus

Create `/etc/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 30s
  evaluation_interval: 30s
  external_labels:
    monitor: 'jobstats-dgx'

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'dgx-nodes'
    scrape_interval: 30s
    scrape_timeout: 30s
    static_configs:
      # Replace with actual DGX node hostnames/IPs
      - targets: 
        - 'dgx-node-01:9100'  # node_exporter
        - 'dgx-node-01:9306'  # cgroup_exporter
        - 'dgx-node-01:9445'  # nvidia_gpu_exporter
        - 'dgx-node-02:9100'
        - 'dgx-node-02:9306'
        - 'dgx-node-02:9445'
        # Add more DGX nodes as needed
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: '^go_.*'
        action: drop
```

#### 5.4 Create Systemd Service

Create `/etc/systemd/system/prometheus.service`:

```ini
[Unit]
Description=Prometheus Server for Jobstats
Documentation=https://prometheus.io/docs/introduction/overview/
Wants=network-online.target
After=network-online.target

[Service]
Type=notify
User=prometheus
Group=prometheus
ExecStart=/usr/local/bin/prometheus \
    --config.file=/etc/prometheus/prometheus.yml \
    --storage.tsdb.path=/var/lib/prometheus/ \
    --web.console.templates=/etc/prometheus/consoles \
    --web.console.libraries=/etc/prometheus/console_libraries \
    --web.listen-address=0.0.0.0:9090 \
    --web.enable-lifecycle

ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### 5.5 Start Prometheus

```bash
chown -R prometheus:prometheus /etc/prometheus /var/lib/prometheus
systemctl daemon-reload
systemctl enable prometheus
systemctl start prometheus
```

### 6. Grafana Server

**Components to install:**
- Grafana web interface

#### 6.1 Install Grafana

```bash
wget -q -O - https://packages.grafana.com/gpg.key | apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" > /etc/apt/sources.list.d/grafana.list
apt update
apt install -y grafana
```

#### 6.2 Configure Grafana

Update `/etc/grafana/grafana.ini` to add Prometheus as a data source:

```ini
[datasources]
datasources.yaml:
  apiVersion: 1
  datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus-server:9090  # Replace with actual Prometheus server
    isDefault: true
```

#### 6.3 Start Grafana

```bash
systemctl enable grafana-server
systemctl start grafana-server
```

**Access Grafana:** http://grafana-server:3000
- Default username: `admin`
- Default password: `admin`

## Network Configuration

### Required Network Connectivity

**Prometheus Server must be able to reach:**
- All DGX nodes on ports 9100, 9306, and 9445
- Grafana server on port 3000 (if co-located, localhost)

**Login Nodes must be able to reach:**
- Prometheus server on port 9090

**Grafana Server must be able to reach:**
- Prometheus server on port 9090

**Users must be able to reach:**
- Grafana server on port 3000

### Firewall Configuration

**DGX Nodes (ports to open):**
```bash
# Allow Prometheus to scrape metrics
ufw allow from <prometheus-server-ip> to any port 9100  # node_exporter
ufw allow from <prometheus-server-ip> to any port 9306  # cgroup_exporter
ufw allow from <prometheus-server-ip> to any port 9445  # nvidia_gpu_exporter
```

**Prometheus Server (ports to open):**
```bash
# Allow Grafana to connect
ufw allow from <grafana-server-ip> to any port 9090
# Allow login nodes to query
ufw allow from <login-node-subnet> to any port 9090
```

**Grafana Server (ports to open):**
```bash
# Allow users to access web interface
ufw allow 3000
```

### Service Management

All services are managed via systemd:

```bash
# Check status of all services
systemctl status cgroup_exporter node_exporter nvidia_gpu_prometheus_exporter prometheus grafana-server

# Restart services if needed
systemctl restart cgroup_exporter node_exporter nvidia_gpu_prometheus_exporter prometheus grafana-server

# View logs
journalctl -u cgroup_exporter -f
journalctl -u node_exporter -f
journalctl -u nvidia_gpu_prometheus_exporter -f
journalctl -u prometheus -f
journalctl -u grafana-server -f
```

## Deployment Summary

### System-by-System Checklist

**BCM Head Node:**
- ✅ No jobstats components required

**Slurm Controller Node:**
- [ ] Install prolog/epilog scripts
- [ ] Configure BCM-managed Slurm settings
- [ ] Install job summary script

**Slurm Login Nodes:**
- [ ] Install Python dependencies
- [ ] Install jobstats command files
- [ ] Configure jobstats to point to Prometheus server

**DGX Compute Nodes:**
- [ ] Build and install cgroup_exporter
- [ ] Build and install nvidia_gpu_prometheus_exporter
- [ ] Build and install node_exporter
- [ ] Create and enable systemd services
- [ ] Configure firewall rules

**Prometheus Server:**
- [ ] Install Prometheus binary
- [ ] Create prometheus user
- [ ] Configure prometheus.yml with DGX node targets
- [ ] Create and enable systemd service
- [ ] Configure firewall rules

**Grafana Server:**
- [ ] Install Grafana
- [ ] Configure Prometheus data source
- [ ] Start Grafana service
- [ ] Configure firewall rules

## Verification

### 1. Check Exporter Endpoints on DGX Nodes
```bash
# Node exporter
curl http://dgx-node-01:9100/metrics | head -5

# Cgroup exporter
curl http://dgx-node-01:9306/metrics | head -5

# NVIDIA GPU exporter
curl http://dgx-node-01:9445/metrics | head -5
```

### 2. Check Prometheus Targets
```bash
curl -s http://prometheus-server:9090/api/v1/targets | jq '.data.activeTargets[].health'
```

### 3. Test Jobstats Command on Login Nodes
```bash
jobstats --help
```

### 4. Access Web Interfaces
- **Prometheus**: http://prometheus-server:9090
- **Grafana**: http://grafana-server:3000 (admin/admin)

## Port Configuration

| Service | Port | Description | Required On |
|---------|------|-------------|-------------|
| node_exporter | 9100 | System metrics | DGX nodes only |
| cgroup_exporter | 9306 | CPU job metrics | DGX nodes only |
| nvidia_gpu_prometheus_exporter | 9445 | GPU metrics | DGX nodes only |
| prometheus | 9090 | Metrics database | Prometheus server |
| grafana | 3000 | Web dashboard | Grafana server |

## Lab vs Production Differences

**Lab Environment (Single System):**
- All components installed on one DGX system (dgx-01)
- All services use localhost for communication
- Simplified deployment for testing and development

**Production Environment (Distributed Systems):**
- Components distributed across multiple systems
- Network communication between systems
- Firewall configuration required
- Hostname/IP configuration for inter-system communication
- BCM-managed Slurm configuration changes

## BCM-Specific Considerations

### Configuration Management
- **Slurm Configuration**: Managed by BCM in `/cm/shared/apps/slurm/var/etc/<cluster_name>/`
- **Key Files**:
  - `slurm.conf` - Main Slurm configuration (AUTOGENERATED section cannot be edited directly)
  - `cgroup.conf` - Cgroup configuration for resource management
  - `gres.conf` - GPU resource configuration
  - `topology.conf` - Network topology configuration
- **Configuration Changes**: Must be made through BCM tools (`cmsh` or Base View GUI)
- **Prolog/Epilog Management**: BCM automatically manages script execution and `slurm.conf` parameters

### BCM Prolog/Epilog Script System
- **Script Locations**:
  - Generic scripts: `/cm/local/apps/cmd/scripts/prolog` and `/cm/local/apps/cmd/scripts/epilog`
  - Slurm-specific: `/cm/local/apps/slurm/var/prologs/` and `/cm/local/apps/slurm/var/epilogs/`
- **Script Naming Convention**:
  - Numerical prefixes (00-99) determine execution order
  - Special suffixes: `-prejob` (runs before all jobs), `-cmjob` (runs for cloud jobs)
- **BCM Best Practice**: Use symlinks from local directories to shared storage scripts
  - **Shared Storage**: `/cm/shared/apps/slurm/var/cm/` (accessible to all nodes)
  - **Local Symlinks**: `/cm/local/apps/slurm/var/prologs/` and `/cm/local/apps/slurm/var/epilogs/`
  - **Benefits**: Centralized management, consistent across all nodes, follows BCM patterns

### User Management
- System uses nslcd/slapd for user authentication
- Local system accounts created for service users
- Prometheus user already existed in the system

### File Locations
- **BCM Shared**: `/cm/shared/apps/slurm/var/etc/<cluster_name>/`
- **BCM Local**: `/cm/local/apps/slurm/var/`
- **Service configs**: `/etc/systemd/system/`
- **Prometheus data**: `/var/lib/prometheus/`
- **Grafana data**: `/var/lib/grafana/`

## BCM-Specific Deployment Notes

### BCM Configuration Verification

**Check BCM Slurm Configuration:**
```bash
# Verify BCM-managed Slurm configuration
cmsh
[basecm10]% wlm
[basecm10->wlm]% use slurm
[basecm10->wlm[slurm]]% show | grep -E "(prolog|epilog)"

# Check if prolog/epilog scripts are properly configured
ls -la /cm/local/apps/slurm/var/prologs/
ls -la /cm/local/apps/slurm/var/epilogs/

# Verify script execution order (scripts run in numerical order)
ls -la /cm/local/apps/slurm/var/prologs/ | sort -k9
ls -la /cm/local/apps/slurm/var/epilogs/ | sort -k9
```

**Verify BCM Generic Script Integration:**
```bash
# Check that BCM generic scripts are configured
cmsh -c "wlm;get prolog;get epilog;get epilogslurmctld"

# Expected output:
# /cm/local/apps/cmd/scripts/prolog
# /cm/local/apps/cmd/scripts/epilog
# /usr/local/sbin/slurmctldepilog.sh (after jobstats installation)
```

**Verify BCM Cgroup Configuration:**
```bash
# Check BCM cgroup configuration
cat /cm/shared/apps/slurm/var/etc/<cluster_name>/cgroup.conf

# Verify cgroup mount points
mount | grep cgroup
```

### BCM Script Execution Order and Preservation

**Script Execution Order**: BCM executes prolog/epilog scripts in numerical order based on filename prefixes:
- Scripts with lower numbers (e.g., `10-`, `20-`) run first
- Scripts with higher numbers (e.g., `50-`, `60-`) run later
- Jobstats scripts use `60-` prefix to run after existing BCM scripts

**Preserving Existing Scripts**: The BCM generic prolog/epilog system automatically discovers and executes ALL scripts in the directories:
- Existing scripts (like `50-prolog-enroot.sh`) continue to run
- Jobstats scripts (`60-prolog-jobstats.sh`, `60-epilog-jobstats.sh`) are added without affecting existing functionality
- No existing BCM functionality is lost

**Symlink Benefits**: Following BCM's symlink pattern provides several advantages:
- **Centralized Management**: Scripts stored in `/cm/shared/` are accessible from all nodes
- **Consistency**: Same script version runs on all nodes automatically
- **Easy Updates**: Modify script once in shared storage, changes apply everywhere
- **BCM Compliance**: Follows established BCM patterns (like Enroot integration)

**Script Dependencies**: If jobstats scripts depend on output from other scripts, ensure proper naming order:
- Use lower numbers for dependencies (e.g., `40-` for prerequisites)
- Use higher numbers for jobstats (e.g., `60-` for jobstats scripts)

### BCM Service Management

**BCM automatically manages Slurm services**, so avoid manual service management:
- Do not use `systemctl restart slurm` directly
- Use BCM commands: `cmsh` → `wlm` → `slurm` → `restart`
- BCM handles service dependencies and configuration validation

## Troubleshooting

### Common Issues

1. **Exporters not starting**
   - Check if ports are already in use: `netstat -tlnp | grep -E "(9100|9306|9445)"`
   - Verify user permissions: `ls -la /usr/local/bin/*exporter`

2. **Prometheus not scraping targets**
   - Check configuration: `promtool check config /etc/prometheus/prometheus.yml`
   - Verify targets are accessible: `curl http://localhost:9100/metrics`

3. **Grafana not accessible**
   - Check service status: `systemctl status grafana-server`
   - Verify port binding: `netstat -tlnp | grep 3000`

4. **Jobstats command errors**
   - Check Python dependencies: `python3 -c "import requests, blessed"`
   - Verify config file: `python3 -c "import config"`

5. **BCM-Specific Issues**
   - **Prolog/Epilog not executing**: 
     - Check BCM script naming convention and permissions
     - Verify symlinks exist in `/cm/local/apps/slurm/var/prologs/` and `/cm/local/apps/slurm/var/epilogs/`
     - Verify target scripts exist in `/cm/shared/apps/slurm/var/cm/` and are executable
     - Check symlink targets: `ls -la /cm/local/apps/slurm/var/prologs/60-prolog-jobstats.sh`
     - Check BCM generic script configuration: `cmsh -c "wlm;get prolog;get epilog"`
   - **Script execution order issues**:
     - Verify script naming follows numerical order (e.g., `60-prolog-jobstats.sh`)
     - Check that existing BCM scripts are not being overridden
   - **Slurm configuration not updating**: Use BCM tools instead of direct file editing
   - **Cgroup issues**: Verify BCM cgroup configuration in `/cm/shared/apps/slurm/var/etc/<cluster_name>/cgroup.conf`

### Log Locations
- Systemd logs: `journalctl -u <service-name>`
- Prometheus logs: `journalctl -u prometheus`
- Grafana logs: `/var/log/grafana/grafana.log`
- **BCM logs**: `/var/log/cm/` (CMDaemon logs)
- **Slurm logs**: `/cm/shared/apps/slurm/var/log/` (BCM-managed Slurm logs)

## Next Steps

1. **Clone Required Repositories**: 
   - Clone all required repositories to `/opt/jobstats-deployment/` on each system that needs them
   - Verify repository contents and file structure
2. **Configure BCM Slurm Settings**: 
   - Use `cmsh` or Base View GUI to configure prolog/epilog paths
   - Verify BCM cgroup configuration is compatible with jobstats
3. **Deploy Scripts to BCM Structure**: 
   - Place prolog/epilog scripts in `/cm/local/apps/slurm/var/prologs/` and `/cm/local/apps/slurm/var/epilogs/`
   - Use proper BCM naming convention (e.g., `60-prolog-jobstats.sh`)
   - Follow BCM symlink pattern for shared storage
4. **Import Grafana Dashboard**: Import the jobstats dashboard from the repository
5. **Test with Sample Jobs**: Run test jobs to verify metrics collection and BCM integration
6. **Configure Alerts**: Set up Grafana alerts for job efficiency issues
7. **User Training**: Provide documentation for users on using the jobstats command
8. **BCM Integration Verification**: 
   - Verify BCM service management doesn't conflict with jobstats
   - Test BCM cluster operations with jobstats running

## Additional Resources

- [Princeton Jobstats Repository](https://github.com/PrincetonUniversity/jobstats)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Slurm Cgroup Configuration](https://slurm.schedmd.com/cgroups.html)

## Support

For issues specific to this DGX deployment:
1. Check service logs using `journalctl`
2. Verify BCM configuration changes
3. Test individual components (exporters, Prometheus, Grafana)
4. Consult the original Princeton jobstats documentation

---

**Deployment completed on:** $(date)
**System:** DGX with BCM management
**Slurm Version:** $(sinfo --version)
**NVIDIA Driver:** $(nvidia-smi --query-driver-version --format=csv,noheader)
