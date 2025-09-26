#!/usr/bin/env python3
"""
BCM Jobstats Deployment Automation Script - Shared Host Support

This script automates the deployment of Princeton University's jobstats monitoring platform
on BCM-managed DGX systems. It uses cmsh to verify configurations and supports dry-run mode.
This version properly handles shared hosts (e.g., same node for slurm controller and login, commonly called "slogin" nodes).

Usage:
    python deploy_jobstats_shared.py [--dry-run] [--config CONFIG_FILE]

Requirements:
    - Run from BCM head node with passwordless SSH access to all target systems
    - uv package manager for Python dependency management
    - cmsh access for BCM configuration verification
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BCMJobstatsDeployer:
    """Main deployment class for BCM jobstats automation with shared host support."""
    
    def __init__(self, dry_run: bool = False, config_file: Optional[str] = None):
        self.dry_run = dry_run
        self.dry_run_commands = []
        self.config = self._load_config(config_file)
        self.working_dir = Path("/opt/jobstats-deployment")
        
        # Repository URLs
        self.repositories = {
            'jobstats': 'https://github.com/PrincetonUniversity/jobstats.git',
            'cgroup_exporter': 'https://github.com/PrincetonUniversity/cgroup_exporter.git',
            'nvidia_gpu_prometheus_exporter': 'https://github.com/PrincetonUniversity/nvidia_gpu_prometheus_exporter.git',
            'node_exporter': 'https://github.com/prometheus/node_exporter.git'
        }
        
        # System roles and their requirements
        self.system_roles = {
            'slurm_controller': {
                'repositories': ['jobstats'],
                'components': ['prolog_epilog_scripts', 'slurmctld_epilog']
            },
            'login_nodes': {
                'repositories': ['jobstats'],
                'components': ['jobstats_command']
            },
            'dgx_nodes': {
                'repositories': ['cgroup_exporter', 'nvidia_gpu_prometheus_exporter', 'node_exporter'],
                'components': ['exporters', 'systemd_services']
            },
            'prometheus_server': {
                'repositories': [],
                'components': ['prometheus_binary', 'prometheus_config', 'systemd_service']
            },
            'grafana_server': {
                'repositories': [],
                'components': ['grafana_install', 'grafana_config', 'systemd_service']
            }
        }

    def _load_config(self, config_file: Optional[str]) -> Dict:
        """Load configuration from file or use defaults."""
        default_config = {
            'cluster_name': 'slurm',
            'prometheus_server': 'prometheus-server',
            'grafana_server': 'grafana-server',
            'prometheus_port': 9090,
            'grafana_port': 3000,
            'node_exporter_port': 9100,
            'cgroup_exporter_port': 9306,
            'nvidia_gpu_exporter_port': 9445,
            'prometheus_retention_days': 365,
            'use_existing_prometheus': False,
            'use_existing_grafana': False,
            'bcm_category_management': False,
            'slurm_category': 'slurm-category',
            'kubernetes_category': 'kubernetes-category',
            'systems': {
                'slurm_controller': [],
                'login_nodes': [],
                'dgx_nodes': [],
                'prometheus_server': [],
                'grafana_server': []
            }
        }
        
        if config_file and Path(config_file).exists():
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config

    def _run_command(self, command: str, host: Optional[str] = None, 
                    capture_output: bool = False) -> Tuple[int, str, str]:
        """Run a command locally or on a remote host."""
        if self.dry_run:
            if host:
                full_command = f"ssh {host} '{command}'"
            else:
                full_command = command
            self.dry_run_commands.append(full_command)
            logger.info(f"[DRY RUN] Would execute: {full_command}")
            return 0, "", ""
        
        try:
            if host:
                # Remote execution via SSH
                ssh_command = ['ssh', host, command]
                result = subprocess.run(ssh_command, capture_output=capture_output, 
                                      text=True, check=False)
            else:
                # Local execution
                result = subprocess.run(command, shell=True, capture_output=capture_output,
                                      text=True, check=False)
            
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            logger.error(f"Error executing command '{command}' on {host or 'localhost'}: {e}")
            return 1, "", str(e)

    def _verify_bcm_config(self) -> bool:
        """Verify BCM configuration using cmsh."""
        logger.info("Verifying BCM configuration...")
        
        # Check if cmsh is available
        returncode, stdout, stderr = self._run_command("which cmsh")
        if returncode != 0:
            logger.error("cmsh not found. Please ensure you're running from BCM head node.")
            return False
        
        # Get current BCM prolog/epilog configuration
        cmsh_commands = [
            "cmsh -c 'wlm;get prolog;get epilog;get epilogslurmctld'",
            "cmsh -c 'wlm;use slurm;show' | grep -E '(prolog|epilog)'"
        ]
        
        for cmd in cmsh_commands:
            returncode, stdout, stderr = self._run_command(cmd)
            if returncode == 0:
                logger.info(f"BCM configuration verified: {stdout.strip()}")
            else:
                logger.warning(f"Could not verify BCM config: {stderr}")
        
        return True

    def _get_cluster_name(self) -> str:
        """Get the actual cluster name from BCM."""
        logger.info("Getting cluster name from BCM...")
        
        # Try to get cluster name from cmsh
        returncode, stdout, stderr = self._run_command("cmsh -c 'show' | head -1", capture_output=True)
        if returncode == 0 and stdout.strip():
            cluster_name = stdout.strip().split()[0] if stdout.strip() else self.config['cluster_name']
            logger.info(f"Detected cluster name: {cluster_name}")
            return cluster_name
        
        logger.warning(f"Could not detect cluster name, using default: {self.config['cluster_name']}")
        return self.config['cluster_name']

    def _get_host_roles(self) -> Dict[str, List[str]]:
        """Get all roles for each unique host."""
        host_roles = {}
        
        for system_type, hosts in self.config['systems'].items():
            for host in hosts:
                if host not in host_roles:
                    host_roles[host] = []
                host_roles[host].append(system_type)
        
        return host_roles

    def _clone_repositories(self, host: str, repositories: List[str]) -> bool:
        """Clone required repositories on a host."""
        logger.info(f"Cloning repositories on {host}...")
        
        # Create working directory
        self._run_command(f"mkdir -p {self.working_dir}", host)
        
        for repo_name in repositories:
            if repo_name not in self.repositories:
                logger.error(f"Unknown repository: {repo_name}")
                continue
            
            repo_url = self.repositories[repo_name]
            repo_path = self.working_dir / repo_name
            
            # Check if repository already exists
            returncode, _, _ = self._run_command(f"test -d {repo_path}", host)
            if returncode == 0:
                logger.info(f"Repository {repo_name} already exists on {host}, updating...")
                self._run_command(f"cd {repo_path} && git pull", host)
            else:
                logger.info(f"Cloning {repo_name} on {host}...")
                self._run_command(f"cd {self.working_dir} && git clone {repo_url}", host)
        
        return True

    def _install_dependencies(self, host: str, system_role: str) -> bool:
        """Install system dependencies based on system role."""
        logger.info(f"Installing dependencies for {system_role} on {host}...")
        
        if system_role == 'dgx_nodes':
            # Install Go compiler and build tools
            self._run_command("apt update", host)
            self._run_command("apt install -y golang-go build-essential", host)
        elif system_role == 'login_nodes':
            # Install Python dependencies
            self._run_command("apt update", host)
            self._run_command("apt install -y python3-requests python3-blessed", host)
        elif system_role == 'prometheus_server':
            # Install Prometheus dependencies
            self._run_command("apt update", host)
            self._run_command("apt install -y wget", host)
        elif system_role == 'grafana_server':
            # Install Grafana dependencies
            self._run_command("apt update", host)
            self._run_command("apt install -y wget gnupg", host)
        
        return True

    def _deploy_slurm_controller(self, host: str) -> bool:
        """Deploy jobstats components on Slurm controller node."""
        logger.info(f"Deploying jobstats on Slurm controller: {host}")
        
        # Clone repositories
        self._clone_repositories(host, self.system_roles['slurm_controller']['repositories'])
        
        # Create shared storage directory
        self._run_command("mkdir -p /cm/shared/apps/slurm/var/cm", host)
        
        # Copy and setup prolog/epilog scripts
        scripts = [
            ('prolog.d/gpustats_helper.sh', 'prolog-jobstats.sh'),
            ('epilog.d/gpustats_helper.sh', 'epilog-jobstats.sh')
        ]
        
        for src, dst in scripts:
            src_path = self.working_dir / 'jobstats' / 'jobstats' / 'slurm' / src
            dst_path = f"/cm/shared/apps/slurm/var/cm/{dst}"
            
            self._run_command(f"cp {src_path} {dst_path}", host)
            self._run_command(f"chmod +x {dst_path}", host)
        
        # Create symlinks
        self._run_command("mkdir -p /cm/local/apps/slurm/var/prologs", host)
        self._run_command("mkdir -p /cm/local/apps/slurm/var/epilogs", host)
        
        self._run_command(
            "ln -sf /cm/shared/apps/slurm/var/cm/prolog-jobstats.sh "
            "/cm/local/apps/slurm/var/prologs/60-prolog-jobstats.sh", host
        )
        self._run_command(
            "ln -sf /cm/shared/apps/slurm/var/cm/epilog-jobstats.sh "
            "/cm/local/apps/slurm/var/epilogs/60-epilog-jobstats.sh", host
        )
        
        # Copy slurmctld epilog
        slurmctld_src = self.working_dir / 'jobstats' / 'jobstats' / 'slurm' / 'slurmctldepilog.sh'
        self._run_command(f"cp {slurmctld_src} /usr/local/sbin/", host)
        self._run_command("chmod +x /usr/local/sbin/slurmctldepilog.sh", host)
        
        # Configure BCM (this would need to be done manually or via cmsh API)
        logger.info("Note: BCM configuration for epilogslurmctld needs to be done manually:")
        logger.info("cmsh -> wlm -> use slurm -> set epilogslurmctld /usr/local/sbin/slurmctldepilog.sh -> commit")
        
        # BCM Imaging guidance
        logger.info("")
        logger.info("BCM IMAGING GUIDANCE:")
        logger.info("After successful deployment on this node, capture the image:")
        logger.info(f"cmsh -c 'device;use {host};grabimage -w'")
        logger.info("This will create an image that can be deployed to all Slurm controllers.")
        
        return True

    def _deploy_login_nodes(self, host: str) -> bool:
        """Deploy jobstats command on login nodes."""
        logger.info(f"Deploying jobstats command on login node: {host}")
        
        # Clone repositories
        self._clone_repositories(host, self.system_roles['login_nodes']['repositories'])
        
        # Copy jobstats files
        jobstats_files = [
            'jobstats/jobstats',
            'jobstats/jobstats.py',
            'jobstats/output_formatters.py',
            'jobstats/config.py'
        ]
        
        for file_path in jobstats_files:
            src = self.working_dir / 'jobstats' / file_path
            self._run_command(f"cp {src} /usr/local/bin/", host)
        
        self._run_command("chmod +x /usr/local/bin/jobstats", host)
        
        # Update config.py with Prometheus server
        config_update = f"""
# Update /usr/local/bin/config.py
PROM_SERVER = "http://{self.config['prometheus_server']}:{self.config['prometheus_port']}"
PROM_RETENTION_DAYS = {self.config['prometheus_retention_days']}
"""
        logger.info(f"Config update needed on {host}:{config_update}")
        
        # BCM Imaging guidance
        logger.info("")
        logger.info("BCM IMAGING GUIDANCE:")
        logger.info("After successful deployment on this node, capture the image:")
        logger.info(f"cmsh -c 'device;use {host};grabimage -w'")
        logger.info("This will create an image that can be deployed to all login nodes.")
        
        return True

    def _deploy_dgx_nodes(self, host: str) -> bool:
        """Deploy exporters on DGX compute nodes."""
        logger.info(f"Deploying exporters on DGX node: {host}")
        
        # Clone repositories
        self._clone_repositories(host, self.system_roles['dgx_nodes']['repositories'])
        
        # Build and install exporters
        exporters = [
            ('cgroup_exporter', 'cgroup_exporter'),
            ('nvidia_gpu_prometheus_exporter', 'nvidia_gpu_prometheus_exporter'),
            ('node_exporter', 'node_exporter')
        ]
        
        for repo_name, binary_name in exporters:
            repo_path = self.working_dir / repo_name
            
            if repo_name == 'node_exporter':
                # Node exporter uses make
                self._run_command(f"cd {repo_path} && make build", host)
            else:
                # Other exporters use go build
                self._run_command(f"cd {repo_path} && go build -o {binary_name}", host)
            
            self._run_command(f"cp {repo_path}/{binary_name} /usr/local/bin/", host)
        
        # Create prometheus user
        self._run_command("useradd --no-create-home --shell /bin/false prometheus || true", host)
        
        # Create systemd services
        self._create_systemd_services(host)
        
        # Handle service management based on configuration
        if self.config.get('bcm_category_management', False):
            # For BCM category management, don't enable services at systemd level
            # Services will be managed by BCM category system
            logger.info("BCM category management enabled - services will be managed by BCM categories")
            self._run_command(f"systemctl daemon-reload", host)
        else:
            # Traditional systemd service management
            services = ['cgroup_exporter', 'node_exporter', 'nvidia_gpu_prometheus_exporter']
            for service in services:
                self._run_command(f"systemctl daemon-reload", host)
                self._run_command(f"systemctl enable {service}", host)
                self._run_command(f"systemctl start {service}", host)
        
        # BCM Imaging guidance
        logger.info("")
        logger.info("BCM IMAGING GUIDANCE:")
        logger.info("After successful deployment on this node, capture the image:")
        logger.info(f"cmsh -c 'device;use {host};grabimage -w'")
        logger.info("This will create an image that can be deployed to all DGX nodes.")
        logger.info("")
        logger.info("IMPORTANT: All jobstats files are safe for BCM imaging - no exclude list changes needed.")
        
        return True

    def _setup_bcm_category_services(self) -> bool:
        """Set up BCM category-based service management for jobstats services."""
        if not self.config.get('bcm_category_management', False):
            return True
            
        logger.info("Setting up BCM category-based service management...")
        
        slurm_category = self.config.get('slurm_category', 'slurm-category')
        
        # Check if category exists, create if not
        returncode, stdout, stderr = self._run_command(f"cmsh -c 'category; list' | grep -q '{slurm_category}'")
        if returncode != 0:
            logger.info(f"Creating Slurm category: {slurm_category}")
            self._run_command(f"cmsh -c 'category; clone default {slurm_category}; commit'")
        
        # Add jobstats services to Slurm category
        services = ['cgroup_exporter', 'node_exporter', 'nvidia_gpu_prometheus_exporter']
        
        for service in services:
            logger.info(f"Adding {service} to {slurm_category} category...")
            
            # Add service to category
            self._run_command(f"cmsh -c 'category; use {slurm_category}; services; add {service}'")
            
            # Configure service with autostart and monitoring
            self._run_command(f"cmsh -c 'category; use {slurm_category}; services; use {service}; set autostart yes; set monitored yes; commit'")
        
        logger.info("")
        logger.info("BCM CATEGORY SERVICE MANAGEMENT SETUP COMPLETE:")
        logger.info(f"Jobstats services have been added to the '{slurm_category}' category.")
        logger.info("")
        logger.info("To assign DGX nodes to this category, run:")
        for host in self.config['systems']['dgx_nodes']:
            logger.info(f"  cmsh -c 'device; use {host}; set category {slurm_category}; commit'")
        logger.info("")
        logger.info("To switch nodes between Slurm and Kubernetes categories:")
        logger.info(f"  # Switch to Kubernetes: cmsh -c 'device; use <hostname>; set category {self.config.get('kubernetes_category', 'kubernetes-category')}; commit'")
        logger.info(f"  # Switch to Slurm: cmsh -c 'device; use <hostname>; set category {slurm_category}; commit'")
        logger.info("")
        logger.info("Services will automatically start/stop when nodes change categories.")
        
        return True

    def _create_systemd_services(self, host: str) -> bool:
        """Create systemd service files for exporters."""
        logger.info(f"Creating systemd services on {host}...")
        
        # Cgroup Exporter Service
        cgroup_service = f"""[Unit]
Description=Cgroup Exporter for Jobstats
After=network.target

[Service]
Type=simple
User=prometheus
Group=prometheus
ExecStart=/usr/local/bin/cgroup_exporter --config.paths /slurm --collect.fullslurm --web.listen-address=:{self.config['cgroup_exporter_port']}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        # Node Exporter Service
        node_service = f"""[Unit]
Description=Node Exporter for Jobstats
After=network.target

[Service]
Type=simple
User=prometheus
Group=prometheus
ExecStart=/usr/local/bin/node_exporter --web.listen-address=:{self.config['node_exporter_port']}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        # NVIDIA GPU Exporter Service
        gpu_service = f"""[Unit]
Description=NVIDIA GPU Prometheus Exporter for Jobstats
After=network.target

[Service]
Type=simple
User=prometheus
Group=prometheus
ExecStart=/usr/local/bin/nvidia_gpu_prometheus_exporter --web.listen-address=:{self.config['nvidia_gpu_exporter_port']}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        # Write service files
        services = [
            ('cgroup_exporter.service', cgroup_service),
            ('node_exporter.service', node_service),
            ('nvidia_gpu_prometheus_exporter.service', gpu_service)
        ]
        
        for service_name, service_content in services:
            service_path = f"/etc/systemd/system/{service_name}"
            # Create temporary file and copy to target
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                f.write(service_content)
                temp_file = f.name
            
            self._run_command(f"cp {temp_file} {service_path}", host)
            os.unlink(temp_file)
        
        return True

    def _deploy_prometheus_server(self, host: str) -> bool:
        """Deploy Prometheus server."""
        logger.info(f"Deploying Prometheus server on {host}...")
        
        # Download and install Prometheus
        prometheus_version = "2.45.0"
        self._run_command(
            f"wget https://github.com/prometheus/prometheus/releases/download/v{prometheus_version}/prometheus-{prometheus_version}.linux-amd64.tar.gz",
            host
        )
        self._run_command(f"tar xzf prometheus-{prometheus_version}.linux-amd64.tar.gz", host)
        self._run_command(f"cp prometheus-{prometheus_version}.linux-amd64/prometheus /usr/local/bin/", host)
        self._run_command(f"cp prometheus-{prometheus_version}.linux-amd64/promtool /usr/local/bin/", host)
        self._run_command("mkdir -p /etc/prometheus /var/lib/prometheus", host)
        
        # Create prometheus user
        self._run_command("useradd --no-create-home --shell /bin/false prometheus || true", host)
        self._run_command("chown prometheus:prometheus /var/lib/prometheus", host)
        
        # Create Prometheus configuration
        self._create_prometheus_config(host)
        
        # Create systemd service
        self._create_prometheus_systemd_service(host)
        
        # Enable and start service
        self._run_command("systemctl daemon-reload", host)
        self._run_command("systemctl enable prometheus", host)
        self._run_command("systemctl start prometheus", host)
        
        return True

    def _create_prometheus_config(self, host: str) -> bool:
        """Create Prometheus configuration file."""
        cluster_name = self._get_cluster_name()
        
        # Get DGX nodes from config
        dgx_nodes = self.config['systems']['dgx_nodes']
        if not dgx_nodes:
            logger.warning("No DGX nodes configured, using placeholder targets")
            dgx_nodes = ['dgx-node-01', 'dgx-node-02']
        
        # Build targets list
        targets = []
        for node in dgx_nodes:
            targets.extend([
                f"        - '{node}:{self.config['node_exporter_port']}'  # node_exporter",
                f"        - '{node}:{self.config['cgroup_exporter_port']}'  # cgroup_exporter",
                f"        - '{node}:{self.config['nvidia_gpu_exporter_port']}'  # nvidia_gpu_exporter"
            ])
        
        targets_yaml = '\n'.join(targets)
        
        prometheus_config = f"""global:
  scrape_interval: 30s
  evaluation_interval: 30s
  external_labels:
    monitor: 'jobstats-{cluster_name}'

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:{self.config['prometheus_port']}']

  - job_name: 'dgx-nodes'
    scrape_interval: 30s
    scrape_timeout: 30s
    static_configs:
      - targets: 
{targets_yaml}
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: '^go_.*'
        action: drop
"""
        
        # Write config file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(prometheus_config)
            temp_file = f.name
        
        self._run_command(f"cp {temp_file} /etc/prometheus/prometheus.yml", host)
        self._run_command("chown -R prometheus:prometheus /etc/prometheus /var/lib/prometheus", host)
        os.unlink(temp_file)
        
        return True

    def _create_prometheus_systemd_service(self, host: str) -> bool:
        """Create Prometheus systemd service file."""
        prometheus_service = f"""[Unit]
Description=Prometheus Server for Jobstats
Documentation=https://prometheus.io/docs/introduction/overview/
Wants=network-online.target
After=network-online.target

[Service]
Type=notify
User=prometheus
Group=prometheus
ExecStart=/usr/local/bin/prometheus \\
    --config.file=/etc/prometheus/prometheus.yml \\
    --storage.tsdb.path=/var/lib/prometheus/ \\
    --web.console.templates=/etc/prometheus/consoles \\
    --web.console.libraries=/etc/prometheus/console_libraries \\
    --web.listen-address=0.0.0.0:{self.config['prometheus_port']} \\
    --web.enable-lifecycle

ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(prometheus_service)
            temp_file = f.name
        
        self._run_command(f"cp {temp_file} /etc/systemd/system/prometheus.service", host)
        os.unlink(temp_file)
        
        return True

    def _deploy_grafana_server(self, host: str) -> bool:
        """Deploy Grafana server."""
        logger.info(f"Deploying Grafana server on {host}...")
        
        # Install Grafana
        self._run_command("wget -q -O - https://packages.grafana.com/gpg.key | apt-key add -", host)
        self._run_command('echo "deb https://packages.grafana.com/oss/deb stable main" > /etc/apt/sources.list.d/grafana.list', host)
        self._run_command("apt update", host)
        self._run_command("apt install -y grafana", host)
        
        # Enable and start service
        self._run_command("systemctl enable grafana-server", host)
        self._run_command("systemctl start grafana-server", host)
        
        logger.info(f"Grafana installed on {host}. Access at http://{host}:{self.config['grafana_port']}")
        logger.info("Default credentials: admin/admin")
        
        return True

    def _handle_existing_prometheus(self) -> bool:
        """Provide guidance for existing Prometheus configuration."""
        logger.info("Using existing Prometheus server - manual configuration required")
        logger.info("=" * 60)
        logger.info("PROMETHEUS CONFIGURATION REQUIRED:")
        logger.info("=" * 60)
        
        # Get DGX nodes from config
        dgx_nodes = self.config['systems']['dgx_nodes']
        if not dgx_nodes:
            logger.warning("No DGX nodes configured, using placeholder targets")
            dgx_nodes = ['dgx-node-01', 'dgx-node-02']
        
        # Build targets list
        targets = []
        for node in dgx_nodes:
            targets.extend([
                f"        - '{node}:{self.config['node_exporter_port']}'  # node_exporter",
                f"        - '{node}:{self.config['cgroup_exporter_port']}'  # cgroup_exporter",
                f"        - '{node}:{self.config['nvidia_gpu_exporter_port']}'  # nvidia_gpu_exporter"
            ])
        
        targets_yaml = '\n'.join(targets)
        cluster_name = self._get_cluster_name()
        
        prometheus_config = f"""# Add this job to your existing prometheus.yml scrape_configs:
  - job_name: 'jobstats-dgx-nodes'
    scrape_interval: 30s
    scrape_timeout: 30s
    static_configs:
      - targets: 
{targets_yaml}
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: '^go_.*'
        action: drop
      - source_labels: [__name__]
        regex: '^slurm_.*'
        target_label: 'cluster'
        replacement: '{cluster_name}'
"""
        
        logger.info(prometheus_config)
        logger.info("=" * 60)
        logger.info("INSTRUCTIONS:")
        logger.info("1. Add the above job configuration to your existing prometheus.yml")
        logger.info("2. Reload Prometheus configuration: curl -X POST http://localhost:9090/-/reload")
        logger.info("3. Verify targets are discovered: http://localhost:9090/targets")
        logger.info("=" * 60)
        
        return True

    def _handle_existing_grafana(self) -> bool:
        """Provide guidance for existing Grafana configuration."""
        logger.info("Using existing Grafana server - manual configuration required")
        logger.info("=" * 60)
        logger.info("GRAFANA CONFIGURATION REQUIRED:")
        logger.info("=" * 60)
        
        prometheus_url = f"http://{self.config['prometheus_server']}:{self.config['prometheus_port']}"
        
        logger.info("1. ADD PROMETHEUS DATA SOURCE:")
        logger.info(f"   - URL: {prometheus_url}")
        logger.info("   - Access: Server (default)")
        logger.info("   - Basic Auth: Disabled (unless your Prometheus requires it)")
        logger.info("   - Skip TLS Verify: Yes (unless using HTTPS)")
        logger.info("")
        logger.info("2. IMPORT JOBSTATS DASHBOARDS:")
        logger.info("   - Dashboard ID: 1860 (Node Exporter Full)")
        logger.info("   - Dashboard ID: 1443 (NVIDIA GPU Metrics)")
        logger.info("   - Or create custom dashboards using jobstats metrics")
        logger.info("")
        logger.info("3. KEY METRICS TO MONITOR:")
        logger.info("   - slurm_job_* (job statistics)")
        logger.info("   - nvidia_* (GPU metrics)")
        logger.info("   - node_* (system metrics)")
        logger.info("   - cgroup_* (resource usage)")
        logger.info("")
        logger.info("4. ACCESS GRAFANA:")
        logger.info(f"   - URL: http://{self.config['grafana_server']}:{self.config['grafana_port']}")
        logger.info("   - Default credentials: admin/admin (change on first login)")
        logger.info("=" * 60)
        
        return True

    def _deploy_host(self, host: str, roles: List[str]) -> bool:
        """Deploy all required components for a host with multiple roles."""
        logger.info(f"Deploying to {host} with roles: {', '.join(roles)}")
        
        deployment_success = True
        
        # Install dependencies for all roles (avoid duplicates)
        unique_deps = set()
        for role in roles:
            if role in self.system_roles:
                unique_deps.add(role)
        
        for dep_role in unique_deps:
            if not self._install_dependencies(host, dep_role):
                logger.error(f"Failed to install dependencies for {dep_role} on {host}")
                deployment_success = False
        
        # Deploy components for each role
        for role in roles:
            try:
                if role == 'slurm_controller':
                    success = self._deploy_slurm_controller(host)
                elif role == 'login_nodes':
                    success = self._deploy_login_nodes(host)
                elif role == 'dgx_nodes':
                    success = self._deploy_dgx_nodes(host)
                elif role == 'prometheus_server':
                    success = self._deploy_prometheus_server(host)
                elif role == 'grafana_server':
                    success = self._deploy_grafana_server(host)
                else:
                    logger.error(f"Unknown system type: {role}")
                    success = False
                
                if not success:
                    logger.error(f"Deployment failed for {role} on {host}")
                    deployment_success = False
                else:
                    logger.info(f"Successfully deployed {role} on {host}")
            
            except Exception as e:
                logger.error(f"Error deploying {role} to {host}: {e}")
                deployment_success = False
        
        return deployment_success

    def _write_dry_run_output(self) -> None:
        """Write dry-run commands to output file."""
        output_file = "dry-run-output.txt"
        with open(output_file, 'w') as f:
            f.write("BCM Jobstats Deployment - Dry Run Commands\n")
            f.write("=" * 50 + "\n\n")
            for i, command in enumerate(self.dry_run_commands, 1):
                f.write(f"{i:3d}. {command}\n")
        
        logger.info(f"Dry-run commands written to {output_file}")

    def deploy(self) -> bool:
        """Main deployment method."""
        logger.info("Starting BCM Jobstats deployment...")
        
        if self.dry_run:
            logger.info("Running in DRY-RUN mode - no actual changes will be made")
        
        # Verify BCM configuration
        if not self._verify_bcm_config():
            logger.error("BCM configuration verification failed")
            return False
        
        # Get unique hosts and their roles
        host_roles = self._get_host_roles()
        
        if not host_roles:
            logger.warning("No hosts configured for deployment")
            return True
        
        logger.info(f"Deploying to {len(host_roles)} unique hosts:")
        for host, roles in host_roles.items():
            logger.info(f"  {host}: {', '.join(roles)}")
        
        # Handle existing Prometheus/Grafana installations
        if self.config.get('use_existing_prometheus', False):
            logger.info("Existing Prometheus detected - providing configuration guidance")
            self._handle_existing_prometheus()
        
        if self.config.get('use_existing_grafana', False):
            logger.info("Existing Grafana detected - providing configuration guidance")
            self._handle_existing_grafana()
        
        # Set up BCM category-based service management if enabled
        if self.config.get('bcm_category_management', False):
            logger.info("BCM category-based service management enabled")
            if not self._setup_bcm_category_services():
                logger.error("Failed to set up BCM category services")
                return False
        
        # Deploy to each unique host
        deployment_success = True
        
        for host, roles in host_roles.items():
            logger.info(f"Processing host: {host}")
            
            try:
                # Skip Prometheus/Grafana deployment if using existing installations
                filtered_roles = []
                for role in roles:
                    if role == 'prometheus_server' and self.config.get('use_existing_prometheus', False):
                        logger.info(f"Skipping Prometheus deployment on {host} (using existing)")
                        continue
                    elif role == 'grafana_server' and self.config.get('use_existing_grafana', False):
                        logger.info(f"Skipping Grafana deployment on {host} (using existing)")
                        continue
                    filtered_roles.append(role)
                
                if filtered_roles:
                    success = self._deploy_host(host, filtered_roles)
                    if not success:
                        logger.error(f"Deployment failed for {host}")
                        deployment_success = False
                    else:
                        logger.info(f"Deployment completed successfully for {host}")
                else:
                    logger.info(f"No deployment needed for {host} (all roles skipped)")
            
            except Exception as e:
                logger.error(f"Error deploying to {host}: {e}")
                deployment_success = False
        
        if self.dry_run:
            self._write_dry_run_output()
        
        return deployment_success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="BCM Jobstats Deployment Automation with Shared Host Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Dry run to see what commands would be executed
    python deploy_jobstats_shared.py --dry-run
    
    # Deploy with lab configuration (shared hosts)
    python deploy_jobstats_shared.py --config config-lab.json
    
    # Deploy with custom configuration
    python deploy_jobstats_shared.py --config my_config.json
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what commands would be executed without making changes'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration JSON file'
    )
    
    args = parser.parse_args()
    
    # Create deployer instance
    deployer = BCMJobstatsDeployer(dry_run=args.dry_run, config_file=args.config)
    
    # Run deployment
    success = deployer.deploy()
    
    if success:
        logger.info("Deployment completed successfully!")
        if args.dry_run:
            logger.info("Check dry-run-output.txt for the list of commands that would be executed.")
        sys.exit(0)
    else:
        logger.error("Deployment failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
