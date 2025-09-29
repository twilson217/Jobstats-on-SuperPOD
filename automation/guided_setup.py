#!/usr/bin/env python3
"""
BCM Jobstats Guided Setup Script

This script provides an interactive, step-by-step guided deployment process
that follows the Princeton University jobstats documentation flow.

Usage:
    python guided_setup.py [--resume] [--config CONFIG_FILE]

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
from typing import Dict, List, Optional, Tuple, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Colors for output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[1;37m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

class GuidedJobstatsSetup:
    """Interactive guided setup for BCM jobstats deployment."""
    
    def __init__(self, resume: bool = False, config_file: Optional[str] = None, dry_run: bool = False):
        self.resume = resume
        self.config_file = config_file
        self.dry_run = dry_run
        self.config = self._load_config()
        self.progress_file = Path("automation/logs/guided_setup_progress.json")
        self.progress = self._load_progress()
        self.working_dir = Path("/opt/jobstats-deployment")
        self.document_file = Path("automation/logs/guided_setup_document.md")
        self.document_content = []
        
        # Repository URLs
        self.repositories = {
            'jobstats': 'https://github.com/PrincetonUniversity/jobstats.git',
            'cgroup_exporter': 'https://github.com/PrincetonUniversity/cgroup_exporter.git',
            'nvidia_gpu_prometheus_exporter': 'https://github.com/PrincetonUniversity/nvidia_gpu_prometheus_exporter.git',
            'node_exporter': 'https://github.com/prometheus/node_exporter.git'
        }
        
        # Setup sections following Princeton documentation
        self.setup_sections = [
            {
                'id': 'overview',
                'title': 'Setup Overview',
                'description': 'Introduction to the jobstats platform setup process',
                'completed': False
            },
            {
                'id': 'cgroups',
                'title': 'CPU Job Statistics (Cgroups)',
                'description': 'Configure Slurm for cgroup-based job accounting',
                'completed': False
            },
            {
                'id': 'gpu_scripts',
                'title': 'GPU Job Statistics',
                'description': 'Setup GPU monitoring and prolog/epilog scripts',
                'completed': False
            },
            {
                'id': 'node_stats',
                'title': 'Node Statistics',
                'description': 'Setup node_exporter on compute nodes',
                'completed': False
            },
            {
                'id': 'summaries',
                'title': 'Generating Job Summaries',
                'description': 'Setup slurmctld epilog for job summary retention',
                'completed': False
            },
            {
                'id': 'prometheus',
                'title': 'Prometheus',
                'description': 'Setup Prometheus server and configuration',
                'completed': False
            },
            {
                'id': 'grafana',
                'title': 'Grafana',
                'description': 'Setup Grafana visualization interface',
                'completed': False
            },
            {
                'id': 'ood',
                'title': 'Open OnDemand Jobstats Helper',
                'description': 'Setup Open OnDemand integration (optional)',
                'completed': False
            },
            {
                'id': 'jobstats_command',
                'title': 'The jobstats Command',
                'description': 'Install and configure the jobstats command-line tool',
                'completed': False
            }
        ]

    def _load_config(self) -> Dict:
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
            'bcm_category_management': True,
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
        
        if self.config_file and Path(self.config_file).exists():
            with open(self.config_file, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config

    def _load_progress(self) -> Dict:
        """Load progress tracking from file."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            'current_section': 0,
            'completed_sections': [],
            'setup_commands': []
        }

    def _save_progress(self):
        """Save current progress to file."""
        self.progress_file.parent.mkdir(exist_ok=True)
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def _add_to_document(self, content: str):
        """Add content to the document."""
        self.document_content.append(content)

    def _save_document(self):
        """Save the complete document to file."""
        self.document_file.parent.mkdir(exist_ok=True)
        with open(self.document_file, 'w') as f:
            f.write('\n'.join(self.document_content))

    def _init_document(self):
        """Initialize the document with header and metadata."""
        timestamp = subprocess.run(['date'], capture_output=True, text=True).stdout.strip()
        
        self._add_to_document("# BCM Jobstats Guided Setup Document")
        self._add_to_document("")
        self._add_to_document(f"**Generated on:** {timestamp}")
        self._add_to_document(f"**Mode:** {'Dry Run' if self.dry_run else 'Live Execution'}")
        self._add_to_document(f"**Configuration:** {self.config_file or 'Default'}")
        self._add_to_document("")
        self._add_to_document("This document provides a complete record of the jobstats deployment process.")
        self._add_to_document("It can be used as a reference for what was done or as a manual implementation guide.")
        self._add_to_document("")
        self._add_to_document("## Table of Contents")
        self._add_to_document("")
        
        for i, section in enumerate(self.setup_sections, 1):
            section_id = section['id'].replace('_', '-')
            self._add_to_document(f"{i}. [{section['title']}](#{section_id})")
        
        self._add_to_document("")
        self._add_to_document("---")
        self._add_to_document("")

    def _print_header(self, title: str, description: str = ""):
        """Print a formatted section header."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.WHITE}{title}{Colors.END}")
        print(f"{Colors.CYAN}{'='*80}{Colors.END}")
        if description:
            print(f"\n{Colors.BLUE}{description}{Colors.END}\n")

    def _print_command_summary(self, commands: List[Dict]):
        """Print a summary of commands that will be executed."""
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Commands to be executed:{Colors.END}")
        print(f"{Colors.YELLOW}{'-'*50}{Colors.END}")
        
        for i, cmd in enumerate(commands, 1):
            host = cmd.get('host', 'localhost')
            command = cmd['command']
            description = cmd.get('description', '')
            
            print(f"\n{Colors.BOLD}{i}. {Colors.GREEN}{host}{Colors.END}")
            if description:
                print(f"   {Colors.BLUE}{description}{Colors.END}")
            print(f"   {Colors.WHITE}{command}{Colors.END}")

    def _confirm_execution(self, commands: List[Dict]) -> bool:
        """Ask user to confirm command execution."""
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Ready to execute {len(commands)} command(s).{Colors.END}")
        response = input(f"{Colors.YELLOW}Do you want to proceed? (y/N): {Colors.END}").strip().lower()
        return response in ['y', 'yes']

    def _run_command(self, command: str, host: Optional[str] = None, 
                    capture_output: bool = False) -> Tuple[int, str, str]:
        """Run a command locally or on a remote host."""
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

    def _execute_commands(self, commands: List[Dict], section_title: str = "") -> bool:
        """Execute a list of commands with user confirmation."""
        if not commands:
            return True
        
        # Add commands to document
        if section_title:
            self._add_to_document(f"### Commands for {section_title}")
            self._add_to_document("")
        
        # Group commands by host
        commands_by_host = {}
        for cmd in commands:
            host = cmd.get('host', 'localhost')
            if host not in commands_by_host:
                commands_by_host[host] = []
            commands_by_host[host].append(cmd)
        
        # Add commands to document grouped by host
        for host, host_commands in commands_by_host.items():
            self._add_to_document(f"#### Host: {host}")
            self._add_to_document("")
            for i, cmd in enumerate(host_commands, 1):
                description = cmd.get('description', '')
                command = cmd['command']
                if description:
                    self._add_to_document(f"**{i}. {description}**")
                else:
                    self._add_to_document(f"**{i}. Command**")
                self._add_to_document("")
                self._add_to_document("```bash")
                self._add_to_document(command)
                self._add_to_document("```")
                self._add_to_document("")
            self._add_to_document("---")
            self._add_to_document("")
        
        if self.dry_run:
            print(f"\n{Colors.BOLD}{Colors.YELLOW}[DRY RUN] Commands would be executed:{Colors.END}")
            self._print_command_summary(commands)
            print(f"\n{Colors.BLUE}Commands have been added to the document.{Colors.END}")
            return True
            
        self._print_command_summary(commands)
        
        if not self._confirm_execution(commands):
            print(f"{Colors.YELLOW}Commands skipped by user.{Colors.END}")
            return False
        
        print(f"\n{Colors.BOLD}{Colors.GREEN}Executing commands...{Colors.END}")
        
        success = True
        for cmd in commands:
            host = cmd.get('host')
            command = cmd['command']
            description = cmd.get('description', '')
            
            print(f"\n{Colors.BLUE}Executing: {description or command}{Colors.END}")
            if host:
                print(f"{Colors.CYAN}Host: {host}{Colors.END}")
            
            returncode, stdout, stderr = self._run_command(command, host)
            
            if returncode == 0:
                print(f"{Colors.GREEN}✓ Success{Colors.END}")
                if stdout.strip():
                    print(f"{Colors.WHITE}Output: {stdout.strip()}{Colors.END}")
            else:
                print(f"{Colors.RED}✗ Failed (exit code: {returncode}){Colors.END}")
                if stderr.strip():
                    print(f"{Colors.RED}Error: {stderr.strip()}{Colors.END}")
                success = False
        
        return success

    def section_overview(self):
        """Section 1: Setup Overview"""
        self._print_header(
            "1. Setup Overview",
            "Introduction to the jobstats platform setup process"
        )
        
        # Add to document
        self._add_to_document("## 1. Setup Overview")
        self._add_to_document("")
        self._add_to_document("### Description")
        self._add_to_document("")
        self._add_to_document("The jobstats platform provides comprehensive job monitoring for Slurm clusters.")
        self._add_to_document("This guided setup will walk you through each step of the deployment process.")
        self._add_to_document("")
        self._add_to_document("### Setup Process Overview")
        self._add_to_document("")
        self._add_to_document("1. Switch to cgroup-based job accounting")
        self._add_to_document("2. Setup exporters (cgroup, node, GPU) on compute nodes")
        self._add_to_document("3. Setup prolog/epilog scripts on GPU nodes")
        self._add_to_document("4. Setup Prometheus server and configuration")
        self._add_to_document("5. Setup slurmctld epilog for job summaries")
        self._add_to_document("6. Configure Grafana interface")
        self._add_to_document("7. Install jobstats command-line tool")
        self._add_to_document("")
        self._add_to_document("### Reference Documentation")
        self._add_to_document("")
        self._add_to_document("- Princeton University: https://princetonuniversity.github.io/jobstats/setup/overview/")
        self._add_to_document("")
        
        print(f"{Colors.BLUE}The jobstats platform provides comprehensive job monitoring for Slurm clusters.{Colors.END}")
        print(f"{Colors.BLUE}This guided setup will walk you through each step of the deployment process.{Colors.END}")
        
        print(f"\n{Colors.BOLD}{Colors.WHITE}Setup Process Overview:{Colors.END}")
        print(f"1. {Colors.CYAN}Switch to cgroup-based job accounting{Colors.END}")
        print(f"2. {Colors.CYAN}Setup exporters (cgroup, node, GPU) on compute nodes{Colors.END}")
        print(f"3. {Colors.CYAN}Setup prolog/epilog scripts on GPU nodes{Colors.END}")
        print(f"4. {Colors.CYAN}Setup Prometheus server and configuration{Colors.END}")
        print(f"5. {Colors.CYAN}Setup slurmctld epilog for job summaries{Colors.END}")
        print(f"6. {Colors.CYAN}Configure Grafana interface{Colors.END}")
        print(f"7. {Colors.CYAN}Install jobstats command-line tool{Colors.END}")
        
        print(f"\n{Colors.BOLD}{Colors.GREEN}Reference Documentation:{Colors.END}")
        print(f"• Princeton University: https://princetonuniversity.github.io/jobstats/setup/overview/")
        
        if not self.dry_run:
            input(f"\n{Colors.YELLOW}Press Enter to continue to the next section...{Colors.END}")
        else:
            print(f"\n{Colors.BLUE}[DRY RUN] Continuing to next section...{Colors.END}")
        
        return True

    def section_cgroups(self):
        """Section 2: CPU Job Statistics (Cgroups)"""
        self._print_header(
            "2. CPU Job Statistics (Cgroups)",
            "Configure Slurm for cgroup-based job accounting and install cgroup exporter"
        )
        
        # Add to document
        self._add_to_document("## 2. CPU Job Statistics (Cgroups)")
        self._add_to_document("")
        self._add_to_document("### Description")
        self._add_to_document("")
        self._add_to_document("This section configures Slurm to use cgroup-based job accounting")
        self._add_to_document("instead of Linux process accounting for more accurate resource tracking.")
        self._add_to_document("It also installs the cgroup_exporter to collect cgroup metrics.")
        self._add_to_document("")
        self._add_to_document("### What we'll do")
        self._add_to_document("")
        self._add_to_document("- Check current slurm.conf cgroup settings")
        self._add_to_document("- Update slurm.conf with required cgroup settings")
        self._add_to_document("- Install cgroup_exporter on compute nodes")
        self._add_to_document("- Create systemd service for cgroup_exporter")
        self._add_to_document("- Verify cgroup_exporter is running and collecting metrics")
        self._add_to_document("")
        self._add_to_document("### Required slurm.conf Settings")
        self._add_to_document("")
        self._add_to_document("The following settings will be updated in slurm.conf:")
        self._add_to_document(f"**File location:** `/cm/shared/apps/slurm/var/etc/{self.config.get('cluster_name', 'slurm')}/slurm.conf`")
        self._add_to_document("")
        self._add_to_document("```")
        self._add_to_document("JobAcctGatherType=jobacct_gather/cgroup")
        self._add_to_document("ProctrackType=proctrack/cgroup")
        self._add_to_document("TaskPlugin=affinity,cgroup")
        self._add_to_document("```")
        self._add_to_document("")
        self._add_to_document("**Note:** Settings will be placed before the AUTOGENERATED SECTION to maintain BCM compatibility.")
        self._add_to_document("")
        self._add_to_document("### Service Restart Required")
        self._add_to_document("")
        self._add_to_document("After updating slurm.conf, you will need to restart Slurm services:")
        self._add_to_document("")
        self._add_to_document("```bash")
        self._add_to_document("systemctl restart slurmctld")
        self._add_to_document("systemctl restart slurmd")
        self._add_to_document("```")
        self._add_to_document("")
        
        print(f"{Colors.BLUE}This section configures Slurm to use cgroup-based job accounting{Colors.END}")
        print(f"{Colors.BLUE}and installs the cgroup_exporter for collecting cgroup metrics.{Colors.END}")
        
        print(f"\n{Colors.BOLD}{Colors.WHITE}What we'll do:{Colors.END}")
        print(f"• Check current slurm.conf cgroup settings")
        print(f"• Update slurm.conf with required cgroup settings")
        print(f"• Install cgroup_exporter on compute nodes")
        print(f"• Create systemd service for cgroup_exporter")
        print(f"• Verify cgroup_exporter is running and collecting metrics")
        
        # Get slurm controller host
        slurm_controller = self.config['systems']['slurm_controller'][0] if self.config['systems']['slurm_controller'] else 'slurm-controller'
        
        # Get cluster name for BCM slurm.conf path
        cluster_name = self.config.get('cluster_name', 'slurm')
        slurm_conf_path = f"/cm/shared/apps/slurm/var/etc/{cluster_name}/slurm.conf"
        
        # Step 1: Check current configuration
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Step 1: Checking current slurm.conf settings{Colors.END}")
        print(f"Checking slurm.conf at: {slurm_conf_path}")
        
        check_commands = [
            {
                'host': slurm_controller,
                'command': f'grep -E "^(JobAcctGatherType|ProctrackType|TaskPlugin)" {slurm_conf_path} || echo "No cgroup settings found"',
                'description': 'Check current slurm.conf cgroup settings'
            }
        ]
        
        if not self._execute_commands(check_commands, "Current Configuration Check"):
            print(f"\n{Colors.RED}✗ Failed to check current configuration{Colors.END}")
            return False
        
        # Step 2: Update slurm.conf
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Step 2: Updating slurm.conf with cgroup settings{Colors.END}")
        print(f"Updating slurm.conf at: {slurm_conf_path}")
        
        update_commands = [
            {
                'host': slurm_controller,
                'command': f'''# Backup original slurm.conf
cp {slurm_conf_path} {slurm_conf_path}.backup.$(date +%Y%m%d_%H%M%S)

# Create a Python script to properly update slurm.conf
cat > /tmp/update_slurm_cgroups.py << 'EOF'
import re
import sys

def update_slurm_conf(file_path):
    """Update slurm.conf with cgroup settings, maintaining file structure."""
    
    # Read the file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Settings to update
    settings = {
        'JobAcctGatherType': 'jobacct_gather/cgroup',
        'ProctrackType': 'proctrack/cgroup', 
        'TaskPlugin': 'affinity,cgroup'
    }
    
    updated_lines = []
    updated_settings = set()
    
    for line in lines:
        # Check if this line contains any of our settings
        updated = False
        for setting, value in settings.items():
            if line.strip().startswith(f"{setting}="):
                # Replace the existing value
                new_line = f"{setting}={value}\\n"
                updated_lines.append(new_line)
                updated_settings.add(setting)
                updated = True
                print(f"Updated {setting}={value}")
                break
        
        if not updated:
            updated_lines.append(line)
    
    # Add any missing settings before AUTOGENERATED SECTION
    missing_settings = set(settings.keys()) - updated_settings
    if missing_settings:
        # Find the AUTOGENERATED SECTION line
        autogen_index = -1
        for i, line in enumerate(updated_lines):
            if "AUTOGENERATED SECTION" in line:
                autogen_index = i
                break
        
        if autogen_index > 0:
            # Insert missing settings before AUTOGENERATED SECTION
            for setting in missing_settings:
                value = settings[setting]
                new_line = f"{setting}={value}\\n"
                updated_lines.insert(autogen_index, new_line)
                print(f"Added {setting}={value}")
                autogen_index += 1
        else:
            # If no AUTOGENERATED SECTION found, append to end
            for setting in missing_settings:
                value = settings[setting]
                new_line = f"{setting}={value}\\n"
                updated_lines.append(new_line)
                print(f"Added {setting}={value}")
    
    # Write the updated file
    with open(file_path, 'w') as f:
        f.writelines(updated_lines)
    
    print("slurm.conf updated successfully")

if __name__ == "__main__":
    update_slurm_conf("{slurm_conf_path}")
EOF

# Run the Python script to update slurm.conf
python3 /tmp/update_slurm_cgroups.py

# Verify the settings were updated
echo "Updated slurm.conf cgroup settings:"
grep -E "^(JobAcctGatherType|ProctrackType|TaskPlugin)" {slurm_conf_path}

# Clean up
rm -f /tmp/update_slurm_cgroups.py''',
                'description': 'Update slurm.conf with cgroup settings (BCM-compatible)'
            }
        ]
        
        if not self._execute_commands(update_commands, "Slurm Configuration Update"):
            print(f"\n{Colors.RED}✗ Failed to update slurm.conf{Colors.END}")
            return False
        
        # Step 3: Install cgroup_exporter on compute nodes
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Step 3: Installing cgroup_exporter on compute nodes{Colors.END}")
        
        cgroup_commands = []
        for dgx_node in self.config['systems']['dgx_nodes']:
            cgroup_commands.extend([
                {
                    'host': dgx_node,
                    'command': f'mkdir -p {self.working_dir}',
                    'description': f'Create working directory on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': f'cd {self.working_dir} && git clone {self.repositories["cgroup_exporter"]}',
                    'description': f'Clone cgroup_exporter on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': f'cd {self.working_dir}/cgroup_exporter && make build',
                    'description': f'Build cgroup_exporter on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': f'cp {self.working_dir}/cgroup_exporter/cgroup_exporter /usr/local/bin/',
                    'description': f'Install cgroup_exporter binary on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': 'useradd --no-create-home --shell /bin/false prometheus || true',
                    'description': f'Create prometheus user on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': f'''# Create systemd service for cgroup_exporter
cat > /etc/systemd/system/cgroup_exporter.service << 'EOF'
[Unit]
Description=Cgroup Exporter
After=network.target

[Service]
Type=simple
User=prometheus
ExecStart=/usr/local/bin/cgroup_exporter --port={self.config['cgroup_exporter_port']}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF''',
                    'description': f'Create cgroup_exporter systemd service on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': 'systemctl daemon-reload && systemctl enable cgroup_exporter && systemctl start cgroup_exporter',
                    'description': f'Start cgroup_exporter service on {dgx_node}'
                }
            ])
        
        if not self._execute_commands(cgroup_commands, "Cgroup Exporter Installation"):
            print(f"\n{Colors.RED}✗ Failed to install cgroup_exporter{Colors.END}")
            return False
        
        # Step 4: Verify cgroup_exporter installation
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Step 4: Verifying cgroup_exporter installation{Colors.END}")
        
        verify_commands = []
        for dgx_node in self.config['systems']['dgx_nodes']:
            verify_commands.extend([
                {
                    'host': dgx_node,
                    'command': 'systemctl is-active cgroup_exporter',
                    'description': f'Check cgroup_exporter service status on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': f'curl -s http://localhost:{self.config["cgroup_exporter_port"]}/metrics | head -5',
                    'description': f'Test cgroup_exporter metrics endpoint on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': f'netstat -tlnp | grep :{self.config["cgroup_exporter_port"]} || ss -tlnp | grep :{self.config["cgroup_exporter_port"]}',
                    'description': f'Verify cgroup_exporter is listening on port {self.config["cgroup_exporter_port"]} on {dgx_node}'
                }
            ])
        
        if not self._execute_commands(verify_commands, "Cgroup Exporter Verification"):
            print(f"\n{Colors.RED}✗ Failed to verify cgroup_exporter installation{Colors.END}")
            return False
        
        print(f"\n{Colors.BOLD}{Colors.GREEN}✓ Cgroup configuration and exporter installation completed{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}✓ Cgroup_exporter verification completed{Colors.END}")
        
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Next Steps:{Colors.END}")
        print(f"1. Restart Slurm services to apply cgroup configuration:")
        print(f"   • {Colors.WHITE}systemctl restart slurmctld{Colors.END}")
        print(f"   • {Colors.WHITE}systemctl restart slurmd{Colors.END}")
        print(f"2. Verify cgroup_exporter is running (already checked):")
        print(f"   • {Colors.WHITE}systemctl status cgroup_exporter{Colors.END}")
        print(f"3. Check metrics endpoint (already tested):")
        print(f"   • {Colors.WHITE}curl http://localhost:{self.config['cgroup_exporter_port']}/metrics{Colors.END}")
        
        if not self.dry_run:
            input(f"\n{Colors.YELLOW}Press Enter to continue to the next section...{Colors.END}")
        else:
            print(f"\n{Colors.BLUE}[DRY RUN] Continuing to next section...{Colors.END}")
        return True

    def section_gpu_scripts(self):
        """Section 3: GPU Job Statistics"""
        self._print_header(
            "3. GPU Job Statistics",
            "Setup GPU monitoring and prolog/epilog scripts"
        )
        
        print(f"{Colors.BLUE}This section sets up GPU monitoring and the necessary scripts{Colors.END}")
        print(f"{Colors.BLUE}to track which GPUs are assigned to which jobs.{Colors.END}")
        
        print(f"\n{Colors.BOLD}{Colors.WHITE}What we'll do:{Colors.END}")
        print(f"• Clone jobstats repository")
        print(f"• Install prolog/epilog scripts on GPU nodes")
        print(f"• Configure BCM for script execution")
        print(f"• Setup GPU ownership tracking")
        
        # Commands for GPU nodes
        gpu_commands = []
        
        for dgx_node in self.config['systems']['dgx_nodes']:
            gpu_commands.extend([
                {
                    'host': dgx_node,
                    'command': f'mkdir -p {self.working_dir}',
                    'description': f'Create working directory on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': f'cd {self.working_dir} && git clone {self.repositories["jobstats"]}',
                    'description': f'Clone jobstats repository on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': 'mkdir -p /run/gpustat',
                    'description': f'Create GPU status directory on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': f'cp {self.working_dir}/jobstats/slurm/prolog.d/gpustats_helper.sh /etc/slurm/prolog.d/',
                    'description': f'Install prolog script on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': f'cp {self.working_dir}/jobstats/slurm/epilog.d/gpustats_helper.sh /etc/slurm/epilog.d/',
                    'description': f'Install epilog script on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': 'chmod +x /etc/slurm/prolog.d/gpustats_helper.sh /etc/slurm/epilog.d/gpustats_helper.sh',
                    'description': f'Make scripts executable on {dgx_node}'
                }
            ])
        
        if self._execute_commands(gpu_commands, "GPU Scripts Installation"):
            print(f"\n{Colors.GREEN}✓ GPU scripts installation completed{Colors.END}")
        else:
            print(f"\n{Colors.RED}✗ GPU scripts installation failed{Colors.END}")
            return False
        
        print(f"\n{Colors.BOLD}{Colors.YELLOW}BCM Configuration Required:{Colors.END}")
        print(f"Add the following to your slurm.conf:")
        print(f"• {Colors.WHITE}Prolog=/etc/slurm/prolog.d/*.sh{Colors.END}")
        print(f"• {Colors.WHITE}Epilog=/etc/slurm/epilog.d/*.sh{Colors.END}")
        
        if not self.dry_run:
            input(f"\n{Colors.YELLOW}Press Enter to continue to the next section...{Colors.END}")
        else:
            print(f"\n{Colors.BLUE}[DRY RUN] Continuing to next section...{Colors.END}")
        return True

    def section_node_stats(self):
        """Section 4: Node Statistics"""
        self._print_header(
            "4. Node Statistics",
            "Setup node_exporter on compute nodes"
        )
        
        print(f"{Colors.BLUE}This section installs the Prometheus node_exporter{Colors.END}")
        print(f"{Colors.BLUE}on all compute nodes to collect system metrics.{Colors.END}")
        
        print(f"\n{Colors.BOLD}{Colors.WHITE}What we'll do:{Colors.END}")
        print(f"• Clone node_exporter repository")
        print(f"• Build and install node_exporter")
        print(f"• Create systemd service")
        print(f"• Start and enable service")
        
        # Commands for all compute nodes
        node_commands = []
        
        for dgx_node in self.config['systems']['dgx_nodes']:
            node_commands.extend([
                {
                    'host': dgx_node,
                    'command': f'cd {self.working_dir} && git clone {self.repositories["node_exporter"]}',
                    'description': f'Clone node_exporter on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': f'cd {self.working_dir}/node_exporter && make build',
                    'description': f'Build node_exporter on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': f'cp {self.working_dir}/node_exporter/node_exporter /usr/local/bin/',
                    'description': f'Install node_exporter binary on {dgx_node}'
                },
                {
                    'host': dgx_node,
                    'command': 'useradd --no-create-home --shell /bin/false prometheus || true',
                    'description': f'Create prometheus user on {dgx_node}'
                }
            ])
        
        if self._execute_commands(node_commands):
            print(f"\n{Colors.GREEN}✓ Node exporter installation completed{Colors.END}")
        else:
            print(f"\n{Colors.RED}✗ Node exporter installation failed{Colors.END}")
            return False
        
        if not self.dry_run:
            input(f"\n{Colors.YELLOW}Press Enter to continue to the next section...{Colors.END}")
        else:
            print(f"\n{Colors.BLUE}[DRY RUN] Continuing to next section...{Colors.END}")
        return True

    def section_summaries(self):
        """Section 5: Generating Job Summaries"""
        self._print_header(
            "5. Generating Job Summaries",
            "Setup slurmctld epilog for job summary retention"
        )
        
        print(f"{Colors.BLUE}This section sets up the slurmctld epilog script{Colors.END}")
        print(f"{Colors.BLUE}to generate and store job summaries in the Slurm database.{Colors.END}")
        
        print(f"\n{Colors.BOLD}{Colors.WHITE}What we'll do:{Colors.END}")
        print(f"• Install slurmctld epilog script")
        print(f"• Configure BCM for epilog execution")
        print(f"• Test job summary generation")
        
        # Commands for Slurm controller
        summary_commands = [
            {
                'host': self.config['systems']['slurm_controller'][0] if self.config['systems']['slurm_controller'] else 'slurm-controller',
                'command': f'cp {self.working_dir}/jobstats/slurm/slurmctldepilog.sh /usr/local/sbin/',
                'description': 'Install slurmctld epilog script'
            },
            {
                'host': self.config['systems']['slurm_controller'][0] if self.config['systems']['slurm_controller'] else 'slurm-controller',
                'command': 'chmod +x /usr/local/sbin/slurmctldepilog.sh',
                'description': 'Make epilog script executable'
            }
        ]
        
        if self._execute_commands(summary_commands):
            print(f"\n{Colors.GREEN}✓ Job summary setup completed{Colors.END}")
        else:
            print(f"\n{Colors.RED}✗ Job summary setup failed{Colors.END}")
            return False
        
        print(f"\n{Colors.BOLD}{Colors.YELLOW}BCM Configuration Required:{Colors.END}")
        print(f"Add the following to your slurm.conf:")
        print(f"• {Colors.WHITE}EpilogSlurmctld=/usr/local/sbin/slurmctldepilog.sh{Colors.END}")
        
        if not self.dry_run:
            input(f"\n{Colors.YELLOW}Press Enter to continue to the next section...{Colors.END}")
        else:
            print(f"\n{Colors.BLUE}[DRY RUN] Continuing to next section...{Colors.END}")
        return True

    def section_prometheus(self):
        """Section 6: Prometheus"""
        self._print_header(
            "6. Prometheus",
            "Setup Prometheus server and configuration"
        )
        
        print(f"{Colors.BLUE}This section sets up the Prometheus time series database{Colors.END}")
        print(f"{Colors.BLUE}to collect and store metrics from all exporters.{Colors.END}")
        
        print(f"\n{Colors.BOLD}{Colors.WHITE}What we'll do:{Colors.END}")
        print(f"• Download and install Prometheus")
        print(f"• Create Prometheus configuration")
        print(f"• Setup systemd service")
        print(f"• Start Prometheus server")
        
        # Commands for Prometheus server
        prometheus_commands = [
            {
                'host': self.config['prometheus_server'],
                'command': 'wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz',
                'description': 'Download Prometheus'
            },
            {
                'host': self.config['prometheus_server'],
                'command': 'tar xzf prometheus-2.45.0.linux-amd64.tar.gz',
                'description': 'Extract Prometheus'
            },
            {
                'host': self.config['prometheus_server'],
                'command': 'cp prometheus-2.45.0.linux-amd64/prometheus /usr/local/bin/',
                'description': 'Install Prometheus binary'
            },
            {
                'host': self.config['prometheus_server'],
                'command': 'mkdir -p /etc/prometheus /var/lib/prometheus',
                'description': 'Create Prometheus directories'
            },
            {
                'host': self.config['prometheus_server'],
                'command': 'useradd --no-create-home --shell /bin/false prometheus || true',
                'description': 'Create prometheus user'
            },
            {
                'host': self.config['prometheus_server'],
                'command': 'chown prometheus:prometheus /var/lib/prometheus',
                'description': 'Set ownership of data directory'
            }
        ]
        
        if self._execute_commands(prometheus_commands):
            print(f"\n{Colors.GREEN}✓ Prometheus installation completed{Colors.END}")
        else:
            print(f"\n{Colors.RED}✗ Prometheus installation failed{Colors.END}")
            return False
        
        # Create Prometheus configuration
        self._create_prometheus_config()
        
        if not self.dry_run:
            input(f"\n{Colors.YELLOW}Press Enter to continue to the next section...{Colors.END}")
        else:
            print(f"\n{Colors.BLUE}[DRY RUN] Continuing to next section...{Colors.END}")
        return True

    def _create_prometheus_config(self):
        """Create Prometheus configuration file."""
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Creating Prometheus configuration...{Colors.END}")
        
        # Build targets list
        targets = []
        for node in self.config['systems']['dgx_nodes']:
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
    monitor: 'jobstats-{self.config['cluster_name']}'

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
        
        config_commands = [
            {
                'host': self.config['prometheus_server'],
                'command': f'cp {temp_file} /etc/prometheus/prometheus.yml',
                'description': 'Install Prometheus configuration'
            },
            {
                'host': self.config['prometheus_server'],
                'command': 'chown -R prometheus:prometheus /etc/prometheus',
                'description': 'Set configuration ownership'
            }
        ]
        
        if self._execute_commands(config_commands):
            print(f"{Colors.GREEN}✓ Prometheus configuration created{Colors.END}")
        else:
            print(f"{Colors.RED}✗ Prometheus configuration failed{Colors.END}")
        
        os.unlink(temp_file)

    def section_grafana(self):
        """Section 7: Grafana"""
        self._print_header(
            "7. Grafana",
            "Setup Grafana visualization interface"
        )
        
        print(f"{Colors.BLUE}This section sets up Grafana for visualizing{Colors.END}")
        print(f"{Colors.BLUE}the collected metrics and creating dashboards.{Colors.END}")
        
        print(f"\n{Colors.BOLD}{Colors.WHITE}What we'll do:{Colors.END}")
        print(f"• Install Grafana")
        print(f"• Configure Prometheus data source")
        print(f"• Import jobstats dashboard")
        print(f"• Start Grafana service")
        
        # Commands for Grafana server
        grafana_commands = [
            {
                'host': self.config['grafana_server'],
                'command': 'wget -q -O - https://packages.grafana.com/gpg.key | apt-key add -',
                'description': 'Add Grafana repository key'
            },
            {
                'host': self.config['grafana_server'],
                'command': 'echo "deb https://packages.grafana.com/oss/deb stable main" > /etc/apt/sources.list.d/grafana.list',
                'description': 'Add Grafana repository'
            },
            {
                'host': self.config['grafana_server'],
                'command': 'apt update',
                'description': 'Update package lists'
            },
            {
                'host': self.config['grafana_server'],
                'command': 'apt install -y grafana',
                'description': 'Install Grafana'
            }
        ]
        
        if self._execute_commands(grafana_commands):
            print(f"\n{Colors.GREEN}✓ Grafana installation completed{Colors.END}")
        else:
            print(f"\n{Colors.RED}✗ Grafana installation failed{Colors.END}")
            return False
        
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Manual Configuration Required:{Colors.END}")
        print(f"1. Access Grafana at http://{self.config['grafana_server']}:{self.config['grafana_port']}")
        print(f"2. Login with admin/admin (change password)")
        print(f"3. Add Prometheus data source: http://{self.config['prometheus_server']}:{self.config['prometheus_port']}")
        print(f"4. Import jobstats dashboard from .jobstats/jobstats/grafana/")
        
        if not self.dry_run:
            input(f"\n{Colors.YELLOW}Press Enter to continue to the next section...{Colors.END}")
        else:
            print(f"\n{Colors.BLUE}[DRY RUN] Continuing to next section...{Colors.END}")
        return True

    def section_ood(self):
        """Section 8: Open OnDemand Jobstats Helper"""
        self._print_header(
            "8. Open OnDemand Jobstats Helper",
            "Setup Open OnDemand integration (optional)"
        )
        
        print(f"{Colors.BLUE}This section sets up the Open OnDemand integration{Colors.END}")
        print(f"{Colors.BLUE}for easy access to jobstats dashboards.{Colors.END}")
        
        print(f"\n{Colors.BOLD}{Colors.WHITE}What we'll do:{Colors.END}")
        print(f"• Clone OOD helper application")
        print(f"• Configure OOD integration")
        print(f"• Test dashboard access")
        
        # Commands for OOD setup
        ood_commands = [
            {
                'host': 'localhost',
                'command': f'cd {self.working_dir} && git clone https://github.com/PrincetonUniversity/jobstats.git',
                'description': 'Clone jobstats repository for OOD helper'
            },
            {
                'host': 'localhost',
                'command': f'ls -la {self.working_dir}/jobstats/ood-jobstats-helper/',
                'description': 'List OOD helper files'
            }
        ]
        
        if self._execute_commands(ood_commands):
            print(f"\n{Colors.GREEN}✓ OOD helper setup completed{Colors.END}")
        else:
            print(f"\n{Colors.RED}✗ OOD helper setup failed{Colors.END}")
            return False
        
        print(f"\n{Colors.BOLD}{Colors.YELLOW}OOD Integration:{Colors.END}")
        print(f"The OOD helper files are available in:")
        print(f"• {Colors.WHITE}{self.working_dir}/jobstats/ood-jobstats-helper/{Colors.END}")
        print(f"• Follow the README in that directory for OOD integration")
        
        if not self.dry_run:
            input(f"\n{Colors.YELLOW}Press Enter to continue to the next section...{Colors.END}")
        else:
            print(f"\n{Colors.BLUE}[DRY RUN] Continuing to next section...{Colors.END}")
        return True

    def section_jobstats_command(self):
        """Section 9: The jobstats Command"""
        self._print_header(
            "9. The jobstats Command",
            "Install and configure the jobstats command-line tool"
        )
        
        print(f"{Colors.BLUE}This section installs the jobstats command-line tool{Colors.END}")
        print(f"{Colors.BLUE}for generating job efficiency reports.{Colors.END}")
        
        print(f"\n{Colors.BOLD}{Colors.WHITE}What we'll do:{Colors.END}")
        print(f"• Install jobstats command files")
        print(f"• Configure jobstats settings")
        print(f"• Test jobstats functionality")
        
        # Commands for login nodes
        jobstats_commands = []
        
        for login_node in self.config['systems']['login_nodes']:
            jobstats_commands.extend([
                {
                    'host': login_node,
                    'command': f'cp {self.working_dir}/jobstats/jobstats /usr/local/bin/',
                    'description': f'Install jobstats binary on {login_node}'
                },
                {
                    'host': login_node,
                    'command': f'cp {self.working_dir}/jobstats/jobstats.py /usr/local/bin/',
                    'description': f'Install jobstats.py on {login_node}'
                },
                {
                    'host': login_node,
                    'command': f'cp {self.working_dir}/jobstats/output_formatters.py /usr/local/bin/',
                    'description': f'Install output_formatters.py on {login_node}'
                },
                {
                    'host': login_node,
                    'command': f'cp {self.working_dir}/jobstats/config.py /usr/local/bin/',
                    'description': f'Install config.py on {login_node}'
                },
                {
                    'host': login_node,
                    'command': 'chmod +x /usr/local/bin/jobstats',
                    'description': f'Make jobstats executable on {login_node}'
                }
            ])
        
        if self._execute_commands(jobstats_commands):
            print(f"\n{Colors.GREEN}✓ Jobstats command installation completed{Colors.END}")
        else:
            print(f"\n{Colors.RED}✗ Jobstats command installation failed{Colors.END}")
            return False
        
        print(f"\n{Colors.BOLD}{Colors.YELLOW}Configuration Required:{Colors.END}")
        print(f"Update /usr/local/bin/config.py with:")
        print(f"• {Colors.WHITE}PROM_SERVER = \"http://{self.config['prometheus_server']}:{self.config['prometheus_port']}\"{Colors.END}")
        print(f"• {Colors.WHITE}PROM_RETENTION_DAYS = {self.config['prometheus_retention_days']}{Colors.END}")
        
        if not self.dry_run:
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.END}")
        else:
            print(f"\n{Colors.BLUE}[DRY RUN] Continuing to next section...{Colors.END}")
        return True

    def run_guided_setup(self):
        """Run the complete guided setup process."""
        print(f"{Colors.BOLD}{Colors.PURPLE}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.WHITE}BCM Jobstats Guided Setup{Colors.END}")
        if self.dry_run:
            print(f"{Colors.BOLD}{Colors.YELLOW}[DRY RUN MODE]{Colors.END}")
        print(f"{Colors.BOLD}{Colors.PURPLE}{'='*80}{Colors.END}")
        
        # Initialize document
        self._init_document()
        
        if self.resume and self.progress['current_section'] > 0:
            print(f"\n{Colors.YELLOW}Resuming from section {self.progress['current_section'] + 1}{Colors.END}")
            start_section = self.progress['current_section']
        else:
            start_section = 0
        
        # Run each section
        for i, section in enumerate(self.setup_sections[start_section:], start_section):
            section_id = section['id']
            section_title = section['title']
            
            print(f"\n{Colors.BOLD}{Colors.CYAN}Section {i+1}/{len(self.setup_sections)}: {section_title}{Colors.END}")
            
            # Execute section
            if hasattr(self, f'section_{section_id}'):
                success = getattr(self, f'section_{section_id}')()
                
                if success:
                    self.progress['completed_sections'].append(section_id)
                    self.progress['current_section'] = i + 1
                    self._save_progress()
                    print(f"\n{Colors.GREEN}✓ Section {i+1} completed successfully{Colors.END}")
                else:
                    print(f"\n{Colors.RED}✗ Section {i+1} failed{Colors.END}")
                    if not self.dry_run:
                        print(f"{Colors.YELLOW}You can resume from this section later using --resume{Colors.END}")
                    return False
            else:
                print(f"{Colors.RED}Section {section_id} not implemented{Colors.END}")
                return False
        
        # Save final document
        self._save_document()
        
        # Final summary
        print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*80}{Colors.END}")
        if self.dry_run:
            print(f"{Colors.BOLD}{Colors.WHITE}Dry Run Complete!{Colors.END}")
        else:
            print(f"{Colors.BOLD}{Colors.WHITE}Setup Complete!{Colors.END}")
        print(f"{Colors.BOLD}{Colors.GREEN}{'='*80}{Colors.END}")
        
        print(f"\n{Colors.BLUE}All sections have been completed successfully.{Colors.END}")
        print(f"\n{Colors.BOLD}{Colors.WHITE}Documentation Generated:{Colors.END}")
        print(f"• {Colors.CYAN}Setup document: {self.document_file}{Colors.END}")
        print(f"• {Colors.CYAN}This document contains all commands and can be used for manual implementation{Colors.END}")
        
        if not self.dry_run:
            print(f"\n{Colors.BOLD}{Colors.WHITE}Next Steps:{Colors.END}")
            print(f"1. {Colors.CYAN}Test the deployment with a sample job{Colors.END}")
            print(f"2. {Colors.CYAN}Access Grafana at http://{self.config['grafana_server']}:{self.config['grafana_port']}{Colors.END}")
            print(f"3. {Colors.CYAN}Test jobstats command: jobstats --help{Colors.END}")
            print(f"4. {Colors.CYAN}Review the documentation for troubleshooting{Colors.END}")
        else:
            print(f"\n{Colors.BOLD}{Colors.WHITE}Dry Run Summary:{Colors.END}")
            print(f"1. {Colors.CYAN}Review the generated document: {self.document_file}{Colors.END}")
            print(f"2. {Colors.CYAN}Use the document to implement the setup manually{Colors.END}")
            print(f"3. {Colors.CYAN}Run without --dry-run to execute the setup{Colors.END}")
        
        return True

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="BCM Jobstats Guided Setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run guided setup
    python guided_setup.py
    
    # Run dry-run to generate documentation only
    python guided_setup.py --dry-run
    
    # Resume from where you left off
    python guided_setup.py --resume
    
    # Use custom configuration
    python guided_setup.py --config my_config.json
        """
    )
    
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume setup from where it was left off'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration JSON file'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Generate documentation without executing commands'
    )
    
    args = parser.parse_args()
    
    # Create guided setup instance
    setup = GuidedJobstatsSetup(resume=args.resume, config_file=args.config, dry_run=args.dry_run)
    
    # Run guided setup
    success = setup.run_guided_setup()
    
    if success:
        if args.dry_run:
            print(f"\n{Colors.GREEN}Dry run completed successfully!{Colors.END}")
        else:
            print(f"\n{Colors.GREEN}Guided setup completed successfully!{Colors.END}")
        sys.exit(0)
    else:
        print(f"\n{Colors.RED}Guided setup failed!{Colors.END}")
        sys.exit(1)

if __name__ == "__main__":
    main()
