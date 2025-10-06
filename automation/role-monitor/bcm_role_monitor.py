#!/usr/bin/env python3
"""
BCM Role Monitor for DGX Nodes

This script runs on each DGX node and monitors the BCM REST API to check if the 
slurmclient role is assigned to the node via configuration overlay. It manages
the jobstats exporter services based on the role assignment.

Uses Python requests library to access BCM REST API.

Author: Jobstats Deployment System
"""

import time
import subprocess
import json
import os
import socket
import logging
import requests
import urllib3
import argparse
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

# Suppress SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class BCMRoleMonitor:
    def __init__(self, config_file: str = '/etc/bcm-role-monitor/config.json', 
                 prometheus_targets_dir: Optional[str] = None):
        self.config_file = config_file
        self.prometheus_targets_dir_override = prometheus_targets_dir
        self.config = self.load_config()
        self.hostname = socket.gethostname()
        self.state_file = f'/var/lib/bcm-role-monitor/{self.hostname}_state.json'
        self.log_file = f'/var/log/bcm-role-monitor.log'
        
        # Services to manage
        self.services = ['cgroup_exporter', 'node_exporter', 'nvidia_gpu_exporter']
        
        # Retry tracking
        self.retry_state = {}
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration"""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self) -> Dict:
        """Load configuration from file or create default"""
        default_config = {
            "bcm_headnodes": [],
            "bcm_port": 8081,
            "cert_path": "/etc/bcm-role-monitor/admin.pem",
            "key_path": "/etc/bcm-role-monitor/admin.key",
            "check_interval": 60,
            "retry_interval": 600,  # 10 minutes
            "max_retries": 3,
            "prometheus_targets_dir": "/cm/shared/apps/jobstats/prometheus-targets",
            "node_exporter_port": 9100,
            "cgroup_exporter_port": 9306,
            "nvidia_gpu_exporter_port": 9445,
            "cluster_name": "slurm"
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                self.logger.error(f"Error loading config: {e}")
                return default_config
        else:
            # Create default config file
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            self.logger.info(f"Created default config at {self.config_file}")
            return default_config
    
    def save_config(self):
        """Save current configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def test_bcm_connectivity(self) -> bool:
        """Test connectivity to BCM headnodes via REST API"""
        headnodes = self.config.get('bcm_headnodes', [])
        cert_path = self.config.get('cert_path', '/etc/bcm-role-monitor/admin.pem')
        key_path = self.config.get('key_path', '/etc/bcm-role-monitor/admin.key')
        
        if not headnodes:
            self.logger.error("No BCM headnodes configured")
            return False
        
        # Check if certificates exist
        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            self.logger.error(f"BCM certificates not found: {cert_path}, {key_path}")
            return False
        
        for headnode in headnodes:
            try:
                # Test basic API connectivity using the correct REST API endpoint
                api_url = f"https://{headnode}:{self.config.get('bcm_port', 8081)}/rest/v1/device"
                
                response = requests.get(
                    api_url,
                    cert=(cert_path, key_path),
                    verify=False,  # Equivalent to --insecure
                    timeout=10
                )
                
                if response.status_code == 200:
                    self.logger.info(f"Successfully connected to BCM REST API at {headnode}")
                    return True
                else:
                    self.logger.warning(f"Failed to connect to BCM API at {headnode}: HTTP {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Error testing BCM connectivity to {headnode}: {e}")
                continue
            except Exception as e:
                self.logger.warning(f"Unexpected error testing BCM connectivity to {headnode}: {e}")
                continue
        
        self.logger.error("Failed to connect to any BCM headnode via REST API")
        return False
    
    def check_slurmclient_role(self) -> Optional[bool]:
        """Check if slurmclient role is assigned to this node via BCM REST API"""
        headnodes = self.config.get('bcm_headnodes', [])
        cert_path = self.config.get('cert_path', '/etc/bcm-role-monitor/admin.pem')
        key_path = self.config.get('key_path', '/etc/bcm-role-monitor/admin.key')
        
        for headnode in headnodes:
            try:
                # Use BCM REST API to get all devices
                api_url = f"https://{headnode}:{self.config.get('bcm_port', 8081)}/rest/v1/device"
                
                response = requests.get(
                    api_url,
                    cert=(cert_path, key_path),
                    verify=False,  # Equivalent to --insecure
                    timeout=15
                )
                
                if response.status_code == 200:
                    try:
                        # Parse JSON response and find our device
                        devices = response.json()
                        
                        for device in devices:
                            if device.get('hostname') == self.hostname:
                                roles = device.get('roles', [])
                                has_slurmclient = 'slurmclient' in [role.lower() for role in roles]
                                
                                self.logger.info(f"Node {self.hostname} slurmclient role: {has_slurmclient}")
                                self.logger.debug(f"BCM device roles: {roles}")
                                return has_slurmclient
                        
                        # Device not found in the list
                        self.logger.warning(f"Device {self.hostname} not found in BCM device list")
                        continue
                        
                    except (json.JSONDecodeError, requests.exceptions.JSONDecodeError) as e:
                        self.logger.warning(f"Failed to parse JSON response from {headnode}: {e}")
                        self.logger.debug(f"Raw response: {response.text}")
                        continue
                else:
                    self.logger.warning(f"BCM API request failed on {headnode}: HTTP {response.status_code} - {response.text}")
                    continue
                    
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"BCM REST API request failed on {headnode}: {e}")
                continue
            except Exception as e:
                self.logger.warning(f"Unexpected error checking BCM API on {headnode}: {e}")
                continue
        
        self.logger.error(f"Could not check roles via BCM REST API on any headnode")
        return None
    
    def get_service_status(self, service: str) -> bool:
        """Check if a service is running"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service],
                capture_output=True,
                text=True
            )
            is_active = result.returncode == 0 and result.stdout.strip() == 'active'
            self.logger.debug(f"Service {service} status: {'active' if is_active else 'inactive'}")
            return is_active
        except Exception as e:
            self.logger.error(f"Error checking service {service}: {e}")
            return False
    
    def start_service(self, service: str) -> bool:
        """Start a service"""
        try:
            self.logger.info(f"Starting service {service}")
            result = subprocess.run(
                ['systemctl', 'start', service],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Verify it actually started
                time.sleep(2)
                if self.get_service_status(service):
                    self.logger.info(f"Successfully started service {service}")
                    return True
                else:
                    self.logger.error(f"Service {service} failed to start (not active after start command)")
                    return False
            else:
                self.logger.error(f"Failed to start service {service}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting service {service}: {e}")
            return False
    
    def stop_service(self, service: str) -> bool:
        """Stop a service"""
        try:
            self.logger.info(f"Stopping service {service}")
            result = subprocess.run(
                ['systemctl', 'stop', service],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.logger.info(f"Successfully stopped service {service}")
                return True
            else:
                self.logger.error(f"Failed to stop service {service}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error stopping service {service}: {e}")
            return False
    
    def manage_prometheus_targets(self, should_be_scraped: bool):
        """Add or remove this node from Prometheus scraping targets"""
        # Use command-line override if provided, otherwise use config, otherwise use default
        if self.prometheus_targets_dir_override:
            target_base_dir = self.prometheus_targets_dir_override
        else:
            target_base_dir = self.config.get('prometheus_targets_dir', '/cm/shared/apps/jobstats/prometheus-targets')
        
        # Check if directory exists and is accessible
        if not os.path.exists(target_base_dir):
            self.logger.warning(f"Prometheus targets directory does not exist: {target_base_dir}")
            return
        
        target_file = os.path.join(target_base_dir, f'{self.hostname}.json')
        
        if should_be_scraped:
            # Create single target file with all exporters
            self._create_prometheus_target(target_file)
        else:
            # Remove target file
            self._remove_prometheus_target(target_file)
    
    def _create_prometheus_target(self, target_file: str):
        """Create Prometheus target file atomically with all exporters"""
        try:
            exporters = {
                'node_exporter': self.config.get('node_exporter_port', 9100),
                'cgroup_exporter': self.config.get('cgroup_exporter_port', 9306),
                'gpu_exporter': self.config.get('nvidia_gpu_exporter_port', 9445)
            }
            
            # Create a list of targets - one entry per exporter
            target_data = []
            for exporter_name, port in exporters.items():
                target_data.append({
                    "targets": [f"{self.hostname}:{port}"],
                    "labels": {
                        "job": exporter_name,
                        "cluster": self.config.get('cluster_name', 'slurm'),
                        "hostname": self.hostname
                    }
                })
            
            # Write to temp file, then atomic move
            temp_file = f"{target_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(target_data, f, indent=2)
            
            # Atomic rename
            os.rename(temp_file, target_file)
            self.logger.info(f"Created Prometheus target file: {target_file}")
            
        except Exception as e:
            self.logger.error(f"Error creating Prometheus target {target_file}: {e}")
    
    def _remove_prometheus_target(self, target_file: str):
        """Remove Prometheus target file"""
        try:
            if os.path.exists(target_file):
                os.remove(target_file)
                self.logger.info(f"Removed Prometheus target file: {target_file}")
        except Exception as e:
            self.logger.error(f"Error removing Prometheus target {target_file}: {e}")
    
    def load_state(self) -> Dict:
        """Load previous state"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading state: {e}")
        return {}
    
    def save_state(self, state: Dict):
        """Save current state"""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")
    
    def handle_service_retry(self, service: str) -> bool:
        """Handle service start retry logic"""
        now = datetime.now()
        
        # Initialize retry state for service if not exists
        if service not in self.retry_state:
            self.retry_state[service] = {
                'attempts': 0,
                'last_attempt': None,
                'next_attempt': None,
                'failed_permanently': False
            }
        
        retry_info = self.retry_state[service]
        
        # If permanently failed, don't retry until service is seen running again
        if retry_info['failed_permanently']:
            if self.get_service_status(service):
                self.logger.info(f"Service {service} is running again, resetting retry state")
                self.retry_state[service] = {'attempts': 0, 'last_attempt': None, 'next_attempt': None, 'failed_permanently': False}
            return False
        
        # Check if we should attempt to start
        if retry_info['next_attempt'] and now < retry_info['next_attempt']:
            return False  # Not time yet
        
        # Attempt to start service
        if self.start_service(service):
            # Success - reset retry state
            self.retry_state[service] = {'attempts': 0, 'last_attempt': None, 'next_attempt': None, 'failed_permanently': False}
            return True
        else:
            # Failed - update retry state
            retry_info['attempts'] += 1
            retry_info['last_attempt'] = now
            
            if retry_info['attempts'] >= self.config['max_retries']:
                retry_info['failed_permanently'] = True
                self.logger.error(f"Service {service} failed to start after {self.config['max_retries']} attempts, giving up")
            else:
                retry_info['next_attempt'] = now + timedelta(seconds=self.config['retry_interval'])
                self.logger.warning(f"Service {service} start failed, attempt {retry_info['attempts']}/{self.config['max_retries']}, next attempt at {retry_info['next_attempt']}")
            
            return False
    
    def manage_services(self, should_run: bool):
        """Manage services based on role assignment"""
        for service in self.services:
            is_running = self.get_service_status(service)
            
            if should_run:
                if not is_running:
                    self.logger.info(f"Service {service} should be running but is not, attempting to start")
                    self.handle_service_retry(service)
                else:
                    # Service is running and should be - reset any retry state
                    if service in self.retry_state:
                        self.retry_state[service] = {'attempts': 0, 'last_attempt': None, 'next_attempt': None, 'failed_permanently': False}
            else:
                if is_running:
                    self.logger.info(f"Service {service} should not be running, stopping")
                    self.stop_service(service)
                # Reset retry state when services should not be running
                if service in self.retry_state:
                    self.retry_state[service] = {'attempts': 0, 'last_attempt': None, 'next_attempt': None, 'failed_permanently': False}
    
    def monitor_loop(self):
        """Main monitoring loop"""
        self.logger.info(f"Starting BCM role monitor for node {self.hostname}")
        
        previous_state = self.load_state()
        previous_role_status = previous_state.get('has_slurmclient_role')
        
        while True:
            try:
                # Test BCM connectivity
                if not self.test_bcm_connectivity():
                    self.logger.error("Cannot connect to BCM REST API, sleeping and retrying")
                    time.sleep(self.config['check_interval'])
                    continue
                
                # Check role assignment
                has_slurmclient_role = self.check_slurmclient_role()
                
                if has_slurmclient_role is None:
                    self.logger.error("Could not determine role status, not making any changes")
                    time.sleep(self.config['check_interval'])
                    continue
                
                # Log role change
                if previous_role_status != has_slurmclient_role:
                    self.logger.info(f"Role change detected: slurmclient role = {has_slurmclient_role}")
                
                # Manage services based on role
                self.manage_services(has_slurmclient_role)
                
                # Manage Prometheus targets based on role
                self.manage_prometheus_targets(has_slurmclient_role)
                
                # Save current state
                current_state = {
                    'has_slurmclient_role': has_slurmclient_role,
                    'last_check': datetime.now().isoformat(),
                    'retry_state': self.retry_state
                }
                self.save_state(current_state)
                previous_role_status = has_slurmclient_role
                
                # Sleep until next check
                time.sleep(self.config['check_interval'])
                
            except KeyboardInterrupt:
                self.logger.info("Received interrupt signal, shutting down")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in monitor loop: {e}")
                time.sleep(self.config['check_interval'])

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='BCM Role Monitor - Manages jobstats exporters and Prometheus targets based on BCM role assignment',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default configuration
  %(prog)s
  
  # Override Prometheus targets directory
  %(prog)s --prometheus-targets-dir /my/custom/targets
  
  # Use custom config file
  %(prog)s --config /etc/my-config.json
  
  # Combine options
  %(prog)s --config /etc/my-config.json --prometheus-targets-dir /shared/prometheus/targets
        """
    )
    
    parser.add_argument(
        '--config',
        default='/etc/bcm-role-monitor/config.json',
        help='Path to configuration file (default: /etc/bcm-role-monitor/config.json)'
    )
    
    parser.add_argument(
        '--prometheus-targets-dir',
        dest='prometheus_targets_dir',
        help='Override Prometheus targets directory (default: from config or /cm/shared/apps/jobstats/prometheus-targets)'
    )
    
    args = parser.parse_args()
    
    monitor = BCMRoleMonitor(
        config_file=args.config,
        prometheus_targets_dir=args.prometheus_targets_dir
    )
    monitor.monitor_loop()

if __name__ == "__main__":
    main()
