# Update documentation for system components
_Exported on 9/26/2025 at 13:49:56 EDT from Cursor (1.6.45)_

---

**User**

our other chat was unresponsive. so i started a new one. I exported our previous chat session to previous-chat.md. we were working on updating the documentation in dgx-jobstats.md.

Here is the prompt I was trying to send:

That's great! Thank you! Since this was a lab environment it is fine that we installed everything on the same system--dgx-01 in this case. However, in production it won't be that way. We will have these all as separate systems:

- BCM head node
- slurm controller (also runs the slurm accounting db)
- slurm login nodes (where the end users run their jobs, and where they will want to run the jobstats command)
- grafana server (may be the same as prometheus, but may be different)
- prometheus server (may be the same as grafana, but may not be also)
- dgx nodes

Some of these components will absolutely need to be on the dgx nodes running the workloads, such as the cgroups exporter, the nvidia exporter, and the prometheus node exporter. However, we don't want to put anything on the dgx nodes running the workloads unless it absolutely needs to be there. Can you please update the documentation to reflect what needs to be done on which system?

---

**Cursor**

I'll help you update the documentation to reflect the production architecture with separate systems. Let me first read the current documentation and the previous chat to understand the context.


Now let me create a todo list to organize the documentation update for the production architecture:


Based on my analysis of the current documentation and your requirements, I need to update the documentation to reflect a production architecture with separate systems. Let me identify which components need to be on which systems:

**Components that MUST be on DGX nodes (workload nodes):**
- cgroup_exporter (needs access to /slurm cgroup filesystem)
- nvidia_gpu_prometheus_exporter (needs access to nvidia-smi)
- prometheus node_exporter (needs access to system metrics)

**Components that can be on other systems:**
- Prometheus server (can be on dedicated server)
- Grafana server (can be on dedicated server or same as Prometheus)
- jobstats command (should be on login nodes where users run jobs)
- Slurm controller and accounting database (on slurm controller)
- BCM head node (management only)

Let me update the documentation:


```markdown
# DGX Jobstats Deployment Guide

This document provides step-by-step instructions for deploying Princeton University's jobstats monitoring platform on a DGX system managed by BCM (Base Command Manager).

## Overview

Jobstats is a comprehensive job monitoring platform designed for CPU and GPU clusters using Slurm. It provides:
- Real-time job utilization metrics
- GPU and CPU performance monitoring
- Automated efficiency reports
- Web-based dashboards via Grafana
- Command-line tools for job analysis

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

## Step-by-Step Deployment

### 1. System Analysis and Preparation

The system was analyzed and found to have:
- ✅ Slurm with cgroup support already configured
- ✅ NVIDIA drivers and nvidia-smi available
- ✅ Go compiler installed
- ✅ BCM-managed configuration in `/cm/shared/apps/slurm/var/etc/slurm/`

**Key Configuration Files:**
- Slurm config: `/cm/shared/apps/slurm/var/etc/slurm/slurm.conf`
- Cgroup config: `/cm/shared/apps/slurm/var/etc/slurm/cgroup.conf`
- GRES config: `/cm/shared/apps/slurm/var/etc/slurm/gres.conf`

### 2. User Management

In BCM-managed environments, user management is handled through nslcd/slapd rather than local `/etc/passwd`. For system services, we created local system accounts:

```bash
# Prometheus user already existed
# Created directories for data storage
mkdir -p /var/lib/prometheus
chown prometheus:prometheus /var/lib/prometheus
```

### 3. Exporters Installation

#### 3.1 Cgroup Exporter
Built and installed the cgroup exporter for CPU job statistics:

```bash
cd /root/jobstats/cgroup_exporter
go build -o cgroup_exporter
cp cgroup_exporter /usr/local/bin/
```

**Systemd Service:** `/etc/systemd/system/cgroup_exporter.service`
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

#### 3.2 Node Exporter
Built and installed the node exporter for system metrics:

```bash
cd /root/jobstats/node_exporter
make build
cp node_exporter /usr/local/bin/
```

**Systemd Service:** `/etc/systemd/system/node_exporter.service`
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

#### 3.3 NVIDIA GPU Exporter
Built and installed the NVIDIA GPU exporter:

```bash
cd /root/jobstats/nvidia_gpu_prometheus_exporter
go build -o nvidia_gpu_prometheus_exporter
cp nvidia_gpu_prometheus_exporter /usr/local/bin/
```

**Systemd Service:** `/etc/systemd/system/nvidia_gpu_prometheus_exporter.service`
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

#### 3.4 Enable and Start Exporters
```bash
systemctl daemon-reload
systemctl enable cgroup_exporter node_exporter nvidia_gpu_prometheus_exporter
systemctl start cgroup_exporter node_exporter nvidia_gpu_prometheus_exporter
```

### 4. Prometheus Installation and Configuration

#### 4.1 Prometheus Configuration
Created `/etc/prometheus/prometheus.yml`:
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

  - job_name: 'dgx-node'
    scrape_interval: 30s
    scrape_timeout: 30s
    static_configs:
      - targets: ['localhost:9100', 'localhost:9306', 'localhost:9445']
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: '^go_.*'
        action: drop
```

#### 4.2 Prometheus Systemd Service
Created `/etc/systemd/system/prometheus.service`:
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

#### 4.3 Start Prometheus
```bash
chown -R prometheus:prometheus /etc/prometheus /var/lib/prometheus
systemctl daemon-reload
systemctl enable prometheus
systemctl start prometheus
```

### 5. Grafana Installation and Configuration

#### 5.1 Install Grafana
```bash
wget -q -O - https://packages.grafana.com/gpg.key | apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" > /etc/apt/sources.list.d/grafana.list
apt update
apt install -y grafana
```

#### 5.2 Start Grafana
```bash
systemctl enable grafana-server
systemctl start grafana-server
```

**Access Grafana:** http://localhost:3000
- Default username: `admin`
- Default password: `admin`

### 6. Jobstats Command Installation

#### 6.1 Install Dependencies
```bash
apt install -y python3-requests python3-blessed
```

#### 6.2 Install Jobstats Files
```bash
cp /root/jobstats/jobstats/jobstats /usr/local/bin/
cp /root/jobstats/jobstats/jobstats.py /usr/local/bin/
cp /root/jobstats/jobstats/output_formatters.py /usr/local/bin/
cp /root/jobstats/jobstats/config.py /usr/local/bin/
chmod +x /usr/local/bin/jobstats
```

#### 6.3 Configure Jobstats
Updated `/usr/local/bin/config.py`:
```python
# prometheus server address, port, and retention period
PROM_SERVER = "http://localhost:9090"
PROM_RETENTION_DAYS = 365
```

### 7. Slurm Integration

#### 7.1 GPU Tracking Scripts
Installed prolog/epilog scripts for GPU job tracking:

```bash
mkdir -p /etc/slurm/prolog.d /etc/slurm/epilog.d
cp /root/jobstats/jobstats/slurm/prolog.d/gpustats_helper.sh /etc/slurm/prolog.d/
cp /root/jobstats/jobstats/slurm/epilog.d/gpustats_helper.sh /etc/slurm/epilog.d/
chmod +x /etc/slurm/prolog.d/gpustats_helper.sh /etc/slurm/epilog.d/gpustats_helper.sh
```

#### 7.2 Slurm Configuration (BCM-Managed)
**REQUIRED BCM CONFIGURATION:** Add these lines to the BCM-managed section of `slurm.conf`:

```
Prolog=/etc/slurm/prolog.d/*.sh
Epilog=/etc/slurm/epilog.d/*.sh
EpilogSlurmctld=/usr/local/sbin/slurmctldepilog.sh
```

#### 7.3 Job Summary Script
```bash
cp /root/jobstats/jobstats/slurm/slurmctldepilog.sh /usr/local/sbin/
chmod +x /usr/local/sbin/slurmctldepilog.sh
```

### 8. Service Management

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

## Verification

### 1. Check Exporter Endpoints
```bash
# Node exporter
curl http://localhost:9100/metrics | head -5

# Cgroup exporter
curl http://localhost:9306/metrics | head -5

# NVIDIA GPU exporter
curl http://localhost:9445/metrics | head -5
```

### 2. Check Prometheus Targets
```bash
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].health'
```

### 3. Test Jobstats Command
```bash
jobstats --help
```

### 4. Access Web Interfaces
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

## Port Configuration

| Service | Port | Description |
|---------|------|-------------|
| node_exporter | 9100 | System metrics |
| cgroup_exporter | 9306 | CPU job metrics |
| nvidia_gpu_prometheus_exporter | 9445 | GPU metrics |
| prometheus | 9090 | Metrics database |
| grafana | 3000 | Web dashboard |

## BCM-Specific Considerations

### Configuration Management
- Slurm configuration is managed by BCM in `/cm/shared/apps/slurm/var/etc/slurm/`
- BCM autogenerated sections cannot be edited directly
- Prolog/epilog settings must be added through BCM interface

### User Management
- System uses nslcd/slapd for user authentication
- Local system accounts created for service users
- Prometheus user already existed in the system

### File Locations
- Slurm configs: `/cm/shared/apps/slurm/var/etc/slurm/`
- Service configs: `/etc/systemd/system/`
- Prometheus data: `/var/lib/prometheus/`
- Grafana data: `/var/lib/grafana/`

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

### Log Locations
- Systemd logs: `journalctl -u <service-name>`
- Prometheus logs: `journalctl -u prometheus`
- Grafana logs: `/var/log/grafana/grafana.log`

## Next Steps

1. **Configure BCM**: Add the required Slurm prolog/epilog settings through BCM
2. **Import Grafana Dashboard**: Import the jobstats dashboard from the repository
3. **Test with Sample Jobs**: Run test jobs to verify metrics collection
4. **Configure Alerts**: Set up Grafana alerts for job efficiency issues
5. **User Training**: Provide documentation for users on using the jobstats command

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

```

Now let me update the deployment steps to be organized by system type:


```markdown
# DGX Jobstats Deployment Guide

This document provides step-by-step instructions for deploying Princeton University's jobstats monitoring platform on a DGX system managed by BCM (Base Command Manager).

## Overview

Jobstats is a comprehensive job monitoring platform designed for CPU and GPU clusters using Slurm. It provides:
- Real-time job utilization metrics
- GPU and CPU performance monitoring
- Automated efficiency reports
- Web-based dashboards via Grafana
- Command-line tools for job analysis

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

## Production Deployment by System

### Prerequisites

Before deployment, ensure the following are available:
- BCM-managed DGX cluster with Slurm
- Network connectivity between all systems
- Go compiler on systems building exporters
- Python 3.6+ on login nodes for jobstats command
- Administrative access to all target systems

### 1. BCM Head Node

**No jobstats components required.** This system only manages the cluster through BCM.

### 2. Slurm Controller Node

**Components to install:**
- Slurm prolog/epilog scripts for job tracking

#### 2.1 Install Slurm Integration Scripts

```bash
# Create prolog/epilog directories
mkdir -p /etc/slurm/prolog.d /etc/slurm/epilog.d

# Copy GPU tracking scripts
cp /path/to/jobstats/jobstats/slurm/prolog.d/gpustats_helper.sh /etc/slurm/prolog.d/
cp /path/to/jobstats/jobstats/slurm/epilog.d/gpustats_helper.sh /etc/slurm/epilog.d/
chmod +x /etc/slurm/prolog.d/gpustats_helper.sh /etc/slurm/epilog.d/gpustats_helper.sh

# Copy job summary script
cp /path/to/jobstats/jobstats/slurm/slurmctldepilog.sh /usr/local/sbin/
chmod +x /usr/local/sbin/slurmctldepilog.sh
```

#### 2.2 Configure Slurm (BCM-Managed)

**REQUIRED BCM CONFIGURATION:** Add these lines to the BCM-managed section of `slurm.conf`:

```
Prolog=/etc/slurm/prolog.d/*.sh
Epilog=/etc/slurm/epilog.d/*.sh
EpilogSlurmctld=/usr/local/sbin/slurmctldepilog.sh
```

**Key Configuration Files:**
- Slurm config: `/cm/shared/apps/slurm/var/etc/slurm/slurm.conf`
- Cgroup config: `/cm/shared/apps/slurm/var/etc/slurm/cgroup.conf`
- GRES config: `/cm/shared/apps/slurm/var/etc/slurm/gres.conf`

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
cp /path/to/jobstats/jobstats/jobstats /usr/local/bin/
cp /path/to/jobstats/jobstats/jobstats.py /usr/local/bin/
cp /path/to/jobstats/jobstats/output_formatters.py /usr/local/bin/
cp /path/to/jobstats/jobstats/config.py /usr/local/bin/
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
- ✅ Slurm with cgroup support already configured
- ✅ NVIDIA drivers and nvidia-smi available
- ✅ Go compiler installed

#### 4.2 Build and Install Exporters

**Cgroup Exporter:**
```bash
cd /path/to/cgroup_exporter
go build -o cgroup_exporter
cp cgroup_exporter /usr/local/bin/
```

**Node Exporter:**
```bash
cd /path/to/node_exporter
make build
cp node_exporter /usr/local/bin/
```

**NVIDIA GPU Exporter:**
```bash
cd /path/to/nvidia_gpu_prometheus_exporter
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

### 3. Exporters Installation

#### 3.1 Cgroup Exporter
Built and installed the cgroup exporter for CPU job statistics:

```bash
cd /root/jobstats/cgroup_exporter
go build -o cgroup_exporter
cp cgroup_exporter /usr/local/bin/
```

**Systemd Service:** `/etc/systemd/system/cgroup_exporter.service`
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

#### 3.2 Node Exporter
Built and installed the node exporter for system metrics:

```bash
cd /root/jobstats/node_exporter
make build
cp node_exporter /usr/local/bin/
```

**Systemd Service:** `/etc/systemd/system/node_exporter.service`
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

#### 3.3 NVIDIA GPU Exporter
Built and installed the NVIDIA GPU exporter:

```bash
cd /root/jobstats/nvidia_gpu_prometheus_exporter
go build -o nvidia_gpu_prometheus_exporter
cp nvidia_gpu_prometheus_exporter /usr/local/bin/
```

**Systemd Service:** `/etc/systemd/system/nvidia_gpu_prometheus_exporter.service`
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

#### 3.4 Enable and Start Exporters
```bash
systemctl daemon-reload
systemctl enable cgroup_exporter node_exporter nvidia_gpu_prometheus_exporter
systemctl start cgroup_exporter node_exporter nvidia_gpu_prometheus_exporter
```

### 4. Prometheus Installation and Configuration

#### 4.1 Prometheus Configuration
Created `/etc/prometheus/prometheus.yml`:
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

  - job_name: 'dgx-node'
    scrape_interval: 30s
    scrape_timeout: 30s
    static_configs:
      - targets: ['localhost:9100', 'localhost:9306', 'localhost:9445']
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: '^go_.*'
        action: drop
```

#### 4.2 Prometheus Systemd Service
Created `/etc/systemd/system/prometheus.service`:
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

#### 4.3 Start Prometheus
```bash
chown -R prometheus:prometheus /etc/prometheus /var/lib/prometheus
systemctl daemon-reload
systemctl enable prometheus
systemctl start prometheus
```

### 5. Grafana Installation and Configuration

#### 5.1 Install Grafana
```bash
wget -q -O - https://packages.grafana.com/gpg.key | apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" > /etc/apt/sources.list.d/grafana.list
apt update
apt install -y grafana
```

#### 5.2 Start Grafana
```bash
systemctl enable grafana-server
systemctl start grafana-server
```

**Access Grafana:** http://localhost:3000
- Default username: `admin`
- Default password: `admin`

### 6. Jobstats Command Installation

#### 6.1 Install Dependencies
```bash
apt install -y python3-requests python3-blessed
```

#### 6.2 Install Jobstats Files
```bash
cp /root/jobstats/jobstats/jobstats /usr/local/bin/
cp /root/jobstats/jobstats/jobstats.py /usr/local/bin/
cp /root/jobstats/jobstats/output_formatters.py /usr/local/bin/
cp /root/jobstats/jobstats/config.py /usr/local/bin/
chmod +x /usr/local/bin/jobstats
```

#### 6.3 Configure Jobstats
Updated `/usr/local/bin/config.py`:
```python
# prometheus server address, port, and retention period
PROM_SERVER = "http://localhost:9090"
PROM_RETENTION_DAYS = 365
```

### 7. Slurm Integration

#### 7.1 GPU Tracking Scripts
Installed prolog/epilog scripts for GPU job tracking:

```bash
mkdir -p /etc/slurm/prolog.d /etc/slurm/epilog.d
cp /root/jobstats/jobstats/slurm/prolog.d/gpustats_helper.sh /etc/slurm/prolog.d/
cp /root/jobstats/jobstats/slurm/epilog.d/gpustats_helper.sh /etc/slurm/epilog.d/
chmod +x /etc/slurm/prolog.d/gpustats_helper.sh /etc/slurm/epilog.d/gpustats_helper.sh
```

#### 7.2 Slurm Configuration (BCM-Managed)
**REQUIRED BCM CONFIGURATION:** Add these lines to the BCM-managed section of `slurm.conf`:

```
Prolog=/etc/slurm/prolog.d/*.sh
Epilog=/etc/slurm/epilog.d/*.sh
EpilogSlurmctld=/usr/local/sbin/slurmctldepilog.sh
```

#### 7.3 Job Summary Script
```bash
cp /root/jobstats/jobstats/slurm/slurmctldepilog.sh /usr/local/sbin/
chmod +x /usr/local/sbin/slurmctldepilog.sh
```

### 8. Service Management

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

## Verification

### 1. Check Exporter Endpoints
```bash
# Node exporter
curl http://localhost:9100/metrics | head -5

# Cgroup exporter
curl http://localhost:9306/metrics | head -5

# NVIDIA GPU exporter
curl http://localhost:9445/metrics | head -5
```

### 2. Check Prometheus Targets
```bash
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].health'
```

### 3. Test Jobstats Command
```bash
jobstats --help
```

### 4. Access Web Interfaces
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

## Port Configuration

| Service | Port | Description |
|---------|------|-------------|
| node_exporter | 9100 | System metrics |
| cgroup_exporter | 9306 | CPU job metrics |
| nvidia_gpu_prometheus_exporter | 9445 | GPU metrics |
| prometheus | 9090 | Metrics database |
| grafana | 3000 | Web dashboard |

## BCM-Specific Considerations

### Configuration Management
- Slurm configuration is managed by BCM in `/cm/shared/apps/slurm/var/etc/slurm/`
- BCM autogenerated sections cannot be edited directly
- Prolog/epilog settings must be added through BCM interface

### User Management
- System uses nslcd/slapd for user authentication
- Local system accounts created for service users
- Prometheus user already existed in the system

### File Locations
- Slurm configs: `/cm/shared/apps/slurm/var/etc/slurm/`
- Service configs: `/etc/systemd/system/`
- Prometheus data: `/var/lib/prometheus/`
- Grafana data: `/var/lib/grafana/`

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

### Log Locations
- Systemd logs: `journalctl -u <service-name>`
- Prometheus logs: `journalctl -u prometheus`
- Grafana logs: `/var/log/grafana/grafana.log`

## Next Steps

1. **Configure BCM**: Add the required Slurm prolog/epilog settings through BCM
2. **Import Grafana Dashboard**: Import the jobstats dashboard from the repository
3. **Test with Sample Jobs**: Run test jobs to verify metrics collection
4. **Configure Alerts**: Set up Grafana alerts for job efficiency issues
5. **User Training**: Provide documentation for users on using the jobstats command

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

```

I notice there's some duplicate content that needs to be cleaned up. Let me remove the old deployment sections and add network considerations:


```markdown
# DGX Jobstats Deployment Guide

This document provides step-by-step instructions for deploying Princeton University's jobstats monitoring platform on a DGX system managed by BCM (Base Command Manager).

## Overview

Jobstats is a comprehensive job monitoring platform designed for CPU and GPU clusters using Slurm. It provides:
- Real-time job utilization metrics
- GPU and CPU performance monitoring
- Automated efficiency reports
- Web-based dashboards via Grafana
- Command-line tools for job analysis

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

## Production Deployment by System

### Prerequisites

Before deployment, ensure the following are available:
- BCM-managed DGX cluster with Slurm
- Network connectivity between all systems
- Go compiler on systems building exporters
- Python 3.6+ on login nodes for jobstats command
- Administrative access to all target systems

### 1. BCM Head Node

**No jobstats components required.** This system only manages the cluster through BCM.

### 2. Slurm Controller Node

**Components to install:**
- Slurm prolog/epilog scripts for job tracking

#### 2.1 Install Slurm Integration Scripts

```bash
# Create prolog/epilog directories
mkdir -p /etc/slurm/prolog.d /etc/slurm/epilog.d

# Copy GPU tracking scripts
cp /path/to/jobstats/jobstats/slurm/prolog.d/gpustats_helper.sh /etc/slurm/prolog.d/
cp /path/to/jobstats/jobstats/slurm/epilog.d/gpustats_helper.sh /etc/slurm/epilog.d/
chmod +x /etc/slurm/prolog.d/gpustats_helper.sh /etc/slurm/epilog.d/gpustats_helper.sh

# Copy job summary script
cp /path/to/jobstats/jobstats/slurm/slurmctldepilog.sh /usr/local/sbin/
chmod +x /usr/local/sbin/slurmctldepilog.sh
```

#### 2.2 Configure Slurm (BCM-Managed)

**REQUIRED BCM CONFIGURATION:** Add these lines to the BCM-managed section of `slurm.conf`:

```
Prolog=/etc/slurm/prolog.d/*.sh
Epilog=/etc/slurm/epilog.d/*.sh
EpilogSlurmctld=/usr/local/sbin/slurmctldepilog.sh
```

**Key Configuration Files:**
- Slurm config: `/cm/shared/apps/slurm/var/etc/slurm/slurm.conf`
- Cgroup config: `/cm/shared/apps/slurm/var/etc/slurm/cgroup.conf`
- GRES config: `/cm/shared/apps/slurm/var/etc/slurm/gres.conf`

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
cp /path/to/jobstats/jobstats/jobstats /usr/local/bin/
cp /path/to/jobstats/jobstats/jobstats.py /usr/local/bin/
cp /path/to/jobstats/jobstats/output_formatters.py /usr/local/bin/
cp /path/to/jobstats/jobstats/config.py /usr/local/bin/
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
- ✅ Slurm with cgroup support already configured
- ✅ NVIDIA drivers and nvidia-smi available
- ✅ Go compiler installed

#### 4.2 Build and Install Exporters

**Cgroup Exporter:**
```bash
cd /path/to/cgroup_exporter
go build -o cgroup_exporter
cp cgroup_exporter /usr/local/bin/
```

**Node Exporter:**
```bash
cd /path/to/node_exporter
make build
cp node_exporter /usr/local/bin/
```

**NVIDIA GPU Exporter:**
```bash
cd /path/to/nvidia_gpu_prometheus_exporter
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

## Verification

### 1. Check Exporter Endpoints
```bash
# Node exporter
curl http://localhost:9100/metrics | head -5

# Cgroup exporter
curl http://localhost:9306/metrics | head -5

# NVIDIA GPU exporter
curl http://localhost:9445/metrics | head -5
```

### 2. Check Prometheus Targets
```bash
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].health'
```

### 3. Test Jobstats Command
```bash
jobstats --help
```

### 4. Access Web Interfaces
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

## Port Configuration

| Service | Port | Description |
|---------|------|-------------|
| node_exporter | 9100 | System metrics |
| cgroup_exporter | 9306 | CPU job metrics |
| nvidia_gpu_prometheus_exporter | 9445 | GPU metrics |
| prometheus | 9090 | Metrics database |
| grafana | 3000 | Web dashboard |

## BCM-Specific Considerations

### Configuration Management
- Slurm configuration is managed by BCM in `/cm/shared/apps/slurm/var/etc/slurm/`
- BCM autogenerated sections cannot be edited directly
- Prolog/epilog settings must be added through BCM interface

### User Management
- System uses nslcd/slapd for user authentication
- Local system accounts created for service users
- Prometheus user already existed in the system

### File Locations
- Slurm configs: `/cm/shared/apps/slurm/var/etc/slurm/`
- Service configs: `/etc/systemd/system/`
- Prometheus data: `/var/lib/prometheus/`
- Grafana data: `/var/lib/grafana/`

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

### Log Locations
- Systemd logs: `journalctl -u <service-name>`
- Prometheus logs: `journalctl -u prometheus`
- Grafana logs: `/var/log/grafana/grafana.log`

## Next Steps

1. **Configure BCM**: Add the required Slurm prolog/epilog settings through BCM
2. **Import Grafana Dashboard**: Import the jobstats dashboard from the repository
3. **Test with Sample Jobs**: Run test jobs to verify metrics collection
4. **Configure Alerts**: Set up Grafana alerts for job efficiency issues
5. **User Training**: Provide documentation for users on using the jobstats command

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

```

Now let me update the verification section and add a deployment summary:


```markdown
# DGX Jobstats Deployment Guide

This document provides step-by-step instructions for deploying Princeton University's jobstats monitoring platform on a DGX system managed by BCM (Base Command Manager).

## Overview

Jobstats is a comprehensive job monitoring platform designed for CPU and GPU clusters using Slurm. It provides:
- Real-time job utilization metrics
- GPU and CPU performance monitoring
- Automated efficiency reports
- Web-based dashboards via Grafana
- Command-line tools for job analysis

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

## Production Deployment by System

### Prerequisites

Before deployment, ensure the following are available:
- BCM-managed DGX cluster with Slurm
- Network connectivity between all systems
- Go compiler on systems building exporters
- Python 3.6+ on login nodes for jobstats command
- Administrative access to all target systems

### 1. BCM Head Node

**No jobstats components required.** This system only manages the cluster through BCM.

### 2. Slurm Controller Node

**Components to install:**
- Slurm prolog/epilog scripts for job tracking

#### 2.1 Install Slurm Integration Scripts

```bash
# Create prolog/epilog directories
mkdir -p /etc/slurm/prolog.d /etc/slurm/epilog.d

# Copy GPU tracking scripts
cp /path/to/jobstats/jobstats/slurm/prolog.d/gpustats_helper.sh /etc/slurm/prolog.d/
cp /path/to/jobstats/jobstats/slurm/epilog.d/gpustats_helper.sh /etc/slurm/epilog.d/
chmod +x /etc/slurm/prolog.d/gpustats_helper.sh /etc/slurm/epilog.d/gpustats_helper.sh

# Copy job summary script
cp /path/to/jobstats/jobstats/slurm/slurmctldepilog.sh /usr/local/sbin/
chmod +x /usr/local/sbin/slurmctldepilog.sh
```

#### 2.2 Configure Slurm (BCM-Managed)

**REQUIRED BCM CONFIGURATION:** Add these lines to the BCM-managed section of `slurm.conf`:

```
Prolog=/etc/slurm/prolog.d/*.sh
Epilog=/etc/slurm/epilog.d/*.sh
EpilogSlurmctld=/usr/local/sbin/slurmctldepilog.sh
```

**Key Configuration Files:**
- Slurm config: `/cm/shared/apps/slurm/var/etc/slurm/slurm.conf`
- Cgroup config: `/cm/shared/apps/slurm/var/etc/slurm/cgroup.conf`
- GRES config: `/cm/shared/apps/slurm/var/etc/slurm/gres.conf`

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
cp /path/to/jobstats/jobstats/jobstats /usr/local/bin/
cp /path/to/jobstats/jobstats/jobstats.py /usr/local/bin/
cp /path/to/jobstats/jobstats/output_formatters.py /usr/local/bin/
cp /path/to/jobstats/jobstats/config.py /usr/local/bin/
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
- ✅ Slurm with cgroup support already configured
- ✅ NVIDIA drivers and nvidia-smi available
- ✅ Go compiler installed

#### 4.2 Build and Install Exporters

**Cgroup Exporter:**
```bash
cd /path/to/cgroup_exporter
go build -o cgroup_exporter
cp cgroup_exporter /usr/local/bin/
```

**Node Exporter:**
```bash
cd /path/to/node_exporter
make build
cp node_exporter /usr/local/bin/
```

**NVIDIA GPU Exporter:**
```bash
cd /path/to/nvidia_gpu_prometheus_exporter
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

| Service | Port | Description |
|---------|------|-------------|
| node_exporter | 9100 | System metrics |
| cgroup_exporter | 9306 | CPU job metrics |
| nvidia_gpu_prometheus_exporter | 9445 | GPU metrics |
| prometheus | 9090 | Metrics database |
| grafana | 3000 | Web dashboard |

## BCM-Specific Considerations

### Configuration Management
- Slurm configuration is managed by BCM in `/cm/shared/apps/slurm/var/etc/slurm/`
- BCM autogenerated sections cannot be edited directly
- Prolog/epilog settings must be added through BCM interface

### User Management
- System uses nslcd/slapd for user authentication
- Local system accounts created for service users
- Prometheus user already existed in the system

### File Locations
- Slurm configs: `/cm/shared/apps/slurm/var/etc/slurm/`
- Service configs: `/etc/systemd/system/`
- Prometheus data: `/var/lib/prometheus/`
- Grafana data: `/var/lib/grafana/`

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

### Log Locations
- Systemd logs: `journalctl -u <service-name>`
- Prometheus logs: `journalctl -u prometheus`
- Grafana logs: `/var/log/grafana/grafana.log`

## Next Steps

1. **Configure BCM**: Add the required Slurm prolog/epilog settings through BCM
2. **Import Grafana Dashboard**: Import the jobstats dashboard from the repository
3. **Test with Sample Jobs**: Run test jobs to verify metrics collection
4. **Configure Alerts**: Set up Grafana alerts for job efficiency issues
5. **User Training**: Provide documentation for users on using the jobstats command

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

```

Now let me update the port configuration table and add a note about the lab vs production differences:


```markdown
# DGX Jobstats Deployment Guide

This document provides step-by-step instructions for deploying Princeton University's jobstats monitoring platform on a DGX system managed by BCM (Base Command Manager).

## Overview

Jobstats is a comprehensive job monitoring platform designed for CPU and GPU clusters using Slurm. It provides:
- Real-time job utilization metrics
- GPU and CPU performance monitoring
- Automated efficiency reports
- Web-based dashboards via Grafana
- Command-line tools for job analysis

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

## Production Deployment by System

### Prerequisites

Before deployment, ensure the following are available:
- BCM-managed DGX cluster with Slurm
- Network connectivity between all systems
- Go compiler on systems building exporters
- Python 3.6+ on login nodes for jobstats command
- Administrative access to all target systems

### 1. BCM Head Node

**No jobstats components required.** This system only manages the cluster through BCM.

### 2. Slurm Controller Node

**Components to install:**
- Slurm prolog/epilog scripts for job tracking

#### 2.1 Install Slurm Integration Scripts

```bash
# Create prolog/epilog directories
mkdir -p /etc/slurm/prolog.d /etc/slurm/epilog.d

# Copy GPU tracking scripts
cp /path/to/jobstats/jobstats/slurm/prolog.d/gpustats_helper.sh /etc/slurm/prolog.d/
cp /path/to/jobstats/jobstats/slurm/epilog.d/gpustats_helper.sh /etc/slurm/epilog.d/
chmod +x /etc/slurm/prolog.d/gpustats_helper.sh /etc/slurm/epilog.d/gpustats_helper.sh

# Copy job summary script
cp /path/to/jobstats/jobstats/slurm/slurmctldepilog.sh /usr/local/sbin/
chmod +x /usr/local/sbin/slurmctldepilog.sh
```

#### 2.2 Configure Slurm (BCM-Managed)

**REQUIRED BCM CONFIGURATION:** Add these lines to the BCM-managed section of `slurm.conf`:

```
Prolog=/etc/slurm/prolog.d/*.sh
Epilog=/etc/slurm/epilog.d/*.sh
EpilogSlurmctld=/usr/local/sbin/slurmctldepilog.sh
```

**Key Configuration Files:**
- Slurm config: `/cm/shared/apps/slurm/var/etc/slurm/slurm.conf`
- Cgroup config: `/cm/shared/apps/slurm/var/etc/slurm/cgroup.conf`
- GRES config: `/cm/shared/apps/slurm/var/etc/slurm/gres.conf`

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
cp /path/to/jobstats/jobstats/jobstats /usr/local/bin/
cp /path/to/jobstats/jobstats/jobstats.py /usr/local/bin/
cp /path/to/jobstats/jobstats/output_formatters.py /usr/local/bin/
cp /path/to/jobstats/jobstats/config.py /usr/local/bin/
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
- ✅ Slurm with cgroup support already configured
- ✅ NVIDIA drivers and nvidia-smi available
- ✅ Go compiler installed

#### 4.2 Build and Install Exporters

**Cgroup Exporter:**
```bash
cd /path/to/cgroup_exporter
go build -o cgroup_exporter
cp cgroup_exporter /usr/local/bin/
```

**Node Exporter:**
```bash
cd /path/to/node_exporter
make build
cp node_exporter /usr/local/bin/
```

**NVIDIA GPU Exporter:**
```bash
cd /path/to/nvidia_gpu_prometheus_exporter
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
- Slurm configuration is managed by BCM in `/cm/shared/apps/slurm/var/etc/slurm/`
- BCM autogenerated sections cannot be edited directly
- Prolog/epilog settings must be added through BCM interface

### User Management
- System uses nslcd/slapd for user authentication
- Local system accounts created for service users
- Prometheus user already existed in the system

### File Locations
- Slurm configs: `/cm/shared/apps/slurm/var/etc/slurm/`
- Service configs: `/etc/systemd/system/`
- Prometheus data: `/var/lib/prometheus/`
- Grafana data: `/var/lib/grafana/`

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

### Log Locations
- Systemd logs: `journalctl -u <service-name>`
- Prometheus logs: `journalctl -u prometheus`
- Grafana logs: `/var/log/grafana/grafana.log`

## Next Steps

1. **Configure BCM**: Add the required Slurm prolog/epilog settings through BCM
2. **Import Grafana Dashboard**: Import the jobstats dashboard from the repository
3. **Test with Sample Jobs**: Run test jobs to verify metrics collection
4. **Configure Alerts**: Set up Grafana alerts for job efficiency issues
5. **User Training**: Provide documentation for users on using the jobstats command

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

```

Let me check for any linting errors and then provide a summary of the changes:


Perfect! I've successfully updated the `dgx-jobstats.md` documentation to reflect the production architecture with separate systems. Here's a summary of the key changes I made:

## Summary of Documentation Updates

### 1. **Updated Architecture Section**
- Added a clear breakdown of which components go on which systems
- Created a component distribution table showing what's required where
- Distinguished between BCM head node, Slurm controller, login nodes, DGX nodes, Prometheus server, and Grafana server

### 2. **Reorganized Deployment Steps**
- Restructured the entire deployment section by system type instead of by component
- Each system now has its own section with specific installation steps
- Clear separation of what needs to be installed where

### 3. **Updated Configuration Examples**
- Changed all localhost references to use proper hostnames/IPs
- Updated Prometheus configuration to scrape multiple DGX nodes
- Modified jobstats configuration to point to the Prometheus server

### 4. **Added Network Configuration**
- Detailed network connectivity requirements between systems
- Firewall configuration examples for each system type
- Clear port requirements and access patterns

### 5. **Added Production vs Lab Distinction**
- Clear explanation of the differences between the lab environment (single system) and production (distributed)
- Helps users understand the transition from testing to production

### 6. **Enhanced Verification Steps**
- Updated verification commands to use proper hostnames
- Added system-by-system deployment checklist
- Clear verification steps for each component

### Key Production Architecture Points:

**Components that MUST be on DGX nodes:**
- cgroup_exporter (needs access to /slurm cgroup filesystem)
- nvidia_gpu_prometheus_exporter (needs access to nvidia-smi)
- prometheus node_exporter (needs access to system metrics)

**Components that can be on other systems:**
- Prometheus server (dedicated server)
- Grafana server (dedicated server or co-located with Prometheus)
- jobstats command (login nodes where users run jobs)
- Slurm prolog/epilog scripts (Slurm controller)

The documentation now provides a clear roadmap for deploying jobstats in a production environment with proper system separation while maintaining the security principle of only installing components where they're absolutely necessary.

