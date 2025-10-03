#!/usr/bin/env python3
"""
BCM Role Monitor Deployment Script

This script runs from the BCM headnode and deploys the BCM role monitoring 
service to DGX nodes. It discovers BCM headnodes using cmsh and configures
the service accordingly.

Author: Jobstats Deployment System
"""

import os
import sys
import json
import subprocess
import socket
from pathlib import Path
from datetime import datetime
from typing import List, Dict

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    BOLD = '\033[1m'
    END = '\033[0m'

class BCMRoleMonitorDeployer:
    def __init__(self, config: Dict = None):
        self.script_dir = Path(__file__).parent.absolute()
        self.config = config or {}
        self.dgx_nodes = self.config.get('dgx_nodes', [])
        
    def log(self, message):
        """Log info message"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"{Colors.BLUE}[{timestamp}]{Colors.END} {message}")
    
    def error(self, message):
        """Log error message"""
        print(f"{Colors.RED}[ERROR]{Colors.END} {message}", file=sys.stderr)
    
    def success(self, message):
        """Log success message"""
        print(f"{Colors.GREEN}[SUCCESS]{Colors.END} {message}")
    
    def warning(self, message):
        """Log warning message"""
        print(f"{Colors.YELLOW}[WARNING]{Colors.END} {message}")
    
    def discover_bcm_headnodes(self) -> List[str]:
        """Discover BCM headnodes using cmsh command"""
        headnodes = []
        
        try:
            self.log("Discovering BCM headnodes using cmsh...")
            result = subprocess.run(
                ['cmsh', '-c', 'device list --type headnode'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Parse the output to extract hostnames
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    # Skip header lines and empty lines
                    if line and not line.startswith('Name') and not line.startswith('---'):
                        # Extract actual hostname (second column) not BCM internal name
                        parts = line.split()
                        if len(parts) >= 2:
                            hostname = parts[1]  # Second column is the actual hostname
                            if hostname and hostname not in headnodes:
                                headnodes.append(hostname)
                                self.success(f"Discovered BCM headnode: {hostname}")
                
                if headnodes:
                    self.success(f"Found {len(headnodes)} BCM headnode(s)")
                else:
                    self.warning("No headnodes found in cmsh output")
            else:
                self.error(f"cmsh command failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.error("cmsh command timed out")
        except FileNotFoundError:
            self.error("cmsh command not found - are we running on a BCM headnode?")
        except Exception as e:
            self.error(f"Error discovering BCM headnodes: {e}")
        
        return headnodes
    
    def create_config_for_dgx(self, bcm_headnodes: List[str]) -> Dict:
        """Create configuration for DGX nodes"""
        config = {
            "bcm_headnodes": bcm_headnodes,
            "bcm_port": 8081,
            "cert_path": "/etc/bcm-role-monitor/admin.pem",
            "key_path": "/etc/bcm-role-monitor/admin.key",
            "check_interval": 60,
            "retry_interval": 600,  # 10 minutes
            "max_retries": 3
        }
        return config
    
    def test_ssh_connectivity(self, hostname: str) -> bool:
        """Test SSH connectivity to a host"""
        try:
            result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes', 
                 hostname, 'echo "SSH test successful"'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return False
    
    def copy_files_to_dgx(self, dgx_node: str) -> bool:
        """Copy BCM role monitor files to a DGX node"""
        try:
            self.log(f"Copying files to {dgx_node}...")
            
            # Create remote directories
            subprocess.run([
                'ssh', dgx_node, 
                'mkdir -p /usr/local/bin /etc/bcm-role-monitor /var/lib/bcm-role-monitor /var/log'
            ], check=True)
            
            # Copy Python script
            src_script = self.script_dir / 'bcm_role_monitor.py'
            if not src_script.exists():
                self.error(f"Source script not found: {src_script}")
                return False
            
            subprocess.run([
                'scp', str(src_script), f'{dgx_node}:/usr/local/bin/'
            ], check=True)
            
            # Make script executable
            subprocess.run([
                'ssh', dgx_node, 'chmod +x /usr/local/bin/bcm_role_monitor.py'
            ], check=True)
            
            # Copy systemd service
            src_service = self.script_dir / 'bcm-role-monitor.service'
            if not src_service.exists():
                self.error(f"Source service file not found: {src_service}")
                return False
            
            subprocess.run([
                'scp', str(src_service), f'{dgx_node}:/etc/systemd/system/bcm-role-monitor.service'
            ], check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.error(f"Failed to copy files to {dgx_node}: {e}")
            return False
    
    def deploy_config_to_dgx(self, dgx_node: str, config: Dict) -> bool:
        """Deploy configuration to a DGX node"""
        try:
            self.log(f"Deploying configuration to {dgx_node}...")
            
            # Create temporary config file locally
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                json.dump(config, temp_file, indent=2)
                temp_config_path = temp_file.name
            
            try:
                # Copy config file to remote host
                subprocess.run([
                    'scp', temp_config_path, f'{dgx_node}:/etc/bcm-role-monitor/config.json'
                ], check=True)
                
                return True
                
            finally:
                # Clean up temporary file
                import os
                os.unlink(temp_config_path)
            
        except subprocess.CalledProcessError as e:
            self.error(f"Failed to deploy config to {dgx_node}: {e}")
            return False
    
    def copy_bcm_certificates_to_dgx(self, dgx_node: str) -> bool:
        """Copy BCM certificates to DGX node"""
        try:
            self.log(f"Copying BCM certificates to {dgx_node}...")
            
            # Check if certificates exist locally
            cert_files = ['/root/.cm/admin.pem', '/root/.cm/admin.key']
            for cert_file in cert_files:
                if not Path(cert_file).exists():
                    self.error(f"BCM certificate not found: {cert_file}")
                    return False
            
            # Copy certificates to service directory
            subprocess.run([
                'scp', '/root/.cm/admin.pem', f'{dgx_node}:/etc/bcm-role-monitor/admin.pem'
            ], check=True)
            
            subprocess.run([
                'scp', '/root/.cm/admin.key', f'{dgx_node}:/etc/bcm-role-monitor/admin.key'
            ], check=True)
            
            # Set proper permissions (readable only by root)
            subprocess.run([
                'ssh', dgx_node, 'chmod 600 /etc/bcm-role-monitor/admin.pem /etc/bcm-role-monitor/admin.key'
            ], check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.error(f"Failed to copy certificates to {dgx_node}: {e}")
            return False
    
    def enable_and_start_service_on_dgx(self, dgx_node: str) -> bool:
        """Enable and start the BCM role monitor service on DGX node"""
        try:
            self.log(f"Enabling and starting service on {dgx_node}...")
            
            # Reload systemd
            subprocess.run([
                'ssh', dgx_node, 'systemctl daemon-reload'
            ], check=True)
            
            # Enable service
            subprocess.run([
                'ssh', dgx_node, 'systemctl enable bcm-role-monitor.service'
            ], check=True)
            
            # Start service
            subprocess.run([
                'ssh', dgx_node, 'systemctl start bcm-role-monitor.service'
            ], check=True)
            
            # Check if service is running
            result = subprocess.run([
                'ssh', dgx_node, 'systemctl is-active --quiet bcm-role-monitor.service'
            ], capture_output=True)
            
            if result.returncode == 0:
                self.success(f"BCM role monitor service is running on {dgx_node}")
                return True
            else:
                self.error(f"BCM role monitor service failed to start on {dgx_node}")
                return False
            
        except subprocess.CalledProcessError as e:
            self.error(f"Failed to enable/start service on {dgx_node}: {e}")
            return False
    
    def deploy_to_dgx_node(self, dgx_node: str, bcm_headnodes: List[str]) -> bool:
        """Deploy BCM role monitor to a single DGX node"""
        self.log(f"Deploying BCM role monitor to {dgx_node}...")
        
        # Test SSH connectivity
        if not self.test_ssh_connectivity(dgx_node):
            self.error(f"Cannot connect to {dgx_node} via SSH")
            return False
        
        # Create configuration
        config = self.create_config_for_dgx(bcm_headnodes)
        
        # Deploy components
        if not self.copy_files_to_dgx(dgx_node):
            return False
        
        if not self.deploy_config_to_dgx(dgx_node, config):
            return False
        
        if not self.copy_bcm_certificates_to_dgx(dgx_node):
            return False
        
        if not self.enable_and_start_service_on_dgx(dgx_node):
            return False
        
        self.success(f"Successfully deployed BCM role monitor to {dgx_node}")
        return True
    
    def deploy(self) -> bool:
        """Main deployment process"""
        self.log("Starting BCM Role Monitor deployment...")
        
        # Discover BCM headnodes
        bcm_headnodes = self.discover_bcm_headnodes()
        if not bcm_headnodes:
            self.error("No BCM headnodes discovered - cannot proceed")
            return False
        
        # Get DGX nodes to deploy to
        if not self.dgx_nodes:
            self.error("No DGX nodes specified for deployment")
            return False
        
        self.log(f"Deploying to {len(self.dgx_nodes)} DGX node(s)...")
        
        # Deploy to each DGX node
        success_count = 0
        for dgx_node in self.dgx_nodes:
            if self.deploy_to_dgx_node(dgx_node, bcm_headnodes):
                success_count += 1
            else:
                self.error(f"Failed to deploy to {dgx_node}")
        
        # Summary
        if success_count == len(self.dgx_nodes):
            self.success(f"Successfully deployed BCM role monitor to all {success_count} DGX nodes")
            return True
        elif success_count > 0:
            self.warning(f"Deployed to {success_count}/{len(self.dgx_nodes)} DGX nodes")
            return False
        else:
            self.error("Failed to deploy to any DGX nodes")
            return False

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy BCM Role Monitor to DGX nodes')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--dgx-nodes', nargs='+', help='DGX node hostnames')
    
    args = parser.parse_args()
    
    config = {}
    if args.config and Path(args.config).exists():
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    if args.dgx_nodes:
        config['dgx_nodes'] = args.dgx_nodes
    
    deployer = BCMRoleMonitorDeployer(config)
    
    try:
        success = deployer.deploy()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print()
        deployer.error("Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        deployer.error(f"Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
