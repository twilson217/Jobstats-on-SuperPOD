# Prometheus Capacity Planning for Jobstats

Estimate Prometheus storage requirements before deploying jobstats monitoring.

## Quick Start

### Standalone Deployment

The capacity planner is **completely standalone** - just copy the script and run it!

```bash
# Copy to any system with Slurm
scp prometheus_capacity_planner.py user@slurm-login:/tmp/

# SSH and run
ssh user@slurm-login
python3 /tmp/prometheus_capacity_planner.py --verbose
```

**Requirements:**
- Python 3.6+ (standard on modern Linux)
- Slurm commands: `sinfo` (required), `sacct` (optional)
- **No external dependencies!**

### Basic Usage

```bash
# Run with defaults (365 days retention, 30s scrape interval)
python3 prometheus_capacity_planner.py

# Detailed analysis with partition breakdown
python3 prometheus_capacity_planner.py --verbose

# Export JSON report
python3 prometheus_capacity_planner.py --output-json capacity_report.json

# Custom configuration
python3 prometheus_capacity_planner.py --retention-days 180 --scrape-interval 60
```

## What It Does

Analyzes your Slurm cluster to estimate Prometheus storage requirements:

1. **Queries Slurm** for cluster configuration (nodes, GPUs, partitions)
2. **Analyzes job history** from `sacct` (or uses estimates if unavailable)
3. **Calculates storage** for three metric types:
   - **System metrics** (node_exporter): ~2.5 GB/node/year
   - **Job metrics** (cgroup_exporter): ~0.5 GB/concurrent job/year
   - **GPU metrics** (nvidia_gpu_exporter): ~0.5 GB/GPU/year
4. **Provides recommendations** for Prometheus server hardware

## Example Output

```
Cluster Configuration:
  Total Nodes:          30
  • GPU Nodes:          10
  • CPU-Only Nodes:     20
  Total GPUs:           80

Workload Characteristics:
  Jobs per day:         250.5
  Avg concurrent jobs:  43.8

TOTAL STORAGE ESTIMATE:
  365-day storage:      131.8 GB

Per-Partition Storage Breakdown:

  Partition: gpu-partition
    Nodes:            10 (10 GPU, 0 CPU)
    GPUs:             80
    Total storage:    82.5 GB

  Partition: cpu-partition
    Nodes:            20 (0 GPU, 20 CPU)
    GPUs:             0
    Total storage:    49.3 GB

Recommended Prometheus Server:
  • Disk Space (Database): 198 GB minimum
                           396 GB recommended (2x for safety)
  • Disk Space (Total):    446 GB (includes ~50 GB for OS/application)
  • RAM:                   24 GB minimum
                           48 GB recommended
  • CPU Cores:             4-8 cores

Scenario Comparisons:
  GPU nodes only:       82.5 GB
  Full cluster:         131.8 GB
  Increase:             59.8% (+49.3 GB)
```

## Key Insights

### Storage is Driven by Job Count, Not Just Node Count

**Three factors affect storage:**

1. **Node Count** → System Metrics (~2.5 GB/node/year)
2. **Job Count** → Job Metrics (~0.5 GB/concurrent job/year) **← Key factor!**
3. **GPU Count** → GPU Metrics (~0.5 GB/GPU/year, GPU nodes only)

### Adding CPU Nodes Impact

**Question:** "Will adding CPU nodes increase storage a lot?"

**Answer depends on job patterns:**
- Similar job load as GPU nodes: +50-70% storage
- Heavy CPU job load (2-3x more jobs): +100-150% storage
- But absolute increase is manageable: typically 50-100 GB/year

**Cost perspective:** Even 200 GB/year is ~$10-100 depending on storage type (trivial compared to monitoring value)

### GPU Configuration Matters

| Configuration | GPUs per Node | Storage per Node |
|---------------|---------------|------------------|
| Standard DGX | 8 | 6.5 GB/year |
| MIG 90GB | 16 | 10.5 GB/year |
| MIG 45GB | 32 | 18.5 GB/year |

## Common Use Cases

### Pre-Deployment Planning

```bash
# Run analysis before deploying jobstats
python3 prometheus_capacity_planner.py --verbose --output-json report.json

# Review estimates and provision Prometheus server accordingly
```

### Cost Optimization

```bash
# Reduce retention period (50% savings)
python3 prometheus_capacity_planner.py --retention-days 180

# Increase scrape interval (50% savings)
python3 prometheus_capacity_planner.py --scrape-interval 60

# Both (75% savings)
python3 prometheus_capacity_planner.py --retention-days 90 --scrape-interval 60
```

### Customer Presentation

1. Run analysis on customer's cluster
2. Export JSON report
3. Show scenario comparisons and cost analysis
4. Make informed deployment decision

## Troubleshooting

### "Failed to get node information from Slurm"

**Solution:**
```bash
# Load Slurm module
source /etc/profile.d/modules.sh
module load slurm

# Verify
sinfo -V
```

### "Could not retrieve job history from sacct"

**This is OK!** Script will use estimated statistics based on node count.

**Estimates:**
- GPU nodes: ~2 jobs/day
- CPU nodes: ~5 jobs/day
- Average duration: 4 hours

### Python version too old

**Need Python 3.6+**

```bash
# Try different versions
python3.6 prometheus_capacity_planner.py
python3.8 prometheus_capacity_planner.py
```

## Pre-Deployment Checklist

### On-Site Setup (5 minutes)

1. **Copy script to customer site:**
   ```bash
   scp prometheus_capacity_planner.py user@slurm-login:/tmp/
   ```

2. **Verify prerequisites:**
   ```bash
   ssh user@slurm-login
   python3 --version  # Need 3.6+
   sinfo -V           # Verify Slurm access
   ```

3. **Run analysis:**
   ```bash
   cd /tmp
   python3 prometheus_capacity_planner.py --verbose --output-json report.json
   ```

### What to Check

- [ ] Node count looks correct
- [ ] GPU count looks reasonable
- [ ] Job statistics analyzed (or estimates used)
- [ ] Storage estimates seem reasonable
- [ ] Scenario comparison displayed

### Customer Discussion Points

1. **Total Storage Estimate** - "For your cluster, we estimate X GB per year"
2. **Scenario Comparison** - Show GPU-only vs full cluster
3. **Cost Perspective** - Compare storage cost to GPU hour cost
4. **What Drives Storage** - Explain job count matters more than node count
5. **Optimization Options** - Discuss if customer has concerns

## Technical Details

### Zero Dependencies

Uses only Python standard library:
- `argparse`, `json`, `subprocess`, `sys`, `re`, `datetime`, `typing`, `collections`, `dataclasses`

**No pip install required!**

### What It Does NOT Need

❌ Prometheus server  
❌ Grafana  
❌ Config files  
❌ Exporters  
❌ pip packages  
❌ Root access  

### Storage Formula

```
Storage (GB) = (time_series × samples_per_day × bytes_per_sample × retention_days) / (1024³)

Where:
  samples_per_day = 86400 / scrape_interval_seconds
  bytes_per_sample = 1.5 (Prometheus TSDB compression)
```

### Time Series Cardinality

| Metric Source | Time Series per Entity |
|---------------|------------------------|
| node_exporter | 1,500 per node |
| cgroup_exporter | 50 per job |
| nvidia_gpu_exporter | 40 per GPU |

## Integration with Jobstats

**Workflow:**
1. **Plan capacity** (this tool) → Get storage estimates
2. **Deploy jobstats** (../automation/) → Install monitoring
3. **Validate deployment** (../automation/tools/) → Verify everything works
4. **Monitor actual usage** → Compare with estimates

## Quick Reference

### Commands

```bash
# Basic analysis
python3 prometheus_capacity_planner.py

# Detailed with export
python3 prometheus_capacity_planner.py --verbose --output-json report.json

# Cost-optimized
python3 prometheus_capacity_planner.py --retention-days 90 --scrape-interval 60
```

### Storage Estimates

| Cluster Size | Typical Storage (365 days) |
|--------------|---------------------------|
| 10-20 nodes | 50-100 GB |
| 20-50 nodes | 100-200 GB |
| 50-100 nodes | 200-400 GB |

### Hardware Recommendations

| Cluster Size | Database Storage | Total Disk (with OS) | RAM | CPU |
|--------------|------------------|----------------------|-----|-----|
| 10-20 nodes | 100-200 GB | 250-450 GB SSD | 8-16 GB | 4 cores |
| 20-50 nodes | 200-500 GB | 450-1000 GB SSD | 16-32 GB | 8 cores |
| 50-100 nodes | 500 GB-1 TB | 1-2 TB SSD | 32-64 GB | 16 cores |

**Notes:**
- Database storage is for Prometheus TSDB only (2x estimated for safety)
- Total disk includes ~50 GB overhead for OS, Prometheus binary, and working space
- RAM minimum is 4 GB; actual needs scale with active time series (~1.5 KB per series)
- Always provision 2x estimated database storage for safety margin

## Support

For issues or questions:
1. Run with `--verbose` flag for detailed diagnostics
2. Verify Python 3.6+: `python3 --version`
3. Check Slurm access: `sinfo -V`
4. See main project documentation: [../README.md](../README.md)

---

## Sources

All capacity planning estimates in this tool are based on information from the following sources:

### Prometheus Official Documentation
- **Prometheus Storage Documentation**: [https://prometheus.io/docs/prometheus/latest/storage/](https://prometheus.io/docs/prometheus/latest/storage/)
  - Storage formula and TSDB architecture
  - Compression efficiency (~1-2 bytes per sample)
  - Capacity planning guidelines

### Prometheus Community Resources
- **Robust Perception Blog**: [https://www.robustperception.io/](https://www.robustperception.io/)
  - Prometheus capacity planning best practices
  - Time series cardinality management
  - Storage optimization techniques

- **Prometheus Community Capacity Planning Guides**
  - General guidance: 1-2 KB RAM per active time series
  - Disk I/O and performance considerations

### Exporter Repositories
- **node_exporter**: [https://github.com/prometheus/node_exporter](https://github.com/prometheus/node_exporter)
  - Standard system metrics exporter
  - Typical cardinality: ~1,000-2,000 time series per node

- **cgroup_exporter**: [https://github.com/plazonic/cgroup_exporter](https://github.com/plazonic/cgroup_exporter)
  - Slurm cgroup metrics for job monitoring
  - Typical cardinality: ~30-50 time series per job

- **nvidia_gpu_prometheus_exporter**: [https://github.com/plazonic/nvidia_gpu_prometheus_exporter](https://github.com/plazonic/nvidia_gpu_prometheus_exporter)
  - NVIDIA GPU metrics via nvidia-smi
  - Typical cardinality: ~30-40 time series per GPU

### Metric Cardinality Estimates

The time series estimates used in this tool are conservative (slightly higher than typical) to ensure adequate provisioning:

| Metric Source | Estimate Used | Typical Range | Basis |
|---------------|---------------|---------------|-------|
| node_exporter | 1,500 per node | 1,000-2,000 | Prometheus node_exporter documentation and empirical testing |
| cgroup_exporter | 50 per job | 30-50 | plazonic/cgroup_exporter with --collect.fullslurm flag |
| nvidia_gpu_exporter | 40 per GPU | 30-40 | plazonic/nvidia_gpu_prometheus_exporter with job tracking |
| Bytes per sample | 1.5 bytes | 1-2 bytes | Prometheus TSDB compression (documented) |

### Verification Methods

You can verify actual cardinality on your system:

```bash
# Check node_exporter metrics count
curl -s http://node:9100/metrics | grep -c "^[a-z]"

# Check cgroup_exporter metrics (with jobs running)
curl -s http://node:9306/metrics | grep "jobid=" | cut -d'{' -f1 | sort -u | wc -l

# Check GPU exporter metrics
curl -s http://node:9445/metrics | grep -c "^[a-z]"

# Check actual Prometheus active time series
curl -s http://prometheus:9090/api/v1/query?query=prometheus_tsdb_head_series
```

### Adjusting Estimates

The cardinality constants are defined at the top of the `PrometheusCapacityPlanner` class and can be adjusted based on your actual measurements:

```python
NODE_EXPORTER_SERIES_PER_NODE = 1500  # Adjust based on your node_exporter config
CGROUP_SERIES_PER_JOB = 50            # Adjust based on your cgroup_exporter config
GPU_SERIES_PER_GPU = 30               # Adjust based on your GPU exporter config
GPU_JOB_SERIES_PER_GPU = 10           # Job ownership tracking metrics
BYTES_PER_SAMPLE = 1.5                # Prometheus TSDB compression average
```

**Note**: Estimates are intentionally conservative to prevent under-provisioning. Actual storage requirements may be 10-20% lower depending on your specific configuration and workload patterns.

---

**Ready to plan your Prometheus capacity? Just run `prometheus_capacity_planner.py`!** 🚀