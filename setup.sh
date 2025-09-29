#!/bin/bash

# BCM Jobstats Project Setup Script
# This script sets up the complete environment for BCM jobstats deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to prompt for user input with default
prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    
    if [ -n "$default" ]; then
        read -p "$prompt [$default]: " input
        eval "$var_name=\${input:-$default}"
    else
        read -p "$prompt: " input
        eval "$var_name=\"$input\""
    fi
}

# Function to prompt for multiple hostnames
prompt_hostnames() {
    local role="$1"
    local var_name="$2"
    local hosts=()
    
    echo ""
    print_status "Enter hostnames for $role (one per line, press Enter twice when done):"
    while true; do
        read -p "  Hostname: " hostname
        if [ -z "$hostname" ]; then
            break
        fi
        hosts+=("$hostname")
    done
    
    # Convert array to JSON array format
    local json_array="["
    for i in "${!hosts[@]}"; do
        if [ $i -gt 0 ]; then
            json_array+=","
        fi
        json_array+="\"${hosts[$i]}\""
    done
    json_array+="]"
    
    eval "$var_name='$json_array'"
}

# Function to validate hostname format
validate_hostname() {
    local hostname="$1"
    if [[ "$hostname" =~ ^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$ ]]; then
        return 0
    else
        return 1
    fi
}

# Main setup function
main() {
    echo "=========================================="
    echo "  BCM Jobstats Project Setup"
    echo "=========================================="
    echo ""
    
    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root. This is recommended for BCM deployments."
    else
        print_warning "Not running as root. You may need sudo privileges for some operations."
    fi
    
    # Step 1: Install uv if not present
    print_status "Step 1: Installing uv package manager..."
    
    if command_exists uv; then
        print_success "uv is already installed: $(uv --version)"
    else
        print_status "Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # Add uv to PATH for current session
        export PATH="$HOME/.cargo/bin:$PATH"
        
        # Source bashrc to make uv available
        if [ -f "$HOME/.bashrc" ]; then
            source "$HOME/.bashrc"
        fi
        
        if command_exists uv; then
            print_success "uv installed successfully: $(uv --version)"
        else
            print_error "Failed to install uv. Please install manually and run this script again."
            exit 1
        fi
    fi
    
    # Step 2: Sync dependencies
    print_status "Step 2: Installing Python dependencies..."
    
    if [ -f "pyproject.toml" ]; then
        # Check if dependencies are already installed
        if [ -d ".venv" ] && [ -f ".venv/pyvenv.cfg" ]; then
            print_status "Virtual environment already exists. Checking if dependencies are up to date..."
            if uv sync --check; then
                print_success "Dependencies are already up to date"
            else
                print_status "Dependencies need updating. Installing..."
                uv sync
                print_success "Dependencies updated successfully"
            fi
        else
            print_status "Installing dependencies..."
            uv sync
            print_success "Dependencies installed successfully"
        fi
    else
        print_error "pyproject.toml not found. Are you in the correct directory?"
        exit 1
    fi
    
    # Step 3: Collect configuration information
    print_status "Step 3: Collecting configuration information..."
    echo ""
    
    # Basic configuration
    prompt_with_default "BCM wlm cluster name" "slurm" cluster_name
    prompt_with_default "Prometheus server hostname" "prometheus-server" prometheus_server
    prompt_with_default "Grafana server hostname" "grafana-server" grafana_server
    
    # Ports
    prompt_with_default "Prometheus port" "9090" prometheus_port
    prompt_with_default "Grafana port" "3000" grafana_port
    prompt_with_default "Node exporter port" "9100" node_exporter_port
    prompt_with_default "Cgroup exporter port" "9306" cgroup_exporter_port
    prompt_with_default "NVIDIA GPU exporter port" "9445" nvidia_gpu_exporter_port
    prompt_with_default "Prometheus retention days" "365" prometheus_retention_days
    
    # Advanced options
    echo ""
    print_status "Advanced configuration options:"
    
    read -p "Use existing Prometheus installation? (y/N): " use_existing_prometheus
    use_existing_prometheus=$(echo "$use_existing_prometheus" | tr '[:upper:]' '[:lower:]')
    if [[ "$use_existing_prometheus" == "y" || "$use_existing_prometheus" == "yes" ]]; then
        use_existing_prometheus="true"
    else
        use_existing_prometheus="false"
    fi
    
    read -p "Use existing Grafana installation? (y/N): " use_existing_grafana
    use_existing_grafana=$(echo "$use_existing_grafana" | tr '[:upper:]' '[:lower:]')
    if [[ "$use_existing_grafana" == "y" || "$use_existing_grafana" == "yes" ]]; then
        use_existing_grafana="true"
    else
        use_existing_grafana="false"
    fi
    
    read -p "Enable BCM category management? (Y/n): " bcm_category_management
    bcm_category_management=$(echo "$bcm_category_management" | tr '[:upper:]' '[:lower:]')
    if [[ "$bcm_category_management" == "n" || "$bcm_category_management" == "no" ]]; then
        bcm_category_management="false"
    else
        bcm_category_management="true"
    fi
    
    if [[ "$bcm_category_management" == "true" ]]; then
        prompt_with_default "BCM category for DGX's running Slurm" "slurm-category" slurm_category
        prompt_with_default "BCM category for DGX's running Kubernetes" "kubernetes-category" kubernetes_category
    else
        slurm_category="slurm-category"
        kubernetes_category="kubernetes-category"
    fi
    
    # System hostnames
    echo ""
    print_status "System hostname configuration:"
    echo "Enter hostnames for each system type. Press Enter twice when done with each type."
    
    prompt_hostnames "Slurm controller nodes" slurm_controller_hosts
    prompt_hostnames "Login nodes" login_nodes_hosts
    prompt_hostnames "DGX compute nodes" dgx_nodes_hosts
    
    if [[ "$use_existing_prometheus" == "false" ]]; then
        prompt_hostnames "Prometheus server nodes" prometheus_server_hosts
    else
        prometheus_server_hosts="[]"
    fi
    
    if [[ "$use_existing_grafana" == "false" ]]; then
        prompt_hostnames "Grafana server nodes" grafana_server_hosts
    else
        grafana_server_hosts="[]"
    fi
    
    # Step 4: Create config.json
    print_status "Step 4: Creating configuration file..."
    
    local config_file="automation/configs/config.json"
    local config_dir="automation/configs"
    
    # Ensure config directory exists
    mkdir -p "$config_dir"
    
    # Check if config.json already exists
    if [ -f "$config_file" ]; then
        echo ""
        print_warning "Configuration file already exists: $config_file"
        echo "Current configuration:"
        cat "$config_file" | head -10
        echo "..."
        echo ""
        read -p "Would you like to overwrite the existing config.json? (y/N): " overwrite_config
        overwrite_config=$(echo "$overwrite_config" | tr '[:upper:]' '[:lower:]')
        
        if [[ "$overwrite_config" != "y" && "$overwrite_config" != "yes" ]]; then
            print_status "Keeping existing configuration file."
            print_status "You can manually edit $config_file if needed."
            echo ""
            print_status "Next steps:"
            echo "1. Review your configuration: cat $config_file"
            echo "2. Run a dry-run deployment:"
            echo "   uv run python automation/deploy_jobstats.py --config $config_file --dry-run"
            echo "3. Deploy jobstats:"
            echo "   uv run python automation/deploy_jobstats.py --config $config_file"
            echo ""
            return 0
        else
            print_status "Overwriting existing configuration file..."
        fi
    fi
    
    # Create the JSON configuration
    cat > "$config_file" << EOF
{
  "cluster_name": "$cluster_name",
  "prometheus_server": "$prometheus_server",
  "grafana_server": "$grafana_server",
  "prometheus_port": $prometheus_port,
  "grafana_port": $grafana_port,
  "node_exporter_port": $node_exporter_port,
  "cgroup_exporter_port": $cgroup_exporter_port,
  "nvidia_gpu_exporter_port": $nvidia_gpu_exporter_port,
  "prometheus_retention_days": $prometheus_retention_days,
  "use_existing_prometheus": $use_existing_prometheus,
  "use_existing_grafana": $use_existing_grafana,
  "bcm_category_management": $bcm_category_management,
  "slurm_category": "$slurm_category",
  "kubernetes_category": "$kubernetes_category",
  "systems": {
    "slurm_controller": $slurm_controller_hosts,
    "login_nodes": $login_nodes_hosts,
    "dgx_nodes": $dgx_nodes_hosts,
    "prometheus_server": $prometheus_server_hosts,
    "grafana_server": $grafana_server_hosts
  }
}
EOF
    
    print_success "Configuration file created: $config_file"
    
    # Step 5: Display next steps
    echo ""
    echo "=========================================="
    print_success "Setup completed successfully!"
    echo "=========================================="
    echo ""
    print_status "Next steps:"
    echo "1. Review your configuration: cat $config_file"
    echo "2. Run a dry-run deployment:"
    echo "   uv run python automation/deploy_jobstats.py --config $config_file --dry-run"
    echo "3. Deploy jobstats:"
    echo "   uv run python automation/deploy_jobstats.py --config $config_file"
    echo ""
    print_status "Configuration file location: $config_file"
    print_status "Dry-run output will be saved to: automation/logs/dry-run-output.txt"
    echo ""
    
    # Step 6: Show configuration summary
    print_status "Configuration Summary:"
    echo "  Cluster: $cluster_name"
    echo "  Prometheus: $prometheus_server:$prometheus_port"
    echo "  Grafana: $grafana_server:$grafana_port"
    echo "  Existing Prometheus: $use_existing_prometheus"
    echo "  Existing Grafana: $use_existing_grafana"
    echo "  BCM Category Management: $bcm_category_management"
    echo ""
    
    print_success "Setup complete! You can now run the deployment script."
    
    # Step 7: Offer to run guided setup
    echo ""
    print_status "Step 7: Optional Guided Setup"
    echo ""
    print_status "Would you like to run the guided setup process?"
    print_status "This will walk you through the deployment step-by-step with detailed explanations."
    echo ""
    read -p "Run guided setup? (y/N): " run_guided_setup
    run_guided_setup=$(echo "$run_guided_setup" | tr '[:upper:]' '[:lower:]')
    
    if [[ "$run_guided_setup" == "y" || "$run_guided_setup" == "yes" ]]; then
        echo ""
        print_status "Guided setup options:"
        echo "1. Full automation - Execute all commands automatically"
        echo "2. Dry run - Generate documentation only (no commands executed)"
        echo ""
        read -p "Choose option (1 or 2): " guided_option
        
        if [[ "$guided_option" == "1" ]]; then
            print_status "Running guided setup with full automation..."
            echo ""
            uv run python automation/guided_setup.py --config "$config_file"
        elif [[ "$guided_option" == "2" ]]; then
            print_status "Running guided setup in dry-run mode..."
            echo ""
            uv run python automation/guided_setup.py --config "$config_file" --dry-run
            echo ""
            print_success "Documentation generated! Check automation/logs/guided_setup_document.md"
        else
            print_warning "Invalid option. Skipping guided setup."
        fi
    else
        print_status "Skipping guided setup."
    fi
}

# Run main function
main "$@"
