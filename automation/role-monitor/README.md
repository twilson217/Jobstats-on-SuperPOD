# BCM Role Monitor - Complete Documentation

**Last Updated:** October 6, 2025  
**Status:** Production Ready

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Dynamic Prometheus Target Management](#dynamic-prometheus-target-management)
5. [Command-Line Arguments](#command-line-arguments)
6. [Custom Prometheus Targets Directory](#custom-prometheus-targets-directory)
7. [Guided Setup Integration](#guided-setup-integration)
8. [Auto-Configuration Logic](#auto-configuration-logic)
9. [Deployment](#deployment)
10. [Configuration](#configuration)
11. [Troubleshooting](#troubleshooting)
12. [FAQ](#faq)

---

## Overview

The BCM Role Monitor is an automated service management system that runs on DGX nodes to monitor BCM role assignments and automatically manage jobstats exporter services and Prometheus targets based on configuration overlays.

### Key Features

- ✅ **Automatic Service Management**: Starts/stops jobstats exporters based on `slurmclient` role assignment
- ✅ **Dynamic Prometheus Targets**: Automatically manages Prometheus service discovery files
- ✅ **BCM REST API Integration**: Uses BCM's `/rest/v1/device` endpoint for real-time role monitoring
- ✅ **Distributed Architecture**: Runs independently on each DGX node
- ✅ **Retry Logic**: Intelligent retry mechanism for failed service starts (3 attempts over 30 minutes)
- ✅ **Secure Configuration**: Certificates stored with minimal permissions
- ✅ **BCM Imaging Compatible**: Uses dynamic hostname lookup for seamless image deployment
- ✅ **Custom Directory Support**: Flexible Prometheus targets directory configuration

### What It Does

1. **Monitors BCM API** every 60 seconds to check if node has `slurmclient` role
2. **Manages Services**: Starts/stops exporters (node_exporter, cgroup_exporter, nvidia_gpu_exporter)
3. **Manages Prometheus Targets**: Creates/removes JSON files for Prometheus service discovery
4. **Handles Hostname Changes**: Automatically updates target files when hostname changes
5. **Self-Cleaning**: Removes target files when role is removed

---

## Quick Start

### Quick Checks

**Is the service running?**
```bash
ssh <node> "systemctl status bcm-role-monitor"
```

**Are target files being created?**
```bash
ls -la /cm/shared/apps/jobstats/prometheus-targets/
```

**Is Prometheus scraping the node?**
```bash
curl -s http://prometheus:9090/api/v1/targets | grep <hostname>
```

**View recent service activity:**
```bash
ssh <node> "journalctl -u bcm-role-monitor -n 20 --no-pager"
```

### Common Scenarios

#### New DGX Node Added to Cluster
1. Deploy BCM role monitor service
2. Assign `slurmclient` role via BCM
3. Within 60 seconds: Service creates target files
4. Within 30 seconds: Prometheus discovers and starts scraping

**No manual Prometheus configuration needed!**

#### Node Removed from Slurm
1. Remove `slurmclient` role via BCM
2. Within 60 seconds: Service deletes target files
3. Within 30 seconds: Prometheus stops scraping

**No manual Prometheus configuration needed!**

#### Node Hostname Changed
1. Change hostname via BCM
2. On next check (60 seconds): Service detects new hostname
3. Service writes new files with updated hostname
4. Prometheus picks up new hostname within 30 seconds

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ DGX Node (dgx-01)                                           │
│                                                              │
│  ┌────────────────────────────────────────┐                │
│  │ BCM Role Monitor Service               │                │
│  │                                         │                │
│  │ When slurmclient role assigned:        │                │
│  │   • Start exporter services            │                │
│  │   • Write Prometheus target file       │                │
│  │                                         │                │
│  │ When slurmclient role removed:         │                │
│  │   • Stop exporter services             │                │
│  │   • Delete Prometheus target file      │                │
│  └────┼────────────────────────────────────┘                │
│       │                                                      │
│       ▼                                                      │
│  /cm/shared/apps/jobstats/prometheus-targets/dgx-01.json   │
│  (Contains: node_exporter, cgroup_exporter, gpu_exporter)  │
└─────────────────────────────────────────────────────────────┘
                         ▲
                         │ NFS mount
                         │
┌────────────────────────┼────────────────────────────────────┐
│ Prometheus Server      │                                    │
│                        │                                    │
│  All 3 jobs read the SAME file:                            │
│  - node_exporter    ─┐                                      │
│  - cgroup_exporter  ─┼─→ *.json (filtered by job label)    │
│  - gpu_exporter     ─┘                                      │
│                                                              │
│  Prometheus uses relabel_configs to filter by job label    │
└─────────────────────────────────────────────────────────────┘
```

### Components

**On DGX Nodes:**
- **Service:** `/etc/systemd/system/bcm-role-monitor.service`
- **Script:** `/usr/local/bin/bcm_role_monitor.py`
- **Config:** `/etc/bcm-role-monitor/config.json`
- **Certificates:** `/etc/bcm-role-monitor/admin.{pem,key}`
- **State:** `/var/lib/bcm-role-monitor/<hostname>_state.json`
- **Logs:** `journalctl -u bcm-role-monitor`

**On Shared Storage:**
- **Target files:** `/cm/shared/apps/jobstats/prometheus-targets/<hostname>.json`

**On Prometheus Server:**
- **Config:** `/etc/prometheus/prometheus.yml`

---

## Dynamic Prometheus Target Management

### How It Works

DGX nodes automatically manage their presence in Prometheus by creating/removing a **single JSON file** containing all three exporters when the BCM `slurmclient` role is assigned/removed.

### Single File Per Node

Each node creates **one file** named `<hostname>.json`:

```json
[
  {
    "targets": ["dgx-01:9100"],
    "labels": {
      "job": "node_exporter",
      "cluster": "slurm",
      "hostname": "dgx-01"
    }
  },
  {
    "targets": ["dgx-01:9306"],
    "labels": {
      "job": "cgroup_exporter",
      "cluster": "slurm",
      "hostname": "dgx-01"
    }
  },
  {
    "targets": ["dgx-01:9445"],
    "labels": {
      "job": "gpu_exporter",
      "cluster": "slurm",
      "hostname": "dgx-01"
    }
  }
]
```

### Prometheus Configuration

All three scrape jobs read the **same files** but filter by the `job` label:

```yaml
scrape_configs:
  - job_name: 'node_exporter'
    file_sd_configs:
      - files:
          - '/cm/shared/apps/jobstats/prometheus-targets/*.json'
        refresh_interval: 30s
    relabel_configs:
      - source_labels: [job]
        regex: 'node_exporter'
        action: keep
    metric_relabel_configs:
      - target_label: cluster
        replacement: slurm
      - source_labels: [__name__]
        regex: '^go_.*'
        action: drop

  - job_name: 'cgroup_exporter'
    file_sd_configs:
      - files:
          - '/cm/shared/apps/jobstats/prometheus-targets/*.json'
        refresh_interval: 30s
    relabel_configs:
      - source_labels: [job]
        regex: 'cgroup_exporter'
        action: keep
    metric_relabel_configs:
      - target_label: cluster
        replacement: slurm

  - job_name: 'nvidia_gpu_exporter'
    file_sd_configs:
      - files:
          - '/cm/shared/apps/jobstats/prometheus-targets/*.json'
        refresh_interval: 30s
    relabel_configs:
      - source_labels: [job]
        regex: 'gpu_exporter'
        action: keep
    metric_relabel_configs:
      - target_label: cluster
        replacement: slurm
```

### Benefits

✅ **1 file per node** instead of 3  
✅ **No subdirectories** to manage  
✅ **Atomic updates** - all exporters updated in one operation  
✅ **Simpler logs** - one message instead of three  
✅ **Easier to see active nodes** - just `ls *.json`  
✅ **Easier cleanup** - delete one file, not three  

---

## Command-Line Arguments

### Overview

The BCM role monitor supports command-line arguments for flexible configuration, particularly useful for customers with existing Prometheus infrastructure.

### Usage

#### Default Behavior (No Changes Required)
```bash
/usr/local/bin/bcm_role_monitor.py
```
Uses: `/cm/shared/apps/jobstats/prometheus-targets/`

#### Custom Directory
```bash
/usr/local/bin/bcm_role_monitor.py --prometheus-targets-dir /my/custom/targets
```
Uses: `/my/custom/targets/`

#### In Systemd Service File
```systemd
[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/bcm_role_monitor.py --prometheus-targets-dir /shared/prometheus/targets
ReadWritePaths=/var/lib/bcm-role-monitor /var/log /etc/bcm-role-monitor /shared/prometheus/targets
```

### Available Options

```
--config CONFIG
    Path to configuration file
    Default: /etc/bcm-role-monitor/config.json

--prometheus-targets-dir PROMETHEUS_TARGETS_DIR
    Override Prometheus targets directory
    Default: from config or /cm/shared/apps/jobstats/prometheus-targets

--help
    Show help message and examples
```

### Priority Order

1. **Command-line argument** (highest priority)
2. **Configuration file** (`prometheus_targets_dir` in config.json)
3. **Default** (`/cm/shared/apps/jobstats/prometheus-targets/`)

### Example Use Cases

#### Existing Prometheus with Custom Directory
```systemd
ExecStart=/usr/bin/python3 /usr/local/bin/bcm_role_monitor.py --prometheus-targets-dir /srv/prometheus/targets
```

#### Multiple Clusters
```systemd
# Cluster A
ExecStart=/usr/bin/python3 /usr/local/bin/bcm_role_monitor.py --prometheus-targets-dir /shared/prometheus/cluster-a

# Cluster B  
ExecStart=/usr/bin/python3 /usr/local/bin/bcm_role_monitor.py --prometheus-targets-dir /shared/prometheus/cluster-b
```

#### Different Storage Backend
```systemd
# Using CephFS instead of NFS
ExecStart=/usr/bin/python3 /usr/local/bin/bcm_role_monitor.py --prometheus-targets-dir /cephfs/monitoring/targets
```

---

## Custom Prometheus Targets Directory

### Use Cases

1. **Existing Prometheus Server** - Integrate without changing existing file structure
2. **Different NFS Export** - Use organization's standard NFS export
3. **Multiple Clusters** - Separate target files by cluster
4. **Custom Storage Backend** - Use CephFS, GlusterFS, etc.

### Configuration Methods

#### Method 1: Command-Line Argument (Recommended)

```systemd
[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/bcm_role_monitor.py --prometheus-targets-dir /my/custom/targets
```

**Advantages:**
- ✅ Explicit and visible in service definition
- ✅ Easy to see what's configured
- ✅ Overrides any config file setting

#### Method 2: Configuration File

Set in `/etc/bcm-role-monitor/config.json`:

```json
{
  "prometheus_targets_dir": "/my/custom/targets",
  "bcm_headnodes": ["headnode"],
  "bcm_port": 8081
}
```

**Advantages:**
- ✅ Centralized configuration
- ✅ No need to modify service file
- ✅ Can be managed by configuration management tools

### Step-by-Step Setup

#### Step 1: Choose Your Custom Directory

Example: `/shared/prometheus/service-discovery/`

#### Step 2: Create the Directory

```bash
mkdir -p /shared/prometheus/service-discovery/
chmod 755 /shared/prometheus/service-discovery/
```

#### Step 3: Ensure Directory is Mounted on All Nodes

```bash
ssh dgx-01 "ls -la /shared/prometheus/service-discovery/"
```

#### Step 4: Update Service File

Edit `/etc/systemd/system/bcm-role-monitor.service`:

```systemd
[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/bcm_role_monitor.py --prometheus-targets-dir /shared/prometheus/service-discovery
```

**IMPORTANT:** Also update `ReadWritePaths`:

```systemd
ReadWritePaths=/var/lib/bcm-role-monitor /var/log /etc/bcm-role-monitor /shared/prometheus/service-discovery
```

#### Step 5: Reload and Restart Service

```bash
systemctl daemon-reload
systemctl restart bcm-role-monitor
```

#### Step 6: Verify Target Files Created

```bash
ls -la /shared/prometheus/service-discovery/
# Should show: dgx-01.json, dgx-02.json, etc.
```

#### Step 7: Update Prometheus Configuration

```yaml
scrape_configs:
  - job_name: 'node_exporter'
    file_sd_configs:
      - files:
          - '/shared/prometheus/service-discovery/*.json'
        refresh_interval: 30s
    relabel_configs:
      - source_labels: [job]
        regex: 'node_exporter'
        action: keep
```

#### Step 8: Reload Prometheus

```bash
curl -X POST http://prometheus:9090/-/reload
```

---

## Guided Setup Integration

### Overview

The guided setup (`automation/guided_setup.py`) includes the BCM role monitor as an **optional** deployment step (Section 10) with support for custom Prometheus targets directory configuration.

### Interactive Mode

When users reach Section 10, they will be asked:

1. **"Do you want to deploy the BCM role monitor? (yes/no)"**
   - Default: `yes`
   - If `no`: Skip deployment, provide manual deployment instructions
   - If `yes`: Continue to configuration

2. **"Use custom Prometheus targets directory? (yes/no)"**
   - Default: `no` (use `/cm/shared/apps/jobstats/prometheus-targets/`)
   - If `no`: Use default directory
   - If `yes`: Prompt for custom directory path

3. **"Enter Prometheus targets directory:"** (if custom selected)
   - Default: `/cm/shared/apps/jobstats/prometheus-targets`
   - User can specify any shared storage path

### Non-Interactive Mode

For automated deployments, configuration file options:

```json
{
  "deploy_bcm_role_monitor": true,
  "use_custom_prometheus_targets_dir": false,
  "prometheus_targets_dir": "/custom/path/to/targets"
}
```

### What Gets Deployed

#### Default Configuration (No Custom Directory)

**Service file:**
```systemd
[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/bcm_role_monitor.py
ReadWritePaths=/var/lib/bcm-role-monitor /var/log /etc/bcm-role-monitor /cm/shared/apps/jobstats/prometheus-targets
```

**Target files created at:**
```
/cm/shared/apps/jobstats/prometheus-targets/<hostname>.json
```

#### Custom Directory Configuration

**Service file (automatically generated):**
```systemd
[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/bcm_role_monitor.py --prometheus-targets-dir /custom/path
ReadWritePaths=/var/lib/bcm-role-monitor /var/log /etc/bcm-role-monitor /custom/path
```

**Target files created at:**
```
/custom/path/<hostname>.json
```

---

## Auto-Configuration Logic

### Overview

The guided setup automatically configures the BCM role monitor deployment based on whether you're deploying a new Prometheus server or using an existing one.

### Scenario 1: New Prometheus Deployment

**Config:**
```json
{
  "use_existing_prometheus": false
}
```

**Auto-configured behavior:**
- ✅ `deploy_bcm_role_monitor`: `true`
- ✅ `use_custom_prometheus_targets_dir`: `false`
- ✅ `prometheus_targets_dir`: `/cm/shared/apps/jobstats/prometheus-targets/` (default)

**Rationale:** New Prometheus deployment means we control the entire stack, so we can use the default directory structure.

### Scenario 2: Existing Prometheus Deployment

**Config:**
```json
{
  "use_existing_prometheus": true,
  "prometheus_targets_dir": "/srv/prometheus/service-discovery"
}
```

**Auto-configured behavior:**
- ✅ `deploy_bcm_role_monitor`: `true`
- ✅ `use_custom_prometheus_targets_dir`: `true`
- ✅ `prometheus_targets_dir`: Value from config (required)

**Rationale:** Existing Prometheus likely has its own directory structure for service discovery files, so we need to integrate with it.

### Scenario 3: Existing Prometheus Without Custom Directory

**Config:**
```json
{
  "use_existing_prometheus": true
  // Missing: prometheus_targets_dir
}
```

**Behavior:**
- ⚠️ Warning displayed: "Using existing Prometheus but no custom targets directory specified in config"
- ⚠️ Falls back to default directory
- ⚠️ User should add `prometheus_targets_dir` to config

### Configuration Examples

#### Example 1: New Prometheus (Minimal Config)

**File:** `automation/configs/config.example-new-prometheus.json`

```json
{
  "cluster_name": "slurm",
  "prometheus_server": "prometheus",
  "use_existing_prometheus": false,
  "bcm_category_management": true,
  "systems": {
    "dgx_nodes": ["dgx-01", "dgx-02"],
    "prometheus_server": ["prometheus"]
  }
}
```

**Result:** BCM role monitor deployed with default directory

#### Example 2: Existing Prometheus (Full Config)

**File:** `automation/configs/config.example-existing-prometheus.json`

```json
{
  "cluster_name": "slurm",
  "prometheus_server": "existing-prometheus",
  "use_existing_prometheus": true,
  "prometheus_targets_dir": "/srv/prometheus/service-discovery",
  "bcm_category_management": true,
  "systems": {
    "dgx_nodes": ["dgx-01", "dgx-02"],
    "prometheus_server": ["existing-prometheus"]
  }
}
```

**Result:** BCM role monitor deployed with custom directory

---

## Deployment

### Automatic Deployment (Recommended)

Via guided setup:

```bash
uv run python automation/guided_setup.py --config automation/configs/config.json
```

The BCM role monitor is deployed in Section 10.

### Manual Deployment

#### Deploy to Specific Nodes

```bash
python3 automation/role-monitor/deploy_bcm_role_monitor.py --dgx-nodes dgx-01 dgx-02
```

#### Deploy to All Nodes from Config

```bash
python3 automation/role-monitor/deploy_bcm_role_monitor.py --config automation/configs/config.json
```

#### Deploy with Custom Prometheus Targets Directory

```bash
python3 automation/role-monitor/deploy_bcm_role_monitor.py \
  --dgx-nodes dgx-01 dgx-02 \
  --prometheus-targets-dir /custom/path
```

---

## Configuration

### Service Configuration

The service is configured via `/etc/bcm-role-monitor/config.json` on each DGX node:

```json
{
  "bcm_headnodes": ["bcm-headnode-01", "bcm-headnode-02"],
  "bcm_port": 8081,
  "cert_path": "/etc/bcm-role-monitor/admin.pem",
  "key_path": "/etc/bcm-role-monitor/admin.key",
  "check_interval": 60,
  "retry_interval": 600,
  "max_retries": 3,
  "prometheus_targets_dir": "/cm/shared/apps/jobstats/prometheus-targets",
  "node_exporter_port": 9100,
  "cgroup_exporter_port": 9306,
  "nvidia_gpu_exporter_port": 9445,
  "cluster_name": "slurm"
}
```

### Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `bcm_headnodes` | List of BCM headnode hostnames | Auto-discovered |
| `bcm_port` | BCM REST API port | 8081 |
| `cert_path` | Path to admin certificate | `/etc/bcm-role-monitor/admin.pem` |
| `key_path` | Path to admin key | `/etc/bcm-role-monitor/admin.key` |
| `check_interval` | Seconds between role checks | 60 |
| `retry_interval` | Seconds between retry attempts | 600 |
| `max_retries` | Maximum service start retries | 3 |
| `prometheus_targets_dir` | Prometheus targets directory | `/cm/shared/apps/jobstats/prometheus-targets` |
| `node_exporter_port` | Node exporter port | 9100 |
| `cgroup_exporter_port` | Cgroup exporter port | 9306 |
| `nvidia_gpu_exporter_port` | GPU exporter port | 9445 |
| `cluster_name` | Cluster identifier | `slurm` |

---

## Troubleshooting

### Service Not Running

**Check service status:**
```bash
ssh <node> "systemctl status bcm-role-monitor"
```

**View logs:**
```bash
ssh <node> "journalctl -u bcm-role-monitor -n 50 --no-pager"
```

**Restart service:**
```bash
ssh <node> "systemctl restart bcm-role-monitor"
```

### Target Files Not Being Created

**Check if directory exists:**
```bash
ls -la /cm/shared/apps/jobstats/prometheus-targets/
```

**Check service logs for errors:**
```bash
ssh <node> "journalctl -u bcm-role-monitor -n 50 --no-pager | grep ERROR"
```

**Verify write permissions:**
```bash
ssh <node> "touch /cm/shared/apps/jobstats/prometheus-targets/test && rm /cm/shared/apps/jobstats/prometheus-targets/test"
```

**Check ReadWritePaths in service file:**
```bash
ssh <node> "grep ReadWritePaths /etc/systemd/system/bcm-role-monitor.service"
```

### "Read-only file system" Error

**Solution:** Update `ReadWritePaths` in service file:

```systemd
ReadWritePaths=/var/lib/bcm-role-monitor /var/log /etc/bcm-role-monitor /your/custom/path
```

Then reload:
```bash
systemctl daemon-reload
systemctl restart bcm-role-monitor
```

### Prometheus Not Discovering Targets

**Check Prometheus config:**
```bash
ssh prometheus "cat /etc/prometheus/prometheus.yml | grep -A 5 file_sd_configs"
```

**Check Prometheus can access files:**
```bash
ssh prometheus "ls -la /cm/shared/apps/jobstats/prometheus-targets/"
```

**Check Prometheus logs:**
```bash
ssh prometheus "journalctl -u prometheus -n 50 --no-pager"
```

**Reload Prometheus:**
```bash
curl -X POST http://prometheus:9090/-/reload
```

### Stale Files for Removed Nodes

**List all target files:**
```bash
ls -la /cm/shared/apps/jobstats/prometheus-targets/
```

**List active nodes in BCM:**
```bash
cmsh -c "device list -f hostname,category" | grep dgx
```

**Remove stale files manually:**
```bash
rm -f /cm/shared/apps/jobstats/prometheus-targets/<old-hostname>.json
```

---

## FAQ

### Q: Can different nodes use different target directories?
**A:** Yes! Each node can be configured independently. However, Prometheus needs to read from all directories.

### Q: Can I use a local directory instead of shared storage?
**A:** No. Prometheus needs to read the files, so they must be on shared storage accessible to both nodes and Prometheus server.

### Q: What happens if the custom directory becomes unavailable?
**A:** The service will log a warning and continue monitoring BCM/managing services. It will retry writing target files on the next check cycle (60 seconds).

### Q: Can I change the directory while the service is running?
**A:** You need to update the service file and restart the service. The change is not picked up dynamically.

### Q: Does this work with multiple Prometheus servers?
**A:** Yes! Multiple Prometheus servers can read from the same shared directory.

### Q: How do I skip BCM role monitor deployment?
**A:** Set `"deploy_bcm_role_monitor": false` in your config.json, or answer "no" when prompted in interactive mode.

### Q: What happens when a node's hostname changes?
**A:** The service detects the new hostname and creates a new target file with the updated hostname. Old files can be manually cleaned up.

### Q: Can I manually add a node to Prometheus?
**A:** Yes! Create a JSON file manually:
```bash
cat > /cm/shared/apps/jobstats/prometheus-targets/test-node.json <<'EOF'
[
  {"targets": ["test-node:9100"], "labels": {"job": "node_exporter", "cluster": "slurm", "hostname": "test-node"}},
  {"targets": ["test-node:9306"], "labels": {"job": "cgroup_exporter", "cluster": "slurm", "hostname": "test-node"}},
  {"targets": ["test-node:9445"], "labels": {"job": "gpu_exporter", "cluster": "slurm", "hostname": "test-node"}}
]
EOF
```

---

## Additional Resources

- **Deployment Script:** `automation/role-monitor/deploy_bcm_role_monitor.py`
- **Service File:** `automation/role-monitor/bcm-role-monitor.service`
- **Example Service File:** `automation/role-monitor/bcm-role-monitor.service.example-custom-targets`
- **Main Script:** `automation/role-monitor/bcm_role_monitor.py`
- **Guided Setup:** `automation/guided_setup.py`
- **Example Configs:** `automation/configs/config.example-*.json`

---

**For issues or questions, check the service logs first:**
```bash
journalctl -u bcm-role-monitor -n 50 --no-pager
```
