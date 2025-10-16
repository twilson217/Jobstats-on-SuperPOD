# Jobstats Troubleshooting Guide

This comprehensive troubleshooting guide documents the issues encountered during jobstats deployment and their solutions. This guide is based on real-world troubleshooting experience with BCM-managed Slurm clusters.

## Table of Contents

1. [Common Jobstats Issues](#common-jobstats-issues)
2. [Slurm Configuration Issues](#slurm-configuration-issues)
3. [Cgroup and Metrics Collection Issues](#cgroup-and-metrics-collection-issues)
4. [Prometheus Integration Issues](#prometheus-integration-issues)
5. [BCM-Specific Issues](#bcm-specific-issues)
6. [Jobstats Command Issues](#jobstats-command-issues)
7. [Service and Installation Issues](#service-and-installation-issues)
8. [Visual Features and Dashboard Issues](#visual-features-and-dashboard-issues)
9. [Testing and Validation](#testing-and-validation)
10. [Prevention and Best Practices](#prevention-and-best-practices)

## Common Jobstats Issues

### Issue: "No data was found for job X" or "This is probably because it is too old"

**Symptoms:**
- Jobstats command returns "No data was found for job X"
- Message suggests job is too old or expired from database
- Occurs even for recent jobs

**Root Causes:**
1. **Missing Prometheus metrics** - Job completed before metrics were scraped
2. **Incorrect Prometheus configuration** - Missing cluster labels
3. **Slurm database issues** - MariaDB not running or misconfigured
4. **Jobstats configuration** - Wrong Prometheus server address

**Solutions:**

#### 1. Check Prometheus Data Availability
```bash
# Check if job metrics exist in Prometheus
curl -s "http://statsrv:9090/api/v1/query?query=cgroup_cpu_total_seconds{jobid=\"JOB_ID\"}" | jq '.data.result | length'

# Check all cgroup metrics
curl -s "http://statsrv:9090/api/v1/label/__name__/values" | jq '.data[]' | grep cgroup
```

#### 2. Verify Slurm Database Connection
```bash
# Check MariaDB status
systemctl status mariadb

# Test Slurm database connection
sacct -u $USER --start=today --format=JobID,JobName,State,CPUTime
```

#### 3. Check Jobstats Configuration
```bash
# Verify Prometheus server address in config.py
grep "PROM_SERVER" /usr/local/jobstats/config.py

# Should show: PROM_SERVER = "http://statsrv:9090"
```

### Issue: "Total CPU time was found to be zero" / Falling back to seff

**Symptoms:**
- Jobstats shows "Total CPU time was found to be zero"
- Falls back to `seff` output instead of Prometheus metrics
- Low or zero CPU utilization displayed

**Root Causes:**
1. **Cgroup constraints disabled** - Slurm not creating cgroups for jobs
2. **Cgroup_exporter misconfigured** - Wrong paths or missing flags
3. **Short job duration** - Jobs complete before metrics collection
4. **Missing Slurm environment** - `module load slurm` not executed

**Solutions:**

#### 1. Enable Cgroup Constraints (BCM)
```bash
# Enable cgroup constraints via BCM
cmsh -c "wlm;use slurm;cgroups;set constrainramspace yes;commit"
cmsh -c "wlm;use slurm;cgroups;set constraincores yes;commit"
cmsh -c "wlm;use slurm;set selecttypeparameters CR_CPU_Memory;commit"

# Restart Slurm services
systemctl restart slurmctld
systemctl restart slurmd
```

#### 2. Configure Cgroup_exporter Correctly
```bash
# Check cgroup_exporter service configuration
systemctl cat cgroup_exporter

# Should include:
# --config.paths /slurm
# --collect.fullslurm
```

#### 3. Load Slurm Environment
```bash
module load slurm
jobstats -j JOB_ID
```

#### 4. Use Longer-Running Jobs for Testing
```bash
# Create CPU-intensive test job
srun --cpus-per-task=2 --mem=1G --time=60 --pty bash -c "echo 'CPU test'; sleep 30; echo 'Test completed'"
```

## Slurm Configuration Issues

### Issue: Slurm Services Failing to Start

**Symptoms:**
- `systemctl status slurmd` shows failed
- `systemctl status slurmctld` shows failed
- Slurm commands not working

**Root Causes:**
1. **Missing Slurm environment** - `module load slurm` not executed
2. **Configuration errors** - Invalid slurm.conf settings
3. **Permission issues** - Incorrect file ownership
4. **Dependency issues** - Required services not running

**Solutions:**

#### 1. Load Slurm Environment
```bash
# Load Slurm module
module load slurm

# Verify Slurm commands work
sinfo
squeue
```

#### 2. Check Slurm Configuration
```bash
# Verify slurm.conf syntax
slurmctld -t

# Check for configuration errors
journalctl -u slurmctld --since "5 minutes ago"
journalctl -u slurmd --since "5 minutes ago"
```

#### 3. Restart Services in Correct Order
```bash
# Stop services
systemctl stop slurmd
systemctl stop slurmctld

# Start in correct order
systemctl start slurmctld
sleep 5
systemctl start slurmd

# Verify status
systemctl status slurmctld
systemctl status slurmd
```

### Issue: Cgroups Not Created for Jobs

**Symptoms:**
- No cgroup directories in `/sys/fs/cgroup/cpu,cpuacct/slurm/`
- Cgroup_exporter not collecting job metrics
- Jobs run without resource constraints

**Root Causes:**
1. **Cgroup constraints disabled** - `ConstrainCores=no`, `ConstrainRAMSpace=no`
2. **Wrong select type parameters** - Missing `CR_CPU_Memory`
3. **Cgroup plugin issues** - Missing or misconfigured plugins

**Solutions:**

#### 1. Enable Cgroup Constraints (BCM Method)
```bash
# Use BCM cmsh commands (recommended for BCM-managed clusters)
cmsh -c "wlm;use slurm;cgroups;set constrainramspace yes;commit"
cmsh -c "wlm;use slurm;cgroups;set constraincores yes;commit"
cmsh -c "wlm;use slurm;set selecttypeparameters CR_CPU_Memory;commit"
```

#### 2. Verify Cgroup Configuration
```bash
# Check cgroup.conf settings
cat /cm/shared/apps/slurm/var/etc/slurm/cgroup.conf

# Should show:
# ConstrainCores=yes
# ConstrainRAMSpace=yes
```

#### 3. Test Cgroup Creation
```bash
# Run test job and check for cgroups
srun --cpus-per-task=2 --mem=1G --time=60 --pty bash -c "echo 'Test job'; sleep 20" &

# Check for cgroup directories
find /sys/fs/cgroup -name "*job*" -type d
```

## Cgroup and Metrics Collection Issues

### Issue: Cgroup_exporter Not Collecting Job Metrics

**Symptoms:**
- Cgroup_exporter running but no job-specific metrics
- Missing `jobid`, `step`, `task` labels in metrics
- Only system-level cgroup metrics available

**Root Causes:**
1. **Wrong cgroup paths** - Not pointing to Slurm cgroups
2. **Missing --collect.fullslurm flag** - Not parsing Slurm job data
3. **Cgroup_exporter version issues** - Using wrong exporter version

**Solutions:**

#### 1. Configure Correct Cgroup Paths
```bash
# Check current cgroup_exporter configuration
systemctl cat cgroup_exporter

# Should use:
# --config.paths /slurm
# --collect.fullslurm
```

#### 2. Verify Cgroup Paths Exist
```bash
# Check if Slurm cgroup paths exist
ls -la /sys/fs/cgroup/cpu,cpuacct/slurm/
ls -la /sys/fs/cgroup/memory/slurm/
```

#### 3. Test Metrics Collection
```bash
# Check cgroup_exporter metrics
curl -s "http://dgx-01:9306/metrics" | grep "cgroup_cpu_total_seconds" | head -5

# Should show job-specific metrics with jobid labels
```

### Issue: Prometheus Not Scraping Cgroup Metrics

**Symptoms:**
- Cgroup_exporter collecting metrics locally
- Prometheus not storing cgroup metrics
- Missing metrics in Prometheus queries

**Root Causes:**
1. **Missing cluster labels** - Prometheus config lacks cluster labels
2. **Scrape configuration errors** - Wrong job names or targets
3. **Network connectivity** - Prometheus can't reach exporters

**Solutions:**

#### 1. Add Cluster Labels to Prometheus Config
```yaml
# In prometheus.yml, add metric_relabel_configs:
- job_name: 'cgroup_exporter'
  static_configs:
    - targets: ['dgx-01:9306']
  metric_relabel_configs:
    - source_labels: [__name__]
      target_label: cluster
      replacement: 'slurm'
```

#### 2. Verify Prometheus Targets
```bash
# Check if cgroup_exporter is being scraped
curl -s "http://statsrv:9090/api/v1/targets" | jq '.data.activeTargets[] | select(.labels.job == "cgroup_exporter")'
```

#### 3. Test Prometheus Queries
```bash
# Query cgroup metrics in Prometheus
curl -s "http://statsrv:9090/api/v1/query?query=cgroup_cpu_total_seconds" | jq '.data.result'
```

## Prometheus Integration Issues

### Issue: Missing Cluster Labels in Metrics

**Symptoms:**
- Jobstats queries fail with "invalid parameter" errors
- Prometheus metrics lack cluster labels
- Jobstats falls back to seff output

**Root Causes:**
1. **Prometheus configuration missing relabeling** - No cluster label injection
2. **Wrong query format** - Jobstats expecting cluster labels
3. **Configuration mismatch** - Jobstats and Prometheus configs don't match

**Solutions:**

#### 1. Update Prometheus Configuration
```yaml
# Add metric_relabel_configs to all exporter jobs
- job_name: 'cgroup_exporter'
  static_configs:
    - targets: ['dgx-01:9306']
  metric_relabel_configs:
    - source_labels: [__name__]
      target_label: cluster
      replacement: 'slurm'

- job_name: 'node_exporter'
  static_configs:
    - targets: ['dgx-01:9100']
  metric_relabel_configs:
    - source_labels: [__name__]
      target_label: cluster
      replacement: 'slurm'
```

#### 2. Restart Prometheus
```bash
# Restart Prometheus to apply new configuration
systemctl restart prometheus

# Verify configuration is loaded
curl -s "http://statsrv:9090/api/v1/status/config" | jq '.data.yaml'
```

### Issue: Prometheus Configuration File Creation Errors

**Symptoms:**
- Guided setup fails during Prometheus config creation
- "Text file busy" errors
- Temporary file issues

**Root Causes:**
1. **File locking** - Prometheus using config file
2. **Permission issues** - Can't write to config directory
3. **Temporary file conflicts** - Multiple processes creating files

**Solutions:**

#### 1. Stop Prometheus Before Config Update
```bash
# Stop Prometheus service
systemctl stop prometheus

# Update configuration
# ... (update prometheus.yml)

# Start Prometheus
systemctl start prometheus
```

#### 2. Use Atomic File Operations
```bash
# Create config in temporary location first
cat > /tmp/prometheus.yml << 'EOF'
# ... configuration content ...
EOF

# Move atomically
mv /tmp/prometheus.yml /etc/prometheus/prometheus.yml
```

## BCM-Specific Issues

### Issue: BCM cmsh Commands Failing

**Symptoms:**
- `cmsh` commands return errors
- Configuration changes not applied
- "Command not found" errors

**Root Causes:**
1. **Missing commit keywords** - BCM commands need `commit`
2. **Wrong BCM headnode** - Commands run on wrong host
3. **Permission issues** - Insufficient privileges

**Solutions:**

#### 1. Always Include Commit Keywords
```bash
# Correct BCM command format
cmsh -c "wlm;use slurm;cgroups;set constrainramspace yes;commit"

# Wrong (missing commit)
cmsh -c "wlm;use slurm;cgroups;set constrainramspace yes"
```

#### 2. Run Commands on BCM Headnode
```bash
# Run cmsh commands on slurm_controller (BCM headnode)
ssh slogin "/cm/local/apps/cmd/bin/cmsh -c 'wlm;use slurm;cgroups;set constrainramspace yes;commit'"
```

### Issue: Prolog/Epilog Scripts Not Executing

**Symptoms:**
- GPU job ownership not tracked
- Missing `/run/gpustat/` files
- GPU metrics lack job labels

**Root Causes:**
1. **Wrong script locations** - Scripts not in BCM directories
2. **Missing symlinks** - BCM can't find scripts
3. **Permission issues** - Scripts not executable

**Solutions:**

#### 1. Use BCM Script Discovery Pattern
```bash
# Create shared storage directory
mkdir -p /cm/shared/apps/slurm/var/cm

# Copy scripts to shared storage
cp prolog-jobstats.sh /cm/shared/apps/slurm/var/cm/
cp epilog-jobstats.sh /cm/shared/apps/slurm/var/cm/

# Create symlinks with proper naming
ln -sf /cm/shared/apps/slurm/var/cm/prolog-jobstats.sh /cm/local/apps/slurm/var/prologs/60-prolog-jobstats.sh
ln -sf /cm/shared/apps/slurm/var/cm/epilog-jobstats.sh /cm/local/apps/slurm/var/epilogs/60-epilog-jobstats.sh
```

#### 2. Verify Script Execution
```bash
# Check if scripts are executable
ls -la /cm/local/apps/slurm/var/prologs/60-prolog-jobstats.sh
ls -la /cm/local/apps/slurm/var/epilogs/60-epilog-jobstats.sh

# Test script execution
bash /cm/local/apps/slurm/var/prologs/60-prolog-jobstats.sh
```

## Jobstats Command Issues

### Issue: TypeError in jobstats Output

**Symptoms:**
- `TypeError: unsupported operand type(s) for //: 'str' and 'int'`
- `TypeError: '>' not supported between instances of 'str' and 'int'`
- Malformed output with repeated text

**Root Causes:**
1. **UNLIMITED time limits** - String values in numeric operations
2. **Alloc/cores division** - String values in division operations
3. **Data type mismatches** - Slurm returning strings instead of numbers

**Solutions:**

#### 1. Fix UNLIMITED Time Limit Handling
```python
# In output_formatters.py, fix time_limit_formatted method
def time_limit_formatted(self) -> str:
    # Handle UNLIMITED time limit
    if self.js.timelimitraw == "UNLIMITED" or str(self.js.timelimitraw).upper() == "UNLIMITED":
        hs = "UNLIMITED"
    else:
        hs = self.human_seconds(SECONDS_PER_MINUTE * self.js.timelimitraw)
    return f"     Time Limit: {clr}{hs}{self.txt_normal}"
```

#### 2. Fix Alloc/Cores Division
```python
# In output_formatters.py, fix alloc/cores calculation
if cores > 0:
    if isinstance(alloc, str):
        hb_alloc = self.human_bytes(float(alloc) / cores).replace(".0GB", "GB")
    else:
        hb_alloc = self.human_bytes(alloc / cores).replace(".0GB", "GB")
else:
    hb_alloc = "Unknown"
```

#### 3. Use Patch Scripts
```bash
# Apply jobstats patches
python3 /path/to/fix_jobstats_timelimit.py
python3 /path/to/fix_jobstats_alloc_cores.py
```

### Issue: Jobstats Installation Path Problems

**Symptoms:**
- `jobstats` command not found
- Files installed in wrong location
- Symlink issues

**Root Causes:**
1. **Wrong installation directory** - Files in `/usr/local/bin/` instead of `/usr/local/jobstats/`
2. **Missing symlink** - No symlink to `/usr/local/bin/jobstats`
3. **Permission issues** - Files not executable

**Solutions:**

#### 1. Correct Installation Structure
```bash
# Create proper directory structure
mkdir -p /usr/local/jobstats

# Install files in correct location
cp jobstats /usr/local/jobstats/
cp jobstats.py /usr/local/jobstats/
cp output_formatters.py /usr/local/jobstats/
cp config.py /usr/local/jobstats/

# Create symlink
ln -sf /usr/local/jobstats/jobstats /usr/local/bin/jobstats

# Make executable
chmod +x /usr/local/jobstats/jobstats
```

#### 2. Verify Installation
```bash
# Check file locations
ls -la /usr/local/jobstats/
ls -la /usr/local/bin/jobstats

# Test command
which jobstats
jobstats --help
```

## Service and Installation Issues

### Issue: Systemd Services Failing to Start

**Symptoms:**
- Services show "failed" status
- "Text file busy" errors during updates
- Services not starting after installation

**Root Causes:**
1. **Binary in use** - Can't replace running binary
2. **Wrong service configuration** - Invalid systemd unit files
3. **Missing dependencies** - Required packages not installed

**Solutions:**

#### 1. Stop Services Before Updates
```bash
# Stop service before updating binary
systemctl stop cgroup_exporter
sleep 2

# Update binary
cp new_binary /usr/local/bin/cgroup_exporter

# Start service
systemctl start cgroup_exporter
```

#### 2. Verify Service Configuration
```bash
# Check service file
systemctl cat cgroup_exporter

# Test service configuration
systemd-analyze verify /etc/systemd/system/cgroup_exporter.service
```

### Issue: Missing Python Dependencies

**Symptoms:**
- Jobstats fails with import errors
- "ModuleNotFoundError" for requests or blessed
- Python package installation failures

**Root Causes:**
1. **Missing packages** - `python3-requests`, `python3-blessed` not installed
2. **Virtual environment issues** - Packages installed in wrong environment
3. **Package manager issues** - APT not finding packages

**Solutions:**

#### 1. Install Required Packages
```bash
# Update package list
apt update

# Install Python dependencies
apt install -y python3-requests python3-blessed

# Verify installation
python3 -c "import requests, blessed; print('Dependencies OK')"
```

#### 2. Handle Virtual Environment Issues
```bash
# If using virtual environment
python3 -m venv /tmp/jobstats_env
source /tmp/jobstats_env/bin/activate
pip install requests blessed

# Or install system-wide (if needed)
pip3 install --break-system-packages requests blessed
```

## Testing and Validation

### Issue: Test Jobs Not Generating Metrics

**Symptoms:**
- Test jobs complete successfully
- No cgroup metrics collected
- Jobstats shows zero utilization

**Root Causes:**
1. **Jobs too short** - Complete before metrics collection
2. **No resource requests** - Jobs don't request CPU/memory
3. **Wrong partition** - Jobs on wrong Slurm partition

**Solutions:**

#### 1. Create Proper Test Jobs
```bash
# CPU-intensive job with resource requests
srun --cpus-per-task=2 --mem=1G --time=60 --pty bash -c "
    echo 'Starting CPU test'
    for i in {1..1000}; do
        echo 'CPU test running...'
        sleep 0.1
    done
    echo 'CPU test completed'
"

# GPU test job
srun --gpus=1 --cpus-per-task=4 --mem=8G --time=60 --pty bash -c "
    echo 'Starting GPU test'
    python3 -c '
import torch
x = torch.randn(1000, 1000).cuda()
for i in range(100):
    y = torch.mm(x, x)
print(\"GPU test completed\")
'"
```

#### 2. Use Dedicated Test Scripts
```python
# cpu_load_test.py
import time
import sys

duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30
print(f"Starting CPU load test for {duration} seconds")

start_time = time.time()
while time.time() - start_time < duration:
    # Busy loop to consume CPU
    for i in range(1000000):
        pass
    time.sleep(0.1)

print("CPU load test completed")
```

### Issue: Validation Scripts Failing

**Symptoms:**
- Validation tests fail
- Incorrect path checks
- Missing service validations

**Root Causes:**
1. **Wrong paths** - Validation checking incorrect locations
2. **Service name mismatches** - Different service names than expected
3. **Timing issues** - Services not ready when checked

**Solutions:**

#### 1. Update Validation Paths
```python
# Check correct BCM paths
def validate_cgroup_exporter():
    # Check service status
    result = subprocess.run(['systemctl', 'is-active', 'cgroup_exporter'], 
                          capture_output=True, text=True)
    if result.stdout.strip() != 'active':
        return False, "Cgroup exporter not active"
    
    # Check metrics endpoint
    try:
        response = requests.get('http://localhost:9306/metrics', timeout=5)
        if response.status_code == 200:
            return True, "Cgroup exporter working"
    except:
        return False, "Cannot reach cgroup exporter metrics"
```

#### 2. Add Retry Logic
```python
import time

def check_service_with_retry(service_name, max_retries=3):
    for attempt in range(max_retries):
        result = subprocess.run(['systemctl', 'is-active', service_name], 
                              capture_output=True, text=True)
        if result.stdout.strip() == 'active':
            return True
        time.sleep(5)
    return False
```

## Prevention and Best Practices

### 1. Always Use BCM Commands for Configuration
- Use `cmsh` commands instead of direct file editing
- Always include `commit` keyword
- Run commands on correct BCM headnode

### 2. Test with Realistic Workloads
- Use jobs that request actual resources
- Run jobs long enough for metrics collection
- Test both CPU and GPU workloads

### 3. Verify Each Step
- Check service status after installation
- Verify metrics collection before proceeding
- Test jobstats command with known jobs

### 4. Use Proper Installation Structure
- Install jobstats files in `/usr/local/jobstats/`
- Create proper symlinks
- Set correct permissions

### 5. Monitor Logs
- Check systemd service logs
- Monitor Prometheus targets
- Verify cgroup creation

### 6. Document Changes
- Keep track of configuration changes
- Document any manual fixes
- Update deployment scripts

## Quick Reference Commands

### Essential BCM Commands
```bash
# Enable cgroup constraints
cmsh -c "wlm;use slurm;cgroups;set constrainramspace yes;commit"
cmsh -c "wlm;use slurm;cgroups;set constraincores yes;commit"
cmsh -c "wlm;use slurm;set selecttypeparameters CR_CPU_Memory;commit"

# Configure epilogslurmctld
cmsh -c "wlm;use slurm;set epilogslurmctld /usr/local/sbin/slurmctldepilog.sh;commit"
```

### Service Management
```bash
# Restart Slurm services
systemctl restart slurmctld
systemctl restart slurmd

# Check service status
systemctl status cgroup_exporter
systemctl status nvidia_gpu_exporter
systemctl status node_exporter
```

### Testing Commands
```bash
# Load Slurm environment
source /etc/profile.d/modules.sh
module load slurm

# Test jobstats
jobstats -j JOB_ID

# Check Prometheus metrics
curl -s "http://statsrv:9090/api/v1/query?query=cgroup_cpu_total_seconds" | jq
```

### Verification Commands
```bash
# Check cgroup creation
find /sys/fs/cgroup -name "*job*" -type d

# Check cgroup_exporter metrics
curl -s "http://dgx-01:9306/metrics" | grep "cgroup_cpu_total_seconds"

# Check Prometheus targets
curl -s "http://statsrv:9090/api/v1/targets" | jq '.data.activeTargets[]'
```

## Visual Features and Dashboard Issues

### Issue: Grafana Dashboard Shows "No Data"

**Symptoms:**
- Grafana dashboard panels display "No data" or empty graphs
- Job ID input returns no results
- All visualizations appear empty

**Root Causes:**
1. **Prometheus not collecting data** - Exporters not running or misconfigured
2. **Job ID doesn't exist in Prometheus** - Job completed before metrics were collected
3. **Incorrect Prometheus data source** - Grafana pointing to wrong Prometheus instance
4. **Time range issues** - Dashboard looking at wrong time period

**Solutions:**

#### 1. Check Prometheus Data Collection
```bash
# Check if Prometheus is collecting data
curl -s http://<monitoring server>:9090/api/v1/query?query=up

# Verify job ID exists in Prometheus
curl -s "http://<monitoring server>:9090/api/v1/query?query=cgroup_cpus{jobid=\"<jobid>\"}"

# Check all available job IDs
curl -s "http://<monitoring server>:9090/api/v1/query?query=group by (jobid) (cgroup_cpu_total_seconds)" | jq
```

#### 2. Verify Grafana Data Source
- Go to Grafana → Configuration → Data Sources
- Check that Prometheus data source is configured correctly
- Test the connection using "Test" button
- Ensure URL points to correct Prometheus server

#### 3. Check Time Range
- Verify dashboard time range includes the job execution period
- Use "Last 1 hour" or "Last 6 hours" for recent jobs
- Check if job completed within the selected time range

### Issue: Grafana Dashboard Import Fails

**Symptoms:**
- Dashboard import fails with error messages
- Imported dashboard shows errors or missing panels
- JSON file upload fails

**Root Causes:**
1. **Incompatible Grafana version** - Dashboard requires newer Grafana
2. **Corrupted JSON file** - File damaged during transfer
3. **Missing data source** - Dashboard references non-existent data source
4. **Permission issues** - Insufficient access to import dashboards

**Solutions:**

#### 1. Check Grafana Version
```bash
# Check Grafana version
grafana-server --version

# Ensure version is 8.1.2 or compatible
# Upgrade if necessary
```

#### 2. Verify JSON File Integrity
```bash
# Check file exists and is readable
ls -la /opt/jobstats-deployment/jobstats/grafana/Single_Job_Stats.json

# Validate JSON syntax
python3 -m json.tool /opt/jobstats-deployment/jobstats/grafana/Single_Job_Stats.json > /dev/null
```

#### 3. Check Data Source Configuration
- Ensure Prometheus data source is configured before importing
- Verify data source name matches dashboard requirements
- Test data source connection

### Issue: Additional Tools Can't Connect to Prometheus

**Symptoms:**
- gpudash shows connection errors
- Job Defense Shield fails to connect
- Tools report "Connection refused" or timeout errors

**Root Causes:**
1. **Prometheus server not running** - Service stopped or crashed
2. **Network connectivity issues** - Firewall blocking connections
3. **Wrong server address** - Tools pointing to incorrect Prometheus URL
4. **Port conflicts** - Another service using port 9090

**Solutions:**

#### 1. Verify Prometheus Server Status
```bash
# Check Prometheus service status
systemctl status prometheus

# Check if Prometheus is listening on port 9090
netstat -tlnp | grep :9090 || ss -tlnp | grep :9090

# Test local connection
curl -s http://localhost:9090/api/v1/query?query=up
```

#### 2. Check Network Connectivity
```bash
# Test connection from tool server to Prometheus
telnet <monitoring server> 9090

# Check if port is open
nmap -p 9090 <monitoring server>

# Test with curl
curl -s http://<monitoring server>:9090/api/v1/query?query=up
```

#### 3. Verify Firewall Rules
```bash
# Check firewall status
ufw status

# Allow Prometheus port if needed
ufw allow 9090

# Check iptables rules
iptables -L | grep 9090
```

### Issue: GPU Dashboard (gpudash) Not Working

**Symptoms:**
- gpudash shows "No GPUs found" or connection errors
- Empty output or crashes when running
- Can't connect to GPU nodes

**Root Causes:**
1. **Missing Python dependencies** - blessed or requests not installed
2. **GPU nodes not accessible** - Network or SSH issues
3. **nvidia-smi not available** - NVIDIA drivers not installed
4. **Permission issues** - Can't access GPU information

**Solutions:**

#### 1. Install Dependencies
```bash
# Install required Python packages
pip3 install blessed requests

# Verify installation
python3 -c "import blessed, requests; print('Dependencies OK')"
```

#### 2. Check GPU Node Access
```bash
# Test SSH access to GPU nodes
ssh <dgx node> "nvidia-smi"

# Check if nvidia-smi is available
ssh <dgx node> "which nvidia-smi"

# Test GPU information retrieval
ssh <dgx node> "nvidia-smi --query-gpu=index,name,utilization.gpu --format=csv"
```

#### 3. Verify GPU Exporter
```bash
# Check if nvidia_gpu_exporter is running
ssh <dgx node> "systemctl status nvidia_gpu_exporter"

# Test metrics endpoint
curl -s http://<dgx node>:9445/metrics | grep nvidia_gpu
```

### Issue: Job Defense Shield Not Working

**Symptoms:**
- Job Defense Shield fails to generate reports
- Configuration errors or missing files
- Can't connect to Prometheus or Slurm

**Root Causes:**
1. **Missing configuration file** - config.json not created or misconfigured
2. **Wrong Prometheus URL** - Pointing to incorrect server
3. **Missing dependencies** - Python packages not installed
4. **Permission issues** - Can't access required files

**Solutions:**

#### 1. Create Configuration File
```bash
# Copy example configuration
cp config.json.example config.json

# Edit configuration with correct settings
nano config.json

# Verify configuration
python3 -c "import json; json.load(open('config.json'))"
```

#### 2. Install Dependencies
```bash
# Install required packages
pip3 install -r requirements.txt

# Verify installation
python3 -c "import job_defense_shield; print('Dependencies OK')"
```

#### 3. Test Configuration
```bash
# Run dry-run test
python3 job_defense_shield.py --config config.json --dry-run

# Test Prometheus connection
python3 -c "import requests; requests.get('http://<monitoring server>:9090/api/v1/query?query=up')"
```

This troubleshooting guide should help resolve most common issues encountered during jobstats deployment. Always start with the most likely causes and work through the solutions systematically.