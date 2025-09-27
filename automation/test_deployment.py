#!/usr/bin/env python3
"""
Test script for BCM Jobstats Deployment Automation

This script provides basic testing functionality for the deployment automation.
"""

import json
import tempfile
from pathlib import Path
from deploy_jobstats import BCMJobstatsDeployer


def test_config_loading():
    """Test configuration loading functionality."""
    print("Testing configuration loading...")
    
    # Create a temporary config file
    test_config = {
        "cluster_name": "test-cluster",
        "prometheus_server": "test-prometheus",
        "systems": {
            "slurm_controller": ["test-controller"],
            "login_nodes": ["test-login"],
            "dgx_nodes": ["test-dgx"],
            "prometheus_server": ["test-prometheus"],
            "grafana_server": ["test-grafana"]
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_config, f)
        config_file = f.name
    
    try:
        # Test with config file
        deployer = BCMJobstatsDeployer(dry_run=True, config_file=config_file)
        assert deployer.config['cluster_name'] == 'test-cluster'
        assert deployer.config['prometheus_server'] == 'test-prometheus'
        print("✓ Configuration loading test passed")
        
        # Test with default config
        deployer_default = BCMJobstatsDeployer(dry_run=True)
        assert deployer_default.config['cluster_name'] == 'slurm'
        print("✓ Default configuration test passed")
        
    finally:
        Path(config_file).unlink()


def test_dry_run_mode():
    """Test dry-run mode functionality."""
    print("Testing dry-run mode...")
    
    deployer = BCMJobstatsDeployer(dry_run=True)
    
    # Test that commands are recorded in dry-run mode
    deployer._run_command("echo 'test command'")
    assert len(deployer.dry_run_commands) == 1
    assert "echo 'test command'" in deployer.dry_run_commands[0]
    print("✓ Dry-run command recording test passed")
    
    # Test remote command recording
    deployer._run_command("ls -la", host="test-host")
    assert len(deployer.dry_run_commands) == 2
    assert "ssh test-host 'ls -la'" in deployer.dry_run_commands[1]
    print("✓ Dry-run remote command recording test passed")


def test_repository_configuration():
    """Test repository configuration."""
    print("Testing repository configuration...")
    
    deployer = BCMJobstatsDeployer(dry_run=True)
    
    # Test that all required repositories are configured
    required_repos = ['jobstats', 'cgroup_exporter', 'nvidia_gpu_prometheus_exporter', 'node_exporter']
    for repo in required_repos:
        assert repo in deployer.repositories
        assert deployer.repositories[repo].startswith('https://')
    print("✓ Repository configuration test passed")


def test_system_roles():
    """Test system role configuration."""
    print("Testing system role configuration...")
    
    deployer = BCMJobstatsDeployer(dry_run=True)
    
    # Test that all system roles are properly configured
    expected_roles = ['slurm_controller', 'login_nodes', 'dgx_nodes', 'prometheus_server', 'grafana_server']
    for role in expected_roles:
        assert role in deployer.system_roles
        assert 'repositories' in deployer.system_roles[role]
        assert 'components' in deployer.system_roles[role]
    print("✓ System role configuration test passed")


def test_dry_run_output():
    """Test dry-run output file creation."""
    print("Testing dry-run output file creation...")
    
    deployer = BCMJobstatsDeployer(dry_run=True)
    
    # Add some test commands
    deployer._run_command("test command 1")
    deployer._run_command("test command 2", host="test-host")
    
    # Write dry-run output
    deployer._write_dry_run_output()
    
    # Check that file was created
    output_file = Path("dry-run-output.txt")
    assert output_file.exists()
    
    # Check file contents
    content = output_file.read_text()
    assert "BCM Jobstats Deployment - Dry Run Commands" in content
    assert "test command 1" in content
    assert "ssh test-host 'test command 2'" in content
    
    # Clean up
    output_file.unlink()
    print("✓ Dry-run output file creation test passed")


def main():
    """Run all tests."""
    print("Running BCM Jobstats Deployment Tests")
    print("=" * 40)
    
    try:
        test_config_loading()
        test_dry_run_mode()
        test_repository_configuration()
        test_system_roles()
        test_dry_run_output()
        
        print("\n" + "=" * 40)
        print("✓ All tests passed!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
