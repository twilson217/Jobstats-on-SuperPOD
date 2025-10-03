#!/usr/bin/env python3
"""
BCM Role Monitor for DGX Nodes

This script runs on each DGX node and monitors the BCM API to check if the 
slurmclient role is assigned to the node via configuration overlay. It manages
the jobstats exporter services based on the role assignment.

Author: Jobstats Deployment System
"""

import time
import subprocess
import json
import os
import socket
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

# Try to import pythoncm, but make it optional
try:
    import pythoncm
    HAS_PYTHONCM = True
except ImportError:
    HAS_PYTHONCM = False
    pythoncm = None

class BCMRoleMonitor:
    def __init__(self, config_file: str = '/etc/bcm-role-monitor/config.json'):
        self.config_file = config_file
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
        
        # BCM connection (only if pythoncm is available)
        if HAS_PYTHONCM:
            self.cm = pythoncm.ClusterManager()
            self.cluster = None
        else:
            self.cm = None
            self.cluster = None
        
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
            "cert_path": "/root/.cm/admin.pem",
            "key_path": "/root/.cm/admin.key",
            "check_interval": 60,
            "retry_interval": 600,  # 10 minutes
            "max_retries": 3
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
    
    def discover_bcm_headnodes(self) -> List[str]:
        """Discover BCM headnodes from configuration (set during deployment)"""
        # BCM headnodes should be configured during deployment from the BCM headnode
        # where cmsh is available. This method is just a fallback for missing config.
        headnodes = []
        
        self.logger.warning("No BCM headnodes configured - this should have been set during deployment")
        self.logger.info("Attempting fallback discovery methods...")
        
        # Fallback: try common naming patterns
        common_names = [
            'bcm-head', 'bcm-headnode', 'head', 'headnode',
            'slogin-01', 'login-01', 'mgmt-01', 'management-01'
        ]
        
        for name in common_names:
            try:
                socket.gethostbyname(name)
                headnodes.append(name)
                self.logger.info(f"Discovered potential BCM headnode via fallback: {name}")
            except socket.gaierror:
                continue
        
        if not headnodes:
            self.logger.error("No BCM headnodes could be discovered. Please check configuration.")
        
        return headnodes
    
    def connect_to_bcm(self) -> bool:
        """Connect to BCM cluster with failover"""
        headnodes = self.config.get('bcm_headnodes', [])
        
        # If no headnodes configured, try to discover them
        if not headnodes:
            headnodes = self.discover_bcm_headnodes()
            if headnodes:
                self.config['bcm_headnodes'] = headnodes
                self.save_config()
        
        if not headnodes:
            self.logger.error("No BCM headnodes configured or discovered")
            return False
        
        # If we have pythoncm, use the Python API
        if HAS_PYTHONCM and self.cm:
            for headnode in headnodes:
                try:
                    url = f"https://{headnode}:{self.config['bcm_port']}"
                    self.logger.info(f"Attempting to connect to BCM at {url}")
                    
                    self.cluster = self.cm.addCluster(
                        url,
                        self.config['cert_path'],
                        self.config['key_path']
                    )
                    
                    if self.cluster.connect():
                        self.logger.info(f"Successfully connected to BCM at {headnode}")
                        return True
                    else:
                        self.logger.warning(f"Failed to connect to BCM at {headnode}")
                        
                except Exception as e:
                    self.logger.warning(f"Error connecting to {headnode}: {e}")
                    continue
        else:
            # Without pythoncm, we'll use SSH + cmsh approach
            # Test SSH connectivity to at least one headnode
            for headnode in headnodes:
                try:
                    result = subprocess.run(
                        ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes', 
                         headnode, 'echo "SSH test successful"'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        self.logger.info(f"Successfully connected to BCM headnode {headnode} via SSH")
                        return True
                except Exception as e:
                    self.logger.warning(f"SSH connection to {headnode} failed: {e}")
                    continue
        
        self.logger.error("Failed to connect to any BCM headnode")
        return False
    
    def save_config(self):
        """Save current configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def check_slurmclient_role(self) -> Optional[bool]:
        """Check if slurmclient role is assigned to this node via configuration overlay"""
        try:
            if HAS_PYTHONCM and self.cluster:
                # Use Python API if available
                return self._check_role_via_api()
            else:
                # Use SSH + cmsh approach
                return self._check_role_via_ssh()
                
        except Exception as e:
            self.logger.error(f"Error checking slurmclient role: {e}")
            return None
    
    def _check_role_via_api(self) -> Optional[bool]:
        """Check role using BCM Python API"""
        # Get the current node
        nodes = self.cluster.getAll('node')
        current_node = None
        
        for node in nodes:
            if node.hostname == self.hostname:
                current_node = node
                break
        
        if not current_node:
            self.logger.error(f"Node {self.hostname} not found in BCM")
            return None
        
        # Check roles assigned to the node
        roles = current_node.roles
        
        # Look for slurmclient role (could be via overlay)
        has_slurmclient = False
        for role in roles:
            role_name = role.name if hasattr(role, 'name') else str(role)
            self.logger.debug(f"Found role: {role_name}")
            if 'slurmclient' in role_name.lower():
                has_slurmclient = True
                break
        
        self.logger.info(f"Node {self.hostname} slurmclient role: {has_slurmclient}")
        return has_slurmclient
    
    def _check_role_via_ssh(self) -> Optional[bool]:
        """Check role using SSH + cmsh commands"""
        headnodes = self.config.get('bcm_headnodes', [])
        
        for headnode in headnodes:
            try:
                # Use cmsh to check roles for this node
                result = subprocess.run([
                    'ssh', '-o', 'ConnectTimeout=10', '-o', 'BatchMode=yes',
                    headnode, 
                    f'cmsh -c "device; use {self.hostname}; roles; list"'
                ], capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0:
                    # Parse the output to look for slurmclient role
                    output = result.stdout.lower()
                    has_slurmclient = 'slurmclient' in output
                    
                    self.logger.info(f"Node {self.hostname} slurmclient role: {has_slurmclient}")
                    self.logger.debug(f"BCM roles output: {result.stdout}")
                    return has_slurmclient
                else:
                    self.logger.warning(f"cmsh command failed on {headnode}: {result.stderr}")
                    continue
                    
            except Exception as e:
                self.logger.warning(f"SSH + cmsh failed on {headnode}: {e}")
                continue
        
        self.logger.error(f"Could not check roles via SSH on any BCM headnode")
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
                # Connect to BCM if not connected
                if HAS_PYTHONCM:
                    if not self.cluster or not self.cluster.isConnected():
                        if not self.connect_to_bcm():
                            self.logger.error("Cannot connect to BCM, sleeping and retrying")
                            time.sleep(self.config['check_interval'])
                            continue
                else:
                    # For SSH approach, test connectivity each time
                    if not self.connect_to_bcm():
                        self.logger.error("Cannot connect to BCM headnodes via SSH, sleeping and retrying")
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
    monitor = BCMRoleMonitor()
    monitor.monitor_loop()

if __name__ == "__main__":
    main()
