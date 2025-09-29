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
            results["BCM prolog/epilog configured"] = True
            results["BCM epilogslurmctld configured"] = "/usr/local/sbin/slurmctldepilog.sh" in stdout
        else:
            results["BCM prolog/epilog configured"] = False
            results["BCM epilogslurmctld configured"] = False
        
        # Check if jobstats scripts are properly installed
        prolog_script = "/cm/local/apps/slurm/var/prologs/60-prolog-jobstats.sh"
        epilog_script = "/cm/local/apps/slurm/var/epilogs/60-epilog-jobstats.sh"
        shared_prolog = "/cm/shared/apps/slurm/var/cm/prolog-jobstats.sh"
        shared_epilog = "/cm/shared/apps/slurm/var/cm/epilog-jobstats.sh"
        
        results["Prolog script symlink exists"] = self._check_file_exists(prolog_script, host)
        results["Epilog script symlink exists"] = self._check_file_exists(epilog_script, host)
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
            'dgx_nodes': ['cgroup_exporter', 'node_exporter', 'nvidia_gpu_prometheus_exporter'],
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
            prolog_exists = self._check_file_exists("/etc/slurm/prolog.d/gpustats_helper.sh", host)
            epilog_exists = self._check_file_exists("/etc/slurm/epilog.d/gpustats_helper.sh", host)
            
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
        
        slurm_controller = self.config['systems']['slurm_controller'][0]
        settings = self._check_bcm_slurm_configuration(slurm_controller)
        
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
        """Display BCM configuration requirements."""
        print(f"\n{Colors.BOLD}8. BCM Configuration Requirements{Colors.END}")
        print("=" * 50)
        
        print(f"{Colors.YELLOW}⚠️  The following settings need to be added to slurm.conf via BCM:{Colors.END}")
        print("   Prolog=/etc/slurm/prolog.d/*.sh")
        print("   Epilog=/etc/slurm/epilog.d/*.sh")
        print("   EpilogSlurmctld=/usr/local/sbin/slurmctldepilog.sh")
        print()
        print("   Additionally, ensure these cgroup settings are present:")
        print("   JobAcctGatherType=jobacct_gather/cgroup")
        print("   ProctrackType=proctrack/cgroup")
        print("   TaskPlugin=affinity,cgroup")
        
        self.results['warnings'] += 1
        self.results['total'] += 1
    
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
