#!/usr/bin/env python3
"""
Prometheus Capacity Planning Tool for Jobstats

This script analyzes Slurm cluster configuration and historical job data to estimate
Prometheus storage requirements for the jobstats monitoring platform.

STANDALONE DEPLOYMENT:
- Zero external dependencies (Python 3.6+ stdlib only)
- No Prometheus server required
- No config files needed
- Just copy this single file and run!

Requirements:
- Python 3.6+ (standard on modern Linux)
- Slurm commands: sinfo (required), sacct (optional)

It considers:
- Node count and types (GPU vs CPU nodes)
- GPU configuration (standard, MIG 90GB, MIG 45GB)
- Historical job patterns and concurrency
- Partition-specific workload characteristics
- Configurable retention periods and scrape intervals

Usage:
    # Basic usage with default settings
    python3 prometheus_capacity_planner.py

    # Specify custom retention and scrape interval
    python3 prometheus_capacity_planner.py --retention-days 180 --scrape-interval 15

    # Analyze specific time period for job history
    python3 prometheus_capacity_planner.py --analysis-days 30

    # Output detailed JSON report
    python3 prometheus_capacity_planner.py --output-json capacity_report.json

    # Verbose mode with detailed breakdown
    python3 prometheus_capacity_planner.py --verbose

Pre-Deployment:
    # Copy to customer site (no other files needed!)
    scp prometheus_capacity_planner.py user@slurm-login:/tmp/
    ssh user@slurm-login
    python3 /tmp/prometheus_capacity_planner.py --verbose

Author: AI Assistant for NVIDIA Jobstats Deployment
Date: 2025-10-06
"""

import argparse
import json
import subprocess
import sys
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    END = '\033[0m'


@dataclass
class NodeConfig:
    """Configuration for a compute node."""
    hostname: str
    partition: str
    state: str
    cpus: int
    memory_mb: int
    gpus: int
    gpu_type: str  # 'none', 'standard', 'mig_90gb', 'mig_45gb'
    is_gpu_node: bool


@dataclass
class MetricEstimate:
    """Estimate for a specific metric category."""
    category: str
    time_series_count: int
    samples_per_day: int
    bytes_per_sample: float
    daily_storage_mb: float
    yearly_storage_gb: float


@dataclass
class CapacityEstimate:
    """Complete capacity estimate for Prometheus."""
    cluster_name: str
    total_nodes: int
    gpu_nodes: int
    cpu_nodes: int
    total_gpus: int
    scrape_interval_seconds: int
    retention_days: int
    
    # Job statistics
    avg_concurrent_jobs: float
    max_concurrent_jobs: int
    jobs_per_day: float
    avg_job_duration_hours: float
    
    # Storage estimates
    system_metrics: MetricEstimate
    job_metrics: MetricEstimate
    gpu_metrics: MetricEstimate
    total_time_series: int
    total_daily_storage_mb: float
    total_storage_gb: float
    
    # Per-partition breakdown
    partition_estimates: Dict[str, Dict]


class PrometheusCapacityPlanner:
    """Analyzes Slurm cluster and estimates Prometheus storage requirements."""
    
    # Metric cardinality estimates (time series per entity)
    NODE_EXPORTER_SERIES_PER_NODE = 1500  # System metrics per node
    CGROUP_SERIES_PER_JOB = 50  # CPU/memory metrics per job
    GPU_SERIES_PER_GPU = 30  # GPU metrics per GPU
    GPU_JOB_SERIES_PER_GPU = 10  # GPU job ownership metrics per GPU
    
    # Storage constants
    BYTES_PER_SAMPLE = 1.5  # Average bytes per sample in Prometheus TSDB
    SECONDS_PER_DAY = 86400
    
    def __init__(self, 
                 retention_days: int = 365,
                 scrape_interval: int = 30,
                 analysis_days: int = 30,
                 verbose: bool = False):
        """Initialize the capacity planner."""
        self.retention_days = retention_days
        self.scrape_interval = scrape_interval
        self.analysis_days = analysis_days
        self.verbose = verbose
        
        self.nodes: List[NodeConfig] = []
        self.job_stats: Dict = {}
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message with color coding."""
        if level == "DEBUG" and not self.verbose:
            return
            
        color_map = {
            "INFO": Colors.BLUE,
            "SUCCESS": Colors.GREEN,
            "WARNING": Colors.YELLOW,
            "ERROR": Colors.RED,
            "HEADER": Colors.BOLD + Colors.CYAN
        }
        
        color = color_map.get(level, "")
        print(f"{color}{message}{Colors.END}")
    
    def run_command(self, command: str) -> Tuple[bool, str]:
        """Run a shell command and return success status and output."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def detect_gpu_type(self, node: str) -> Tuple[int, str]:
        """
        Detect GPU count and type (standard, MIG 90GB, MIG 45GB).
        
        Returns:
            Tuple of (gpu_count, gpu_type)
        """
        # Try to get GPU info from scontrol
        success, output = self.run_command(f"scontrol show node {node}")
        if not success:
            return 0, 'none'
        
        # Try CfgTRES first (most reliable)
        tres_match = re.search(r'CfgTRES=.*?gres/gpu=(\d+)', output)
        if tres_match:
            gpu_count = int(tres_match.group(1))
        else:
            # Fallback to Gres field - try multiple formats
            # Formats: Gres=gpu:1, Gres=gpu:A100:1(S:0), etc.
            gres_match = re.search(r'Gres=gpu[=:](?:[^:=]+:)?(\d+)', output)
            if not gres_match:
                return 0, 'none'
            gpu_count = int(gres_match.group(1))
        
        # Detect MIG configuration by GPU count patterns
        # Standard DGX: 8 GPUs
        # MIG 90GB: 16 instances (2 per physical GPU)
        # MIG 45GB: 32 instances (4 per physical GPU)
        if gpu_count == 8:
            return gpu_count, 'standard'
        elif gpu_count == 16:
            return gpu_count, 'mig_90gb'
        elif gpu_count == 32:
            return gpu_count, 'mig_45gb'
        else:
            # Unknown configuration, treat as standard
            return gpu_count, 'standard'
    
    def gather_node_info(self):
        """Gather information about all compute nodes in the cluster."""
        self.log("\n" + "="*80, "HEADER")
        self.log("GATHERING CLUSTER NODE INFORMATION", "HEADER")
        self.log("="*80, "HEADER")
        
        # Get node list from sinfo
        cmd = "sinfo -N -h -o '%N|%R|%T|%c|%m|%G'"
        success, output = self.run_command(cmd)
        
        if not success:
            self.log("Failed to get node information from Slurm", "ERROR")
            self.log("Make sure Slurm is installed and you have access to sinfo", "ERROR")
            sys.exit(1)
        
        node_dict = {}  # Use dict to deduplicate nodes across partitions
        
        for line in output.split('\n'):
            if not line.strip():
                continue
                
            parts = line.split('|')
            if len(parts) < 6:
                continue
            
            hostname = parts[0].strip()
            partition = parts[1].strip()
            state = parts[2].strip()
            cpus = int(parts[3].strip()) if parts[3].strip().isdigit() else 0
            memory_mb = int(parts[4].strip()) if parts[4].strip().isdigit() else 0
            gres = parts[5].strip()
            
            # Parse GPU count from gres
            # Try multiple formats: gpu:A100:1(S:0), gpu:1, etc.
            gpu_count = 0
            if 'gpu:' in gres or 'gpu=' in gres:
                # Match patterns like: gpu:1, gpu:A100:1, gpu=1, etc.
                match = re.search(r'gpu[=:](?:[^:=]+:)?(\d+)', gres)
                if match:
                    gpu_count = int(match.group(1))
            
            # If still no GPU found, try CfgTRES from scontrol
            if gpu_count == 0:
                success, node_output = self.run_command(f"scontrol show node {hostname}")
                if success:
                    # Look for CfgTRES=...gres/gpu=N
                    tres_match = re.search(r'CfgTRES=.*?gres/gpu=(\d+)', node_output)
                    if tres_match:
                        gpu_count = int(tres_match.group(1))
            
            # Detect GPU type
            if gpu_count > 0:
                gpu_count, gpu_type = self.detect_gpu_type(hostname)
                is_gpu_node = True
            else:
                gpu_type = 'none'
                is_gpu_node = False
            
            # Store node info (will update partition if node appears multiple times)
            if hostname not in node_dict:
                node_dict[hostname] = NodeConfig(
                    hostname=hostname,
                    partition=partition,
                    state=state,
                    cpus=cpus,
                    memory_mb=memory_mb,
                    gpus=gpu_count,
                    gpu_type=gpu_type,
                    is_gpu_node=is_gpu_node
                )
            else:
                # Node in multiple partitions, append partition name
                existing = node_dict[hostname]
                if partition not in existing.partition:
                    existing.partition += f",{partition}"
        
        self.nodes = list(node_dict.values())
        
        # Print summary
        gpu_nodes = [n for n in self.nodes if n.is_gpu_node]
        cpu_nodes = [n for n in self.nodes if not n.is_gpu_node]
        total_gpus = sum(n.gpus for n in self.nodes)
        
        self.log(f"\n✓ Found {len(self.nodes)} compute nodes:", "SUCCESS")
        self.log(f"  • GPU nodes: {len(gpu_nodes)}", "INFO")
        self.log(f"  • CPU-only nodes: {len(cpu_nodes)}", "INFO")
        self.log(f"  • Total GPUs: {total_gpus}", "INFO")
        
        # GPU type breakdown
        if gpu_nodes:
            self.log(f"\n  GPU Configuration Breakdown:", "INFO")
            gpu_types = defaultdict(int)
            gpu_counts = defaultdict(int)
            for node in gpu_nodes:
                gpu_types[node.gpu_type] += 1
                gpu_counts[node.gpu_type] += node.gpus
            
            for gpu_type, count in sorted(gpu_types.items()):
                type_name = {
                    'standard': 'Standard (8 GPUs/node)',
                    'mig_90gb': 'MIG 90GB (16 instances/node)',
                    'mig_45gb': 'MIG 45GB (32 instances/node)'
                }.get(gpu_type, gpu_type)
                self.log(f"    - {type_name}: {count} nodes, {gpu_counts[gpu_type]} GPUs", "INFO")
        
        if self.verbose:
            self.log("\n  Node Details:", "DEBUG")
            for node in self.nodes[:10]:  # Show first 10 nodes
                gpu_info = f"{node.gpus} GPUs ({node.gpu_type})" if node.is_gpu_node else "CPU-only"
                self.log(f"    {node.hostname}: {node.cpus} CPUs, {gpu_info}, partition={node.partition}", "DEBUG")
            if len(self.nodes) > 10:
                self.log(f"    ... and {len(self.nodes) - 10} more nodes", "DEBUG")
    
    def gather_job_statistics(self):
        """Gather historical job statistics from Slurm accounting."""
        self.log("\n" + "="*80, "HEADER")
        self.log("ANALYZING HISTORICAL JOB PATTERNS", "HEADER")
        self.log("="*80, "HEADER")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.analysis_days)
        
        self.log(f"\nAnalyzing jobs from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", "INFO")
        
        # Get job data from sacct
        # Format: JobID|Partition|State|Start|End|AllocCPUS|AllocNodes|AllocTRES
        # Note: Using AllocTRES instead of deprecated AllocGRES (Slurm 23.11+)
        cmd = (
            f"sacct -a -P -n "
            f"--starttime={start_date.strftime('%Y-%m-%d')} "
            f"--endtime={end_date.strftime('%Y-%m-%d')} "
            f"--format=JobID,Partition,State,Start,End,AllocCPUS,AllocNodes,AllocTRES "
            f"--state=COMPLETED,FAILED,CANCELLED,TIMEOUT"
        )
        
        success, output = self.run_command(cmd)
        
        if not success:
            self.log("Warning: Could not retrieve job history from sacct", "WARNING")
            self.log("Using estimated job statistics instead", "WARNING")
            self._use_estimated_job_stats()
            return
        
        # Parse job data
        jobs = []
        for line in output.split('\n'):
            if not line.strip() or '.batch' in line or '.extern' in line:
                continue
            
            parts = line.split('|')
            if len(parts) < 8:
                continue
            
            try:
                job_id = parts[0].strip()
                partition = parts[1].strip()
                state = parts[2].strip()
                start_time = parts[3].strip()
                end_time = parts[4].strip()
                alloc_cpus = int(parts[5].strip()) if parts[5].strip().isdigit() else 0
                alloc_nodes = int(parts[6].strip()) if parts[6].strip().isdigit() else 0
                alloc_tres = parts[7].strip()
                
                # Parse GPU allocation from AllocTRES
                # Format: billing=8,cpu=8,mem=240G,node=1,gres/gpu=1
                # or: cpu=8,mem=240G,node=1,gres/gpu:a100=1
                alloc_gpus = 0
                if 'gres/gpu' in alloc_tres:
                    # Match patterns like: gres/gpu=1, gres/gpu:a100=2, etc.
                    match = re.search(r'gres/gpu[^=]*=(\d+)', alloc_tres)
                    if match:
                        alloc_gpus = int(match.group(1))
                
                # Calculate duration
                if start_time != 'Unknown' and end_time != 'Unknown':
                    try:
                        start_dt = datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S')
                        end_dt = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S')
                        duration_hours = (end_dt - start_dt).total_seconds() / 3600
                    except:
                        duration_hours = 1.0  # Default
                else:
                    duration_hours = 1.0
                
                jobs.append({
                    'job_id': job_id,
                    'partition': partition,
                    'state': state,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration_hours': duration_hours,
                    'alloc_cpus': alloc_cpus,
                    'alloc_nodes': alloc_nodes,
                    'alloc_gpus': alloc_gpus,
                    'is_gpu_job': alloc_gpus > 0
                })
            except Exception as e:
                if self.verbose:
                    self.log(f"Warning: Could not parse job line: {line[:50]}... ({e})", "DEBUG")
                continue
        
        if not jobs:
            self.log("No job history found, using estimates", "WARNING")
            self._use_estimated_job_stats()
            return
        
        # Calculate statistics
        total_jobs = len(jobs)
        gpu_jobs = [j for j in jobs if j['is_gpu_job']]
        cpu_jobs = [j for j in jobs if not j['is_gpu_job']]
        
        avg_duration = sum(j['duration_hours'] for j in jobs) / len(jobs) if jobs else 1.0
        jobs_per_day = total_jobs / self.analysis_days
        
        # Calculate concurrent jobs (approximate)
        # This is a simplified calculation - for exact concurrency we'd need to analyze overlaps
        avg_concurrent = (jobs_per_day * avg_duration) / 24
        max_concurrent = int(avg_concurrent * 2)  # Rough estimate of peak
        
        # Per-partition statistics
        partition_stats = defaultdict(lambda: {'jobs': 0, 'gpu_jobs': 0, 'cpu_jobs': 0, 'total_duration': 0})
        for job in jobs:
            p = job['partition']
            partition_stats[p]['jobs'] += 1
            if job['is_gpu_job']:
                partition_stats[p]['gpu_jobs'] += 1
            else:
                partition_stats[p]['cpu_jobs'] += 1
            partition_stats[p]['total_duration'] += job['duration_hours']
        
        self.job_stats = {
            'total_jobs': total_jobs,
            'gpu_jobs': len(gpu_jobs),
            'cpu_jobs': len(cpu_jobs),
            'avg_duration_hours': avg_duration,
            'jobs_per_day': jobs_per_day,
            'avg_concurrent_jobs': avg_concurrent,
            'max_concurrent_jobs': max_concurrent,
            'partition_stats': dict(partition_stats)
        }
        
        # Print summary
        self.log(f"\n✓ Analyzed {total_jobs} jobs over {self.analysis_days} days:", "SUCCESS")
        self.log(f"  • GPU jobs: {len(gpu_jobs)} ({len(gpu_jobs)/total_jobs*100:.1f}%)", "INFO")
        self.log(f"  • CPU jobs: {len(cpu_jobs)} ({len(cpu_jobs)/total_jobs*100:.1f}%)", "INFO")
        self.log(f"  • Average job duration: {avg_duration:.1f} hours", "INFO")
        self.log(f"  • Jobs per day: {jobs_per_day:.1f}", "INFO")
        self.log(f"  • Estimated avg concurrent jobs: {avg_concurrent:.1f}", "INFO")
        self.log(f"  • Estimated peak concurrent jobs: {max_concurrent}", "INFO")
        
        if self.verbose and partition_stats:
            self.log(f"\n  Per-Partition Breakdown:", "DEBUG")
            for partition, stats in sorted(partition_stats.items()):
                avg_dur = stats['total_duration'] / stats['jobs'] if stats['jobs'] > 0 else 0
                self.log(f"    {partition}: {stats['jobs']} jobs, "
                        f"{stats['gpu_jobs']} GPU, {stats['cpu_jobs']} CPU, "
                        f"avg duration {avg_dur:.1f}h", "DEBUG")
    
    def _use_estimated_job_stats(self):
        """Use estimated job statistics when historical data is unavailable."""
        # Conservative estimates based on typical HPC workloads
        gpu_nodes = len([n for n in self.nodes if n.is_gpu_node])
        cpu_nodes = len([n for n in self.nodes if not n.is_gpu_node])
        
        # Assume GPU nodes run ~2 jobs/day, CPU nodes run ~5 jobs/day
        jobs_per_day = (gpu_nodes * 2) + (cpu_nodes * 5)
        avg_duration = 4.0  # 4 hours average
        avg_concurrent = (jobs_per_day * avg_duration) / 24
        
        self.job_stats = {
            'total_jobs': int(jobs_per_day * self.analysis_days),
            'gpu_jobs': int(gpu_nodes * 2 * self.analysis_days),
            'cpu_jobs': int(cpu_nodes * 5 * self.analysis_days),
            'avg_duration_hours': avg_duration,
            'jobs_per_day': jobs_per_day,
            'avg_concurrent_jobs': avg_concurrent,
            'max_concurrent_jobs': int(avg_concurrent * 2),
            'partition_stats': {}
        }
        
        self.log(f"  Using estimated statistics:", "INFO")
        self.log(f"  • Estimated jobs per day: {jobs_per_day:.1f}", "INFO")
        self.log(f"  • Estimated avg concurrent jobs: {avg_concurrent:.1f}", "INFO")
    
    def calculate_capacity_estimate(self) -> CapacityEstimate:
        """Calculate comprehensive capacity estimate."""
        self.log("\n" + "="*80, "HEADER")
        self.log("CALCULATING PROMETHEUS STORAGE REQUIREMENTS", "HEADER")
        self.log("="*80, "HEADER")
        
        # Node counts
        gpu_nodes = [n for n in self.nodes if n.is_gpu_node]
        cpu_nodes = [n for n in self.nodes if not n.is_gpu_node]
        total_gpus = sum(n.gpus for n in self.nodes)
        
        # Samples per day
        samples_per_day = self.SECONDS_PER_DAY / self.scrape_interval
        
        # 1. System Metrics (node_exporter) - per node, always active
        system_series = len(self.nodes) * self.NODE_EXPORTER_SERIES_PER_NODE
        system_daily_mb = (system_series * samples_per_day * self.BYTES_PER_SAMPLE) / (1024 * 1024)
        system_yearly_gb = (system_daily_mb * self.retention_days) / 1024
        
        system_metrics = MetricEstimate(
            category="System Metrics (node_exporter)",
            time_series_count=system_series,
            samples_per_day=int(samples_per_day),
            bytes_per_sample=self.BYTES_PER_SAMPLE,
            daily_storage_mb=system_daily_mb,
            yearly_storage_gb=system_yearly_gb
        )
        
        # 2. Job Metrics (cgroup_exporter) - per concurrent job
        avg_concurrent = self.job_stats['avg_concurrent_jobs']
        job_series = int(avg_concurrent * self.CGROUP_SERIES_PER_JOB)
        job_daily_mb = (job_series * samples_per_day * self.BYTES_PER_SAMPLE) / (1024 * 1024)
        job_yearly_gb = (job_daily_mb * self.retention_days) / 1024
        
        job_metrics = MetricEstimate(
            category="Job Metrics (cgroup_exporter)",
            time_series_count=job_series,
            samples_per_day=int(samples_per_day),
            bytes_per_sample=self.BYTES_PER_SAMPLE,
            daily_storage_mb=job_daily_mb,
            yearly_storage_gb=job_yearly_gb
        )
        
        # 3. GPU Metrics (nvidia_gpu_exporter) - per GPU
        gpu_series = total_gpus * (self.GPU_SERIES_PER_GPU + self.GPU_JOB_SERIES_PER_GPU)
        gpu_daily_mb = (gpu_series * samples_per_day * self.BYTES_PER_SAMPLE) / (1024 * 1024)
        gpu_yearly_gb = (gpu_daily_mb * self.retention_days) / 1024
        
        gpu_metrics = MetricEstimate(
            category="GPU Metrics (nvidia_gpu_exporter)",
            time_series_count=gpu_series,
            samples_per_day=int(samples_per_day),
            bytes_per_sample=self.BYTES_PER_SAMPLE,
            daily_storage_mb=gpu_daily_mb,
            yearly_storage_gb=gpu_yearly_gb
        )
        
        # Total
        total_series = system_series + job_series + gpu_series
        total_daily_mb = system_daily_mb + job_daily_mb + gpu_daily_mb
        total_yearly_gb = system_yearly_gb + job_yearly_gb + gpu_yearly_gb
        
        # Per-partition estimates
        partition_estimates = self._calculate_partition_estimates()
        
        estimate = CapacityEstimate(
            cluster_name="slurm",
            total_nodes=len(self.nodes),
            gpu_nodes=len(gpu_nodes),
            cpu_nodes=len(cpu_nodes),
            total_gpus=total_gpus,
            scrape_interval_seconds=self.scrape_interval,
            retention_days=self.retention_days,
            avg_concurrent_jobs=avg_concurrent,
            max_concurrent_jobs=self.job_stats['max_concurrent_jobs'],
            jobs_per_day=self.job_stats['jobs_per_day'],
            avg_job_duration_hours=self.job_stats['avg_duration_hours'],
            system_metrics=system_metrics,
            job_metrics=job_metrics,
            gpu_metrics=gpu_metrics,
            total_time_series=total_series,
            total_daily_storage_mb=total_daily_mb,
            total_storage_gb=total_yearly_gb,
            partition_estimates=partition_estimates
        )
        
        return estimate
    
    def _calculate_partition_estimates(self) -> Dict[str, Dict]:
        """Calculate storage estimates per partition."""
        partition_data = defaultdict(lambda: {
            'nodes': [],
            'gpu_nodes': 0,
            'cpu_nodes': 0,
            'total_gpus': 0,
            'jobs': 0,
            'gpu_jobs': 0,
            'cpu_jobs': 0
        })
        
        # Aggregate node data by partition
        for node in self.nodes:
            # Node might be in multiple partitions
            partitions = node.partition.split(',')
            for partition in partitions:
                partition = partition.strip()
                partition_data[partition]['nodes'].append(node)
                if node.is_gpu_node:
                    partition_data[partition]['gpu_nodes'] += 1
                    partition_data[partition]['total_gpus'] += node.gpus
                else:
                    partition_data[partition]['cpu_nodes'] += 1
        
        # Add job statistics
        for partition, stats in self.job_stats.get('partition_stats', {}).items():
            if partition in partition_data:
                partition_data[partition]['jobs'] = stats['jobs']
                partition_data[partition]['gpu_jobs'] = stats['gpu_jobs']
                partition_data[partition]['cpu_jobs'] = stats['cpu_jobs']
        
        # Calculate storage estimates per partition
        samples_per_day = self.SECONDS_PER_DAY / self.scrape_interval
        
        result = {}
        for partition, data in partition_data.items():
            node_count = len(data['nodes'])
            
            # System metrics
            system_series = node_count * self.NODE_EXPORTER_SERIES_PER_NODE
            system_gb = (system_series * samples_per_day * self.BYTES_PER_SAMPLE * 
                        self.retention_days) / (1024 * 1024 * 1024)
            
            # Job metrics (estimate based on job count)
            if data['jobs'] > 0:
                avg_concurrent = (data['jobs'] / self.analysis_days * 
                                self.job_stats['avg_duration_hours']) / 24
            else:
                avg_concurrent = node_count * 0.5  # Estimate
            
            job_series = int(avg_concurrent * self.CGROUP_SERIES_PER_JOB)
            job_gb = (job_series * samples_per_day * self.BYTES_PER_SAMPLE * 
                     self.retention_days) / (1024 * 1024 * 1024)
            
            # GPU metrics
            gpu_series = data['total_gpus'] * (self.GPU_SERIES_PER_GPU + self.GPU_JOB_SERIES_PER_GPU)
            gpu_gb = (gpu_series * samples_per_day * self.BYTES_PER_SAMPLE * 
                     self.retention_days) / (1024 * 1024 * 1024)
            
            result[partition] = {
                'nodes': node_count,
                'gpu_nodes': data['gpu_nodes'],
                'cpu_nodes': data['cpu_nodes'],
                'total_gpus': data['total_gpus'],
                'jobs': data['jobs'],
                'system_storage_gb': round(system_gb, 2),
                'job_storage_gb': round(job_gb, 2),
                'gpu_storage_gb': round(gpu_gb, 2),
                'total_storage_gb': round(system_gb + job_gb + gpu_gb, 2)
            }
        
        return result
    
    def print_report(self, estimate: CapacityEstimate):
        """Print a formatted capacity planning report."""
        self.log("\n" + "="*80, "HEADER")
        self.log("PROMETHEUS CAPACITY PLANNING REPORT", "HEADER")
        self.log("="*80, "HEADER")
        
        # Cluster Overview
        self.log(f"\n{Colors.BOLD}Cluster Configuration:{Colors.END}", "INFO")
        self.log(f"  Total Nodes:          {estimate.total_nodes}", "INFO")
        self.log(f"  • GPU Nodes:          {estimate.gpu_nodes}", "INFO")
        self.log(f"  • CPU-Only Nodes:     {estimate.cpu_nodes}", "INFO")
        self.log(f"  Total GPUs:           {estimate.total_gpus}", "INFO")
        
        # Workload Characteristics
        self.log(f"\n{Colors.BOLD}Workload Characteristics:{Colors.END}", "INFO")
        self.log(f"  Jobs per day:         {estimate.jobs_per_day:.1f}", "INFO")
        self.log(f"  Avg job duration:     {estimate.avg_job_duration_hours:.1f} hours", "INFO")
        self.log(f"  Avg concurrent jobs:  {estimate.avg_concurrent_jobs:.1f}", "INFO")
        self.log(f"  Peak concurrent jobs: {estimate.max_concurrent_jobs}", "INFO")
        
        # Prometheus Configuration
        self.log(f"\n{Colors.BOLD}Prometheus Configuration:{Colors.END}", "INFO")
        self.log(f"  Scrape interval:      {estimate.scrape_interval_seconds} seconds", "INFO")
        self.log(f"  Retention period:     {estimate.retention_days} days", "INFO")
        self.log(f"  Samples per day:      {estimate.system_metrics.samples_per_day:,}", "INFO")
        
        # Storage Breakdown
        self.log(f"\n{Colors.BOLD}Storage Requirements Breakdown:{Colors.END}", "INFO")
        self.log(f"\n  1. System Metrics (node_exporter):", "INFO")
        self.log(f"     • Time series:     {estimate.system_metrics.time_series_count:,}", "INFO")
        self.log(f"     • Daily storage:   {estimate.system_metrics.daily_storage_mb:.1f} MB", "INFO")
        self.log(f"     • {estimate.retention_days}-day storage: {estimate.system_metrics.yearly_storage_gb:.1f} GB", "SUCCESS")
        
        self.log(f"\n  2. Job Metrics (cgroup_exporter):", "INFO")
        self.log(f"     • Time series:     {estimate.job_metrics.time_series_count:,} (avg concurrent)", "INFO")
        self.log(f"     • Daily storage:   {estimate.job_metrics.daily_storage_mb:.1f} MB", "INFO")
        self.log(f"     • {estimate.retention_days}-day storage: {estimate.job_metrics.yearly_storage_gb:.1f} GB", "SUCCESS")
        
        self.log(f"\n  3. GPU Metrics (nvidia_gpu_exporter):", "INFO")
        self.log(f"     • Time series:     {estimate.gpu_metrics.time_series_count:,}", "INFO")
        self.log(f"     • Daily storage:   {estimate.gpu_metrics.daily_storage_mb:.1f} MB", "INFO")
        self.log(f"     • {estimate.retention_days}-day storage: {estimate.gpu_metrics.yearly_storage_gb:.1f} GB", "SUCCESS")
        
        # Total
        self.log(f"\n{Colors.BOLD}{Colors.GREEN}TOTAL STORAGE ESTIMATE:{Colors.END}", "SUCCESS")
        self.log(f"  Active time series:   {estimate.total_time_series:,}", "SUCCESS")
        self.log(f"  Daily storage:        {estimate.total_daily_storage_mb:.1f} MB/day", "SUCCESS")
        self.log(f"  {estimate.retention_days}-day storage:    {estimate.total_storage_gb:.1f} GB", "SUCCESS")
        
        # Per-partition breakdown (always show if partitions exist)
        if estimate.partition_estimates:
            self.log(f"\n{Colors.BOLD}Per-Partition Storage Breakdown:{Colors.END}", "INFO")
            for partition, data in sorted(estimate.partition_estimates.items()):
                self.log(f"\n  Partition: {partition}", "INFO")
                self.log(f"    Nodes:            {data['nodes']} ({data['gpu_nodes']} GPU, {data['cpu_nodes']} CPU)", "INFO")
                self.log(f"    GPUs:             {data['total_gpus']}", "INFO")
                if self.verbose:
                    self.log(f"    Jobs analyzed:    {data['jobs']}", "INFO")
                    self.log(f"    System metrics:   {data['system_storage_gb']:.1f} GB", "INFO")
                    self.log(f"    Job metrics:      {data['job_storage_gb']:.1f} GB", "INFO")
                    self.log(f"    GPU metrics:      {data['gpu_storage_gb']:.1f} GB", "INFO")
                self.log(f"    Total storage:    {data['total_storage_gb']:.1f} GB", "SUCCESS")
        
        # Recommendations
        self.log(f"\n{Colors.BOLD}Recommended Prometheus Server Specifications:{Colors.END}", "INFO")
        
        # Disk space breakdown
        # Database storage
        recommended_db_disk = estimate.total_storage_gb * 1.5
        self.log(f"  • Disk Space (Database): {recommended_db_disk:.0f} GB minimum", "INFO")
        self.log(f"                           {recommended_db_disk * 2:.0f} GB recommended (2x for safety)", "INFO")
        
        # OS and application overhead
        os_overhead = 50  # GB for OS, Prometheus binary, and working space
        total_disk = (recommended_db_disk * 2) + os_overhead
        self.log(f"  • Disk Space (Total):    {total_disk:.0f} GB (includes ~{os_overhead} GB for OS/application)", "INFO")
        
        # RAM (rough estimate: 1-2 KB per active time series)
        # Formula: time_series * 1.5 KB / 1024 = GB
        recommended_ram_gb = (estimate.total_time_series * 1.5) / 1024
        # Ensure minimum of 4 GB
        recommended_ram_gb = max(recommended_ram_gb, 4)
        self.log(f"  • RAM:                   {recommended_ram_gb:.0f} GB minimum", "INFO")
        self.log(f"                           {max(recommended_ram_gb * 2, 8):.0f} GB recommended", "INFO")
        
        # CPU
        self.log(f"  • CPU Cores:             4-8 cores recommended", "INFO")
        
        # Comparison scenarios
        self.log(f"\n{Colors.BOLD}Scenario Comparisons:{Colors.END}", "INFO")
        
        # GPU-only vs Full cluster
        gpu_only_nodes = estimate.gpu_nodes
        gpu_only_storage = self._calculate_scenario_storage(gpu_only_nodes, estimate.total_gpus, estimate)
        
        self.log(f"\n  Scenario 1: GPU nodes only ({gpu_only_nodes} nodes)", "INFO")
        self.log(f"    Estimated storage:  {gpu_only_storage:.1f} GB", "INFO")
        
        self.log(f"\n  Scenario 2: Full cluster ({estimate.total_nodes} nodes)", "INFO")
        self.log(f"    Estimated storage:  {estimate.total_storage_gb:.1f} GB", "INFO")
        
        increase_pct = ((estimate.total_storage_gb - gpu_only_storage) / gpu_only_storage * 100) if gpu_only_storage > 0 else 0
        self.log(f"\n  Adding CPU nodes increases storage by: {increase_pct:.1f}%", "WARNING" if increase_pct > 50 else "INFO")
        self.log(f"  Additional storage needed: {estimate.total_storage_gb - gpu_only_storage:.1f} GB", "INFO")
        
        # Notes
        self.log(f"\n{Colors.BOLD}Important Notes:{Colors.END}", "INFO")
        self.log(f"  • Storage estimates include {estimate.retention_days} days of retention", "INFO")
        self.log(f"  • Actual storage may vary based on workload patterns", "INFO")
        self.log(f"  • Prometheus TSDB compression is very efficient (~1.5 bytes/sample)", "INFO")
        self.log(f"  • Consider monitoring prometheus_tsdb_storage_blocks_bytes metric", "INFO")
        self.log(f"  • Plan for 2x estimated storage for safety margin", "INFO")
        
        self.log("\n" + "="*80, "HEADER")
    
    def _calculate_scenario_storage(self, nodes: int, gpus: int, estimate: CapacityEstimate) -> float:
        """Calculate storage for a specific scenario."""
        samples_per_day = self.SECONDS_PER_DAY / self.scrape_interval
        
        # System metrics
        system_series = nodes * self.NODE_EXPORTER_SERIES_PER_NODE
        system_gb = (system_series * samples_per_day * self.BYTES_PER_SAMPLE * 
                    self.retention_days) / (1024 * 1024 * 1024)
        
        # Job metrics (proportional to nodes)
        job_series = int((estimate.avg_concurrent_jobs * nodes / estimate.total_nodes) * 
                        self.CGROUP_SERIES_PER_JOB)
        job_gb = (job_series * samples_per_day * self.BYTES_PER_SAMPLE * 
                 self.retention_days) / (1024 * 1024 * 1024)
        
        # GPU metrics
        gpu_series = gpus * (self.GPU_SERIES_PER_GPU + self.GPU_JOB_SERIES_PER_GPU)
        gpu_gb = (gpu_series * samples_per_day * self.BYTES_PER_SAMPLE * 
                 self.retention_days) / (1024 * 1024 * 1024)
        
        return system_gb + job_gb + gpu_gb
    
    def export_json(self, estimate: CapacityEstimate, output_file: str):
        """Export capacity estimate to JSON file."""
        data = asdict(estimate)
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.log(f"\n✓ Capacity report exported to: {output_file}", "SUCCESS")
    
    def run(self, output_json: Optional[str] = None):
        """Run the complete capacity planning analysis."""
        self.log(f"\n{Colors.BOLD}{Colors.CYAN}Prometheus Capacity Planning Tool for Jobstats{Colors.END}", "HEADER")
        self.log(f"{Colors.CYAN}Analyzing Slurm cluster and estimating storage requirements{Colors.END}\n", "HEADER")
        
        # Gather data
        self.gather_node_info()
        self.gather_job_statistics()
        
        # Calculate estimate
        estimate = self.calculate_capacity_estimate()
        
        # Print report
        self.print_report(estimate)
        
        # Export JSON if requested
        if output_json:
            self.export_json(estimate, output_json)
        
        self.log(f"\n{Colors.GREEN}✓ Capacity planning analysis complete!{Colors.END}\n", "SUCCESS")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Prometheus Capacity Planning Tool for Jobstats',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with defaults (365 days retention, 30s scrape interval)
  %(prog)s

  # Custom retention period
  %(prog)s --retention-days 180

  # Custom scrape interval (in seconds)
  %(prog)s --scrape-interval 15

  # Analyze longer job history period
  %(prog)s --analysis-days 60

  # Export detailed JSON report
  %(prog)s --output-json capacity_report.json

  # Verbose output with partition breakdown
  %(prog)s --verbose

  # Complete example
  %(prog)s --retention-days 365 --scrape-interval 30 --analysis-days 30 --output-json report.json --verbose
        """
    )
    
    parser.add_argument(
        '--retention-days',
        type=int,
        default=365,
        help='Prometheus retention period in days (default: 365)'
    )
    
    parser.add_argument(
        '--scrape-interval',
        type=int,
        default=30,
        help='Prometheus scrape interval in seconds (default: 30)'
    )
    
    parser.add_argument(
        '--analysis-days',
        type=int,
        default=30,
        help='Number of days of job history to analyze (default: 30)'
    )
    
    parser.add_argument(
        '--output-json',
        type=str,
        help='Export detailed report to JSON file'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output with detailed breakdowns'
    )
    
    args = parser.parse_args()
    
    # Create planner and run
    planner = PrometheusCapacityPlanner(
        retention_days=args.retention_days,
        scrape_interval=args.scrape_interval,
        analysis_days=args.analysis_days,
        verbose=args.verbose
    )
    
    try:
        planner.run(output_json=args.output_json)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Analysis interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
