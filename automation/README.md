# BCM Jobstats Deployment Automation

This project provides automated deployment of Princeton University's jobstats monitoring platform on BCM-managed DGX systems.

## Prerequisites

**Note**: The `setup.sh` script in the main README should have already handled these prerequisites:

- BCM head node with passwordless SSH access to all target systems
- `uv` package manager installed
- `cmsh` access for BCM configuration verification
- Internet access for downloading components

## Guided Setup Script

The `automation/guided_setup.py` script provides step-by-step interactive deployment:

### What it does:
- **Interactive Deployment**: Follows Princeton University's documentation flow
- **Progress Tracking**: Saves progress and allows resumption if interrupted
- **Documentation Generation**: Creates comprehensive deployment documentation
- **Dry-Run Mode**: Preview all commands before execution
- **BCM Integration**: Proper BCM configuration and validation
- **10 Comprehensive Sections**: Covers all aspects of jobstats deployment

### Input Files:
The script uses configuration files from the `automation/configs/` directory:

**Default Configuration:**
- `config.json` - Main configuration file (used by default)

**Template Configurations:**
- `config-shared-hosts.json` - Template for shared host environments
- `config-existing-monitoring.json` - Template for existing Prometheus/Grafana

### Output Files:
The script generates files in the `automation/logs/` directory:
- `guided_setup_document.md` - Complete deployment documentation
- `guided_setup_progress.json` - Progress tracking for resumption

### Usage:
```bash
# Full automated deployment
uv run python automation/guided_setup.py --config automation/configs/config.json

# Dry-run with documentation generation
uv run python automation/guided_setup.py --config automation/configs/config.json --dry-run

# Resume interrupted deployment
uv run python automation/guided_setup.py --config automation/configs/config.json --resume
```

## Additional Automation Tools

For detailed information about additional automation tools including validation scripts, deployment utilities, and testing frameworks, see [automation/tools/README.md](tools/README.md).

