#!/usr/bin/env python3
"""
BCM Jobstats Deployment Validation Script

This script validates that the jobstats deployment is working correctly across all nodes.
It checks services, ports, metrics endpoints, Prometheus targets, and Slurm integration.

Usage:
    python3 validate_jobstats_deployment.py [--config CONFIG_FILE] [--verbose]
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import urllib.request
import urllib.error


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


class JobstatsValidator:
    """Validates jobstats deployment across all nodes."""
    
    def __init__(self, config_file: str = "automation/configs/config.json", verbose: bool = False):
        """Initialize the validator with configuration."""
        self.config_file = config_file
        self.verbose = verbose
        self.config = self._load_config()
        self.results = {
            'passed': 0,
            'failed': 0,
            'warnings': 0,
            'total': 0
        }
        
    def _load_config(self) -> Dict:
        """Load configuration from JSON file."""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            self._log(f"Loaded configuration from {self.config_file}", "INFO")
            return config
        except FileNotFoundError:
            self._log(f"Config file {self.config_file} not found, using defaults", "WARNING")
            return self._get_default_config()
        except json.JSONDecodeError as e:
            self._log(f"Error parsing config file: {e}", "ERROR")
            sys.exit(1)
    
    def _get_default_config(self) -> Dict:
        """Get default configuration."""
        return {
            "cluster_name": "slurm",
            "prometheus_server": "prometheus-server",
            "grafana_server": "grafana-server",
            "prometheus_port": 9090,
            "grafana_port": 3000,
            "node_exporter_port": 9100,
            "cgroup_exporter_port": 9306,
            "nvidia_gpu_exporter_port": 9445,
            "systems": {
                "slurm_controller": ["slogin"],
                "login_nodes": ["slogin"],
                "dgx_nodes": ["dgx-01"],
                "prometheus_server": ["statsrv"],
                "grafana_server": ["statsrv"]
            }
        }
    
    def _log(self, message: str, level: str = "INFO"):
        """Log a message with appropriate formatting."""
        if not self.verbose and level == "DEBUG":
            return
            
        timestamp = time.strftime("%H:%M:%S")
        if level == "ERROR":
            print(f"{Colors.RED}[{timestamp}] ERROR: {message}{Colors.END}")
        elif level == "WARNING":
            print(f"{Colors.YELLOW}[{timestamp}] WARNING: {message}{Colors.END}")
        elif level == "DEBUG":
            print(f"{Colors.BLUE}[{timestamp}] DEBUG: {message}{Colors.END}")
        else:
            print(f"[{timestamp}] {message}")
    
    def _run_command(self, command: str, host: Optional[str] = None) -> Tuple[bool, str, str]:
        """Run a command locally or on a remote host."""
        if host:
            full_command = f"ssh {host} '{command}'"
        else:
            full_command = command
            
        self._log(f"Running: {full_command}", "DEBUG")
        
        try:
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def _check_service(self, service: str, host: Optional[str] = None) -> bool:
        """Check if a systemd service is running."""
        success, stdout, stderr = self._run_command(f"systemctl is-active {service}", host)
        return success and stdout.strip() == "active"
    
    def _check_port(self, port: int, host: Optional[str] = None) -> bool:
        """Check if a port is listening."""
        success, stdout, stderr = self._run_command(f"netstat -tlnp | grep ':{port} ' || ss -tlnp | grep ':{port} '", host)
        return success and stdout.strip() != ""
    
    def _check_metrics_endpoint(self, url: str, host: Optional[str] = None) -> Tuple[bool, str]:
        """Check if a metrics endpoint is responding."""
        if host:
            # For remote hosts, we need to check via SSH
            success, stdout, stderr = self._run_command(f"curl -s {url} | head -1", host)
            if success and "# HELP" in stdout:
                return True, stdout
            return False, stderr
        else:
            # For local host, we can use urllib
            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    content = response.read().decode('utf-8')
                    if "# HELP" in content:
                        return True, content.split('\n')[0]
                    return False, "No metrics found"
            except Exception as e:
                return False, str(e)
    
    def _check_file_exists(self, file_path: str, host: Optional[str] = None) -> bool:
        """Check if a file exists."""
        success, stdout, stderr = self._run_command(f"test -f {file_path}", host)
        return success
    
    def _check_bcm_slurm_configuration(self, host: Optional[str] = None) -> Dict[str, bool]:
        """Check BCM-managed Slurm configuration for jobstats."""
        results = {}
        
        # Check BCM prolog/epilog configuration
        success, stdout, stderr = self._run_command('cmsh -c "wlm;get prolog;get epilog;get epilogslurmctld"', host)
        if success:
            # BCM is configured if prolog/epilog point to the correct directories
            # The output has newlines between values, so we check each line
            lines = stdout.strip().split('\n')
            prolog_line = lines[0] if len(lines) > 0 else ""
            epilog_line = lines[1] if len(lines) > 1 else ""
            epilogslurmctld_line = lines[2] if len(lines) > 2 else ""
            
            prolog_configured = "/cm/local/apps/cmd/scripts/prolog" in prolog_line
            epilog_configured = "/cm/local/apps/cmd/scripts/epilog" in epilog_line
            results["BCM prolog/epilog configured"] = prolog_configured and epilog_configured
            results["BCM epilogslurmctld configured"] = "/usr/local/sbin/slurmctldepilog.sh" in epilogslurmctld_line
        else:
            results["BCM prolog/epilog configured"] = False
            results["BCM epilogslurmctld configured"] = False
        
        # Check if jobstats scripts are properly installed
        # Shared scripts should exist on the slurm controller
        shared_prolog = "/cm/shared/apps/slurm/var/cm/prolog-jobstats.sh"
        shared_epilog = "/cm/shared/apps/slurm/var/cm/epilog-jobstats.sh"
        
        results["Shared prolog script exists"] = self._check_file_exists(shared_prolog, host)
        results["Shared epilog script exists"] = self._check_file_exists(shared_epilog, host)
        
        # Check if scripts are executable
        if results["Shared prolog script exists"]:
            success, stdout, stderr = self._run_command(f"test -x {shared_prolog}", host)
            results["Prolog script executable"] = success
        else:
            results["Prolog script executable"] = False
            
        if results["Shared epilog script exists"]:
            success, stdout, stderr = self._run_command(f"test -x {shared_epilog}", host)
            results["Epilog script executable"] = success
        else:
            results["Epilog script executable"] = False
        
        # Check symlinks on BCM headnode and login nodes (nodes that submit jobs)
        prolog_script = "/cm/local/apps/slurm/var/prologs/60-prolog-jobstats.sh"
        epilog_script = "/cm/local/apps/slurm/var/epilogs/60-epilog-jobstats.sh"
        
        # Check symlinks on BCM headnode (localhost)
        headnode_prolog = self._check_file_exists(prolog_script, None)  # localhost
        headnode_epilog = self._check_file_exists(epilog_script, None)  # localhost
        
        # Check symlinks on login nodes
        login_nodes = self.config['systems'].get('login_nodes', [])
        login_prolog = all(self._check_file_exists(prolog_script, login_host) for login_host in login_nodes) if login_nodes else True
        login_epilog = all(self._check_file_exists(epilog_script, login_host) for login_host in login_nodes) if login_nodes else True
        
        results["Prolog script symlink exists"] = headnode_prolog and login_prolog
        results["Epilog script symlink exists"] = headnode_epilog and login_epilog
        
        return results
    
    def _test_result(self, test_name: str, passed: bool, message: str = "", warning: bool = False):
        """Record and display a test result."""
        self.results['total'] += 1
        
        if warning:
            self.results['warnings'] += 1
            status = f"{Colors.YELLOW}⚠️  WARNING{Colors.END}"
        elif passed:
            self.results['passed'] += 1
            status = f"{Colors.GREEN}✅ PASS{Colors.END}"
        else:
            self.results['failed'] += 1
            status = f"{Colors.RED}❌ FAIL{Colors.END}"
        
        print(f"{status} {test_name}")
        if message:
            print(f"    {message}")
    
    def validate_services(self):
        """Validate that all required services are running."""
        print(f"\n{Colors.BOLD}1. Checking Systemd Services{Colors.END}")
        print("=" * 50)
        
        # Define services by host type
        service_checks = {
            'dgx_nodes': ['cgroup_exporter', 'node_exporter', 'nvidia_gpu_exporter'],
            'prometheus_server': ['prometheus'],
            'grafana_server': ['grafana-server']
        }
        
        for host_type, services in service_checks.items():
            hosts = self.config['systems'].get(host_type, [])
            for host in hosts:
                for service in services:
                    is_running = self._check_service(service, host)
                    self._test_result(
                        f"{service} on {host}",
                        is_running,
                        f"Service {'running' if is_running else 'not running'}"
                    )
    
    def validate_ports(self):
        """Validate that all required ports are listening."""
        print(f"\n{Colors.BOLD}2. Checking Service Ports{Colors.END}")
        print("=" * 50)
        
        port_checks = {
            'dgx_nodes': [
                (self.config['node_exporter_port'], 'node_exporter'),
                (self.config['cgroup_exporter_port'], 'cgroup_exporter'),
                (self.config['nvidia_gpu_exporter_port'], 'nvidia_gpu_exporter')
            ],
            'prometheus_server': [(self.config['prometheus_port'], 'prometheus')],
            'grafana_server': [(self.config['grafana_port'], 'grafana')]
        }
        
        for host_type, ports in port_checks.items():
            hosts = self.config['systems'].get(host_type, [])
            for host in hosts:
                for port, service in ports:
                    is_listening = self._check_port(port, host)
                    self._test_result(
                        f"Port {port} ({service}) on {host}",
                        is_listening,
                        f"Port {'listening' if is_listening else 'not listening'}"
                    )
    
    def validate_metrics_endpoints(self):
        """Validate that all metrics endpoints are responding."""
        print(f"\n{Colors.BOLD}3. Checking Metrics Endpoints{Colors.END}")
        print("=" * 50)
        
        endpoint_checks = {
            'dgx_nodes': [
                (f"http://localhost:{self.config['node_exporter_port']}/metrics", 'node_exporter'),
                (f"http://localhost:{self.config['cgroup_exporter_port']}/metrics", 'cgroup_exporter'),
                (f"http://localhost:{self.config['nvidia_gpu_exporter_port']}/metrics", 'nvidia_gpu_exporter')
            ]
        }
        
        for host_type, endpoints in endpoint_checks.items():
            hosts = self.config['systems'].get(host_type, [])
            for host in hosts:
                for url, service in endpoints:
                    is_responding, response = self._check_metrics_endpoint(url, host)
                    self._test_result(
                        f"{service} metrics on {host}",
                        is_responding,
                        f"Endpoint {'responding' if is_responding else 'not responding'}"
                    )
    
    def validate_prometheus_targets(self):
        """Validate Prometheus targets and configuration."""
        print(f"\n{Colors.BOLD}4. Checking Prometheus Targets{Colors.END}")
        print("=" * 50)
        
        prometheus_host = self.config['systems']['prometheus_server'][0]
        prometheus_port = self.config['prometheus_port']
        
        # Check if Prometheus is responding
        success, stdout, stderr = self._run_command(
            f"curl -s http://localhost:{prometheus_port}/api/v1/targets", 
            prometheus_host
        )
        
        if not success:
            self._test_result("Prometheus API accessible", False, "Cannot reach Prometheus API")
            return
        
        try:
            targets_data = json.loads(stdout)
            active_targets = targets_data.get('data', {}).get('activeTargets', [])
            
            if not active_targets:
                self._test_result("Prometheus has targets", False, "No active targets found")
                return
            
            healthy_targets = [t for t in active_targets if t.get('health') == 'up']
            total_targets = len(active_targets)
            
            self._test_result(
                "Prometheus targets health",
                len(healthy_targets) > 0,
                f"{len(healthy_targets)}/{total_targets} targets healthy"
            )
            
            # List all targets
            for target in active_targets:
                job = target.get('labels', {}).get('job', 'unknown')
                health = target.get('health', 'unknown')
                status = "✅" if health == "up" else "❌"
                print(f"    {status} {job}: {health}")
                
        except json.JSONDecodeError:
            self._test_result("Prometheus targets parsing", False, "Invalid JSON response")
    
    def validate_slurm_integration(self):
        """Validate Slurm integration files and configuration."""
        print(f"\n{Colors.BOLD}5. Checking Slurm Integration{Colors.END}")
        print("=" * 50)
        
        # Check GPU tracking scripts on DGX nodes
        dgx_nodes = self.config['systems'].get('dgx_nodes', [])
        for host in dgx_nodes:
            prolog_exists = self._check_file_exists("/cm/local/apps/slurm/var/prologs/60-prolog-jobstats.sh", host)
            epilog_exists = self._check_file_exists("/cm/local/apps/slurm/var/epilogs/60-epilog-jobstats.sh", host)
            
            self._test_result(
                f"GPU prolog script on {host}",
                prolog_exists,
                "Script installed" if prolog_exists else "Script missing"
            )
            
            self._test_result(
                f"GPU epilog script on {host}",
                epilog_exists,
                "Script installed" if epilog_exists else "Script missing"
            )
        
        # Check job summary script on Slurm controller
        slurm_controller = self.config['systems']['slurm_controller'][0]
        summary_script_exists = self._check_file_exists("/usr/local/sbin/slurmctldepilog.sh", slurm_controller)
        
        self._test_result(
            f"Job summary script on {slurm_controller}",
            summary_script_exists,
            "Script installed" if summary_script_exists else "Script missing"
        )
    
    def validate_slurm_configuration(self):
        """Validate BCM-managed Slurm configuration for jobstats."""
        print(f"\n{Colors.BOLD}6. Checking BCM Slurm Configuration{Colors.END}")
        print("=" * 50)
        
        # BCM commands should be run on the BCM headnode (localhost), not slurm_controller
        settings = self._check_bcm_slurm_configuration(None)  # None = localhost
        
        for setting, exists in settings.items():
            self._test_result(
                f"BCM Slurm: {setting}",
                exists,
                "Configured correctly" if exists else "Not configured"
            )
    
    def validate_jobstats_command(self):
        """Validate jobstats command availability."""
        print(f"\n{Colors.BOLD}7. Checking Jobstats Command{Colors.END}")
        print("=" * 50)
        
        login_nodes = self.config['systems'].get('login_nodes', [])
        for host in login_nodes:
            success, stdout, stderr = self._run_command("command -v jobstats", host)
            self._test_result(
                f"jobstats command on {host}",
                success,
                "Command available" if success else "Command not found"
            )
            
            if success:
                # Check if jobstats is executable
                success, stdout, stderr = self._run_command("jobstats --help | head -1", host)
                if success:
                    print(f"    Version: {stdout.strip()}")
    
    def validate_bcm_requirements(self):
        """Validate BCM configuration requirements that should be automated."""
        print(f"\n{Colors.BOLD}8. BCM Configuration Requirements{Colors.END}")
        print("=" * 50)
        
        slurm_controller = self.config['systems']['slurm_controller'][0]
        
        # Check slurm.conf cgroup settings
        cluster_name = self.config.get('cluster_name', 'slurm')
        slurm_conf_path = f"/cm/shared/apps/slurm/var/etc/{cluster_name}/slurm.conf"
        
        cgroup_settings = {
            'JobAcctGatherType': 'jobacct_gather/cgroup',
            'ProctrackType': 'proctrack/cgroup', 
            'TaskPlugin': 'affinity,cgroup'
        }
        
        print(f"Checking slurm.conf cgroup settings in {slurm_conf_path}...")
        for setting, expected_value in cgroup_settings.items():
            success, stdout, stderr = self._run_command(
                f"grep '^{setting}\\s*=' {slurm_conf_path} | head -1", 
                slurm_controller
            )
            if success and expected_value in stdout:
                self._test_result(
                    f"slurm.conf: {setting}",
                    True,
                    f"Correctly set to {expected_value}"
                )
            else:
                self._test_result(
                    f"slurm.conf: {setting}",
                    False,
                    f"Not set to {expected_value} or missing"
                )
        
        # Check BCM category service management
        slurm_category = self.config.get('slurm_category', 'dgx')
        kubernetes_category = self.config.get('kubernetes_category', 'runai')
        
        print(f"\nChecking BCM category service management...")
        
        # Check if services are configured in Slurm category
        for service in ['cgroup_exporter', 'node_exporter', 'nvidia_gpu_exporter']:
            success, stdout, stderr = self._run_command(
                f'cmsh -c "category; use {slurm_category}; services; list" | grep {service}',
                None  # Run locally on BCM headnode
            )
            self._test_result(
                f"BCM: {service} in {slurm_category} category",
                success,
                "Service configured" if success else "Service not configured"
            )
        
        # Check if services are configured in Kubernetes category (should be disabled)
        for service in ['cgroup_exporter', 'node_exporter', 'nvidia_gpu_exporter']:
            success, stdout, stderr = self._run_command(
                f'cmsh -c "category; use {kubernetes_category}; services; list" | grep {service}',
                None  # Run locally on BCM headnode
            )
            self._test_result(
                f"BCM: {service} in {kubernetes_category} category",
                success,
                "Service configured (should be disabled)" if success else "Service not configured"
            )
    
    def validate_data_quality(self):
        """Validate data quality and check for known issues."""
        print(f"\n{Colors.BOLD}9. Checking Data Quality{Colors.END}")
        print("=" * 50)
        
        # Test for alloc/cores division error
        self._test_alloc_cores_issue()
        
        # Test for timelimit issues
        self._test_timelimit_issues()
        
        # Test job data completeness
        self._test_job_data_completeness()
        
        # Test metric label consistency
        self._test_metric_label_consistency()
    
    def _test_alloc_cores_issue(self):
        """Test for the alloc/cores division error that fix_jobstats_alloc_cores.py addresses."""
        print(f"\n{Colors.BLUE}Testing for alloc/cores division error...{Colors.END}")
        
        # Check if there are any recent jobs with the alloc/cores issue
        slurm_controller = self.config['systems']['slurm_controller'][0]
        
        # Look for jobs in the last 24 hours
        success, stdout, stderr = self._run_command(
            "sacct -S $(date -d '1 day ago' '+%Y-%m-%d') --format=JobID,AllocCPUS,ReqCPUS,State --noheader | head -10",
            slurm_controller
        )
        
        if not success:
            self._test_result(
                "Alloc/cores data availability",
                False,
                "Cannot retrieve job allocation data from Slurm"
            )
            return
        
        # Check for potential alloc/cores mismatches
        alloc_cores_issues = 0
        total_jobs = 0
        
        for line in stdout.strip().split('\n'):
            if not line.strip():
                continue
                
            parts = line.split()
            if len(parts) >= 4:
                job_id, alloc_cpus, req_cpus, state = parts[0], parts[1], parts[2], parts[3]
                total_jobs += 1
                
                # Check for potential division issues (alloc_cpus != req_cpus when both are numbers)
                try:
                    alloc_num = int(alloc_cpus)
                    req_num = int(req_cpus)
                    if alloc_num != req_num and state in ['COMPLETED', 'FAILED', 'CANCELLED']:
                        alloc_cores_issues += 1
                except ValueError:
                    continue
        
        if total_jobs > 0:
            issue_percentage = (alloc_cores_issues / total_jobs) * 100
            self._test_result(
                "Alloc/cores consistency",
                issue_percentage < 50,  # Allow some variance but flag if >50% have issues
                f"Found {alloc_cores_issues}/{total_jobs} jobs with potential alloc/cores mismatch ({issue_percentage:.1f}%)"
            )
        else:
            self._test_result(
                "Alloc/cores data availability",
                True,
                "No recent job data found to analyze"
            )
    
    def _test_timelimit_issues(self):
        """Test for timelimit issues that fix_jobstats_timelimit.py addresses."""
        print(f"\n{Colors.BLUE}Testing for timelimit issues...{Colors.END}")
        
        slurm_controller = self.config['systems']['slurm_controller'][0]
        
        # Check for jobs with unusual timelimit patterns
        success, stdout, stderr = self._run_command(
            "sacct -S $(date -d '1 day ago' '+%Y-%m-%d') --format=JobID,TimeLimit,Elapsed,State --noheader | head -10",
            slurm_controller
        )
        
        if not success:
            self._test_result(
                "Timelimit data availability",
                False,
                "Cannot retrieve job timelimit data from Slurm"
            )
            return
        
        # Check for potential timelimit issues
        timelimit_issues = 0
        total_jobs = 0
        
        for line in stdout.strip().split('\n'):
            if not line.strip():
                continue
                
            parts = line.split()
            if len(parts) >= 4:
                job_id, time_limit, elapsed, state = parts[0], parts[1], parts[2], parts[3]
                total_jobs += 1
                
                # Check for jobs that failed due to time limit
                if state == 'TIMEOUT' or 'TIME' in state:
                    timelimit_issues += 1
        
        if total_jobs > 0:
            issue_percentage = (timelimit_issues / total_jobs) * 100
            self._test_result(
                "Timelimit consistency",
                issue_percentage < 20,  # Flag if >20% of jobs timeout
                f"Found {timelimit_issues}/{total_jobs} jobs with timelimit issues ({issue_percentage:.1f}%)"
            )
        else:
            self._test_result(
                "Timelimit data availability",
                True,
                "No recent job data found to analyze"
            )
    
    def _test_job_data_completeness(self):
        """Test that job data contains all required fields."""
        print(f"\n{Colors.BLUE}Testing job data completeness...{Colors.END}")
        
        # Test jobstats command with a recent job
        login_nodes = self.config['systems'].get('login_nodes', [])
        if not login_nodes:
            self._test_result(
                "Job data completeness",
                False,
                "No login nodes configured for testing"
            )
            return
        
        login_host = login_nodes[0]
        
        # Get a recent completed job
        success, stdout, stderr = self._run_command(
            "sacct -S $(date -d '1 day ago' '+%Y-%m-%d') --format=JobID,State --noheader | grep -E '(COMPLETED|FAILED|CANCELLED)' | head -1",
            login_host
        )
        
        if not success or not stdout.strip():
            self._test_result(
                "Job data completeness",
                True,
                "No recent completed jobs found to test"
            )
            return
        
        job_id = stdout.strip().split()[0]
        
        # Test jobstats command on this job
        success, stdout, stderr = self._run_command(
            f"jobstats {job_id}",
            login_host
        )
        
        if success and "No data was found" not in stdout:
            # Check for key data fields in the output
            required_fields = ['Job ID', 'User', 'Account', 'State', 'Exit Code']
            missing_fields = []
            
            for field in required_fields:
                if field not in stdout:
                    missing_fields.append(field)
            
            self._test_result(
                "Job data completeness",
                len(missing_fields) == 0,
                f"Missing fields: {', '.join(missing_fields)}" if missing_fields else "All required fields present"
            )
        else:
            self._test_result(
                "Job data completeness",
                False,
                f"Jobstats command failed or returned no data for job {job_id}"
            )
    
    def _test_metric_label_consistency(self):
        """Test that Prometheus metrics have consistent labels."""
        print(f"\n{Colors.BLUE}Testing metric label consistency...{Colors.END}")
        
        prometheus_host = self.config['systems']['prometheus_server'][0]
        prometheus_port = self.config['prometheus_port']
        
        # Check node_exporter labels
        success, stdout, stderr = self._run_command(
            f"curl -s 'http://localhost:{self.config['prometheus_port']}/api/v1/query?query=node_uname_info' | jq '.data.result[0].metric' 2>/dev/null || echo 'no_data'",
            prometheus_host
        )
        
        if success and stdout.strip() and stdout.strip() != 'no_data':
            # Parse the JSON metric object
            try:
                import json
                metric = json.loads(stdout)
                if metric is None:
                    self._test_result(
                        "Node exporter labels",
                        False,
                        "No node_exporter metrics found - check if node_exporter is running and accessible"
                    )
                else:
                    required_labels = ['instance', 'job', 'nodename']
                    missing_labels = []
                    
                    for label in required_labels:
                        if label not in metric:
                            missing_labels.append(label)
                    
                    self._test_result(
                        "Node exporter labels",
                        len(missing_labels) == 0,
                        f"Missing labels: {', '.join(missing_labels)}" if missing_labels else "All required labels present"
                    )
            except json.JSONDecodeError:
                self._test_result(
                    "Node exporter labels",
                    False,
                    "Failed to parse metric labels JSON"
                )
        else:
            self._test_result(
                "Node exporter labels",
                False,
                "No node_exporter metrics found - check if node_exporter is running and accessible"
            )
        
        # Check cgroup metrics labels
        success, stdout, stderr = self._run_command(
            f"curl -s 'http://localhost:{prometheus_port}/api/v1/query?query=cgroup_cpu_total_seconds' | jq '.data.result[0].metric' 2>/dev/null || echo 'no_data'",
            prometheus_host
        )
        
        if success and stdout.strip() and stdout.strip() != 'no_data':
            # Parse the JSON metric object
            try:
                import json
                metric = json.loads(stdout)
                if metric is None:
                    self._test_result(
                        "Cgroup metric labels",
                        False,
                        "No cgroup metrics found - check cgroup_exporter configuration",
                        warning=True
                    )
                    self._check_cgroup_exporter_config()
                else:
                    # Check for required labels (based on actual cgroup_exporter output)
                    required_labels = ['jobid', 'cluster', 'instance', 'job']
                    missing_labels = []
                    
                    for label in required_labels:
                        if label not in metric:
                            missing_labels.append(label)
                    
                    self._test_result(
                        "Cgroup metric labels",
                        len(missing_labels) == 0,
                        f"Missing labels: {', '.join(missing_labels)}" if missing_labels else "All required labels present"
                    )
            except json.JSONDecodeError:
                self._test_result(
                    "Cgroup metric labels",
                    False,
                    "Failed to parse metric labels JSON"
                )
        else:
            self._test_result(
                "Cgroup metric labels",
                False,
                "No cgroup metrics found - check cgroup_exporter configuration",
                warning=True
            )
            self._check_cgroup_exporter_config()
    
    def _check_cgroup_exporter_config(self):
        """Check cgroup_exporter configuration and provide diagnostic information."""
        print(f"\n{Colors.YELLOW}🔍 Cgroup Exporter Configuration Check{Colors.END}")
        
        # Check cgroup_exporter configuration
        dgx_nodes = self.config['systems'].get('dgx_nodes', [])
        if dgx_nodes:
            dgx_host = dgx_nodes[0]
            
            # Get cgroup_exporter configuration
            success, stdout, stderr = self._run_command(
                "systemctl cat cgroup_exporter | grep ExecStart",
                dgx_host
            )
            
            if success:
                print(f"{Colors.BLUE}Current cgroup_exporter config: {stdout.strip()}{Colors.END}")
                
                # Check what cgroup paths exist
                success, stdout, stderr = self._run_command(
                    "find /sys/fs/cgroup/ -name '*slurm*' -type d 2>/dev/null | head -5",
                    dgx_host
                )
                
                if success and stdout.strip():
                    print(f"{Colors.BLUE}Available cgroup paths:{Colors.END}")
                    for path in stdout.strip().split('\n'):
                        print(f"  {path}")
                
                # Check if there are job-specific cgroup directories
                success, stdout, stderr = self._run_command(
                    "find /sys/fs/cgroup/ -path '*/slurm/*' -name '*job*' -o -name '*uid*' 2>/dev/null | head -5",
                    dgx_host
                )
                
                if success and stdout.strip():
                    print(f"{Colors.GREEN}Found job-specific cgroup directories:{Colors.END}")
                    for path in stdout.strip().split('\n'):
                        print(f"  {path}")
                else:
                    print(f"{Colors.YELLOW}No job-specific cgroup directories found{Colors.END}")
                    print(f"{Colors.YELLOW}This suggests either:{Colors.END}")
                    print(f"{Colors.YELLOW}  1. No jobs are currently running{Colors.END}")
                    print(f"{Colors.YELLOW}  2. cgroup_exporter is monitoring wrong paths{Colors.END}")
                    print(f"{Colors.YELLOW}  3. Slurm cgroup configuration issue{Colors.END}")
            else:
                print(f"{Colors.RED}Could not retrieve cgroup_exporter configuration{Colors.END}")
    
    def _suggest_test_job(self):
        """Suggest running a test job to generate metrics for validation."""
        if not hasattr(self, '_test_job_suggested'):
            self._test_job_suggested = True
            print(f"\n{Colors.YELLOW}💡 SUGGESTION: No recent job data found for metric validation{Colors.END}")
            print(f"{Colors.BLUE}To generate test data and validate metrics, run this test job:{Colors.END}")
            print(f"{Colors.BOLD}    srun --time=2:00 --cpus-per-task=2 --mem=1G --job-name=jobstats-test \\")
            print(f"        bash -c 'echo \"Testing jobstats deployment...\"; sleep 60; echo \"Test job completed\"'{Colors.END}")
            print(f"\n{Colors.BLUE}After the job completes, wait 2-3 minutes for metrics to be scraped, then run:{Colors.END}")
            print(f"{Colors.BOLD}    python3 automation/tools/validate_jobstats_deployment.py{Colors.END}")
            print(f"\n{Colors.YELLOW}Note: Cgroup metrics are only available while jobs are running or briefly after completion.{Colors.END}")
            print(f"{Colors.YELLOW}If validation still fails, the cgroup_exporter may need configuration adjustment.{Colors.END}")
    
    def generate_report(self):
        """Generate a summary report."""
        print(f"\n{Colors.BOLD}Validation Summary{Colors.END}")
        print("=" * 50)
        
        total = self.results['total']
        passed = self.results['passed']
        failed = self.results['failed']
        warnings = self.results['warnings']
        
        print(f"Total tests: {total}")
        print(f"{Colors.GREEN}Passed: {passed}{Colors.END}")
        print(f"{Colors.RED}Failed: {failed}{Colors.END}")
        print(f"{Colors.YELLOW}Warnings: {warnings}{Colors.END}")
        
        if failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 All critical tests passed! Jobstats deployment is working correctly.{Colors.END}")
            return True
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ Some tests failed. Please review the issues above.{Colors.END}")
            return False
    
    def run_validation(self):
        """Run all validation tests."""
        print(f"{Colors.BOLD}BCM Jobstats Deployment Validation{Colors.END}")
        print(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        try:
            self.validate_services()
            self.validate_ports()
            self.validate_metrics_endpoints()
            self.validate_prometheus_targets()
            self.validate_slurm_integration()
            self.validate_slurm_configuration()
            self.validate_jobstats_command()
            self.validate_bcm_requirements()
            self.validate_data_quality()
            
            return self.generate_report()
            
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Validation interrupted by user{Colors.END}")
            return False
        except Exception as e:
            print(f"\n{Colors.RED}Validation failed with error: {e}{Colors.END}")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate BCM Jobstats Deployment")
    parser.add_argument(
        "--config", 
        default="automation/configs/config.json",
        help="Path to configuration file (default: automation/configs/config.json)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    validator = JobstatsValidator(args.config, args.verbose)
    success = validator.run_validation()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
