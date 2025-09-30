#!/bin/bash
# PyTorch GPU Test Script for Jobstats Validation
# 
# This script creates a PyTorch workload that consumes GPU memory and compute resources
# to generate meaningful metrics for jobstats validation. It's designed to use approximately
# 4GB of VRAM and run for a configurable duration.
#
# Usage:
#   ./test_jobstats_pytorch.sh [options]
#
# Options:
#   -d, --duration DURATION     Duration in minutes (default: 5)
#   -j, --job-name NAME         Job name (default: pytorch-gpu-test)
#   -p, --partition PARTITION   Slurm partition (default: defq)
#   -n, --nodelist NODELIST     Specific node list (default: dgx-01)
#   -u, --username USERNAME     Username to run as (default: testuser)
#   -i, --interactive           Interactive mode for prompts
#   -q, --quiet                 Non-interactive mode (use defaults)
#   --dry-run                   Show what would be done without executing
#   -h, --help                  Show this help message

set -euo pipefail

# Default values
DURATION=5
JOB_NAME="pytorch-gpu-test"
PARTITION="defq"
NODELIST="dgx-01"
USERNAME="testuser"
INTERACTIVE=false
NON_INTERACTIVE=false
DRY_RUN=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
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

# Function to show help
show_help() {
    cat << EOF
PyTorch GPU Test Script for Jobstats Validation

This script creates a PyTorch workload that consumes GPU memory and compute resources
to generate meaningful metrics for jobstats validation. It's designed to use approximately
4GB of VRAM and run for a configurable duration.

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -d, --duration DURATION     Duration in minutes (default: 5)
    -j, --job-name NAME         Job name (default: pytorch-gpu-test)
    -p, --partition PARTITION   Slurm partition (default: defq)
    -n, --nodelist NODELIST     Specific node list (default: dgx-01)
    -u, --username USERNAME     Username to run as (default: testuser)
    -i, --interactive           Interactive mode for prompts
    -q, --quiet                 Non-interactive mode (use defaults)
    --dry-run                   Show what would be done without executing
    -h, --help                  Show this help message

EXAMPLES:
    # Interactive mode (prompts for all values)
    $0 -i

    # Non-interactive with custom values
    $0 -q -d 10 -j my-pytorch-test -p gpu -n dgx-02 -u myuser

    # Dry run to see what would be executed
    $0 --dry-run -d 15

    # Quick test with defaults
    $0 -q

NOTES:
    - The script will automatically install PyTorch if not available
    - GPU memory usage will be approximately 4GB
    - Job will run for the specified duration plus 5 minutes buffer
    - Make sure the specified user exists and has access to the partition
    - The script will handle module loading and environment setup

EOF
}

# Function to get user input interactively
get_user_input() {
    if [ "$NON_INTERACTIVE" = true ]; then
        print_info "Non-interactive mode: Using defaults"
        echo "  Duration: $DURATION minutes"
        echo "  Job Name: $JOB_NAME"
        echo "  Partition: $PARTITION"
        echo "  Nodelist: $NODELIST"
        echo "  Username: $USERNAME"
        return
    fi

    if [ "$INTERACTIVE" = false ]; then
        return
    fi

    echo
    echo "============================================================"
    echo "PyTorch GPU Test Job Configuration"
    echo "============================================================"
    
    # Duration
    read -p "Job duration in minutes [$DURATION]: " duration_input
    if [ -n "$duration_input" ]; then
        DURATION="$duration_input"
    fi
    
    # Job name
    read -p "Job name [$JOB_NAME]: " job_name_input
    if [ -n "$job_name_input" ]; then
        JOB_NAME="$job_name_input"
    fi
    
    # Partition
    read -p "Slurm partition [$PARTITION]: " partition_input
    if [ -n "$partition_input" ]; then
        PARTITION="$partition_input"
    fi
    
    # Nodelist
    read -p "Node list [$NODELIST]: " nodelist_input
    if [ -n "$nodelist_input" ]; then
        NODELIST="$nodelist_input"
    fi
    
    # Username
    read -p "Username [$USERNAME]: " username_input
    if [ -n "$username_input" ]; then
        USERNAME="$username_input"
    fi
}

# Function to find Slurm commands
find_slurm_command() {
    local cmd="$1"
    
    # Try which first
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "$cmd"
        return
    fi
    
    # Fallback to common Slurm paths
    local common_paths=(
        "/cm/shared/apps/slurm/current/bin/$cmd"
        "/cm/shared/apps/slurm/23.11.10/bin/$cmd"
        "/usr/bin/$cmd"
        "/usr/local/bin/$cmd"
    )
    
    for path in "${common_paths[@]}"; do
        if [ -x "$path" ]; then
            echo "$path"
            return
        fi
    done
    
    # Return as-is if not found
    echo "$cmd"
}

# Function to create PyTorch test script
create_pytorch_script() {
    cat << 'EOF'
#!/usr/bin/env python3
"""
PyTorch GPU Test Script
Generated by test_jobstats_pytorch.sh
"""

import torch
import torch.nn as nn
import torch.optim as optim
import time
import sys
import os

def test_gpu_memory_usage():
    """Test GPU memory usage with PyTorch operations."""
    print("PyTorch GPU Test Starting...")
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    
    if not torch.cuda.is_available():
        print("ERROR: CUDA not available on this system!")
        return False
    
    device = torch.device('cuda:0')
    print(f"Using device: {device}")
    print(f"GPU name: {torch.cuda.get_device_name(0)}")
    print(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    
    # Create a model that will use approximately 4GB of VRAM
    print("\nCreating neural network model...")
    
    # Model architecture designed to use ~4GB VRAM
    class GPUTestModel(nn.Module):
        def __init__(self):
            super(GPUTestModel, self).__init__()
            # Large layers to consume memory
            self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3)
            self.conv2 = nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1)
            self.conv3 = nn.Conv2d(128, 256, kernel_size=3, stride=2, padding=1)
            self.conv4 = nn.Conv2d(256, 512, kernel_size=3, stride=2, padding=1)
            
            # Large fully connected layers
            self.fc1 = nn.Linear(512 * 7 * 7, 2048)
            self.fc2 = nn.Linear(2048, 1024)
            self.fc3 = nn.Linear(1024, 10)
            
            self.relu = nn.ReLU()
            self.dropout = nn.Dropout(0.5)
            
        def forward(self, x):
            x = self.relu(self.conv1(x))
            x = self.relu(self.conv2(x))
            x = self.relu(self.conv3(x))
            x = self.relu(self.conv4(x))
            x = x.view(x.size(0), -1)
            x = self.relu(self.fc1(x))
            x = self.dropout(x)
            x = self.relu(self.fc2(x))
            x = self.dropout(x)
            x = self.fc3(x)
            return x
    
    model = GPUTestModel().to(device)
    print(f"Model created and moved to {device}")
    
    # Create optimizer
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.CrossEntropyLoss()
    
    # Create large input tensors to consume memory
    batch_size = 32
    input_tensor = torch.randn(batch_size, 3, 224, 224, device=device)
    target_tensor = torch.randint(0, 10, (batch_size,), device=device)
    
    print(f"Input tensor shape: {input_tensor.shape}")
    print(f"Input tensor memory: {input_tensor.element_size() * input_tensor.nelement() / 1024**2:.1f} MB")
    
    # Monitor GPU memory usage
    def print_gpu_memory():
        allocated = torch.cuda.memory_allocated(0) / 1024**3
        cached = torch.cuda.memory_reserved(0) / 1024**3
        print(f"GPU Memory - Allocated: {allocated:.2f} GB, Cached: {cached:.2f} GB")
    
    print("\nInitial GPU memory usage:")
    print_gpu_memory()
    
    # Training loop
    print(f"\nStarting training loop for {DURATION} minutes...")
    start_time = time.time()
    iteration = 0
    
    try:
        while time.time() - start_time < DURATION * 60:
            iteration += 1
            
            # Forward pass
            optimizer.zero_grad()
            outputs = model(input_tensor)
            loss = criterion(outputs, target_tensor)
            
            # Backward pass
            loss.backward()
            optimizer.step()
            
            # Print progress every 30 seconds
            if iteration % 100 == 0:
                elapsed = time.time() - start_time
                print(f"Iteration {iteration}, Loss: {loss.item():.4f}, "
                      f"Elapsed: {elapsed/60:.1f} min", end="")
                print_gpu_memory()
            
            # Update target tensor occasionally to vary workload
            if iteration % 50 == 0:
                target_tensor = torch.randint(0, 10, (batch_size,), device=device)
    
    except KeyboardInterrupt:
        print("\nTraining interrupted by user")
    except Exception as e:
        print(f"\nError during training: {e}")
        return False
    
    print(f"\nTraining completed after {iteration} iterations")
    print(f"Total time: {(time.time() - start_time)/60:.1f} minutes")
    
    # Final memory usage
    print("\nFinal GPU memory usage:")
    print_gpu_memory()
    
    # Cleanup
    del model, input_tensor, target_tensor, optimizer, criterion
    torch.cuda.empty_cache()
    
    print("\nPyTorch GPU test completed successfully!")
    return True

if __name__ == "__main__":
    success = test_gpu_memory_usage()
    sys.exit(0 if success else 1)
EOF
}

# Function to create Slurm job script
create_job_script() {
    local pytorch_script
    pytorch_script=$(create_pytorch_script)
    
    cat << EOF
#!/bin/bash
#SBATCH --job-name=$JOB_NAME
#SBATCH --partition=$PARTITION
#SBATCH --nodelist=$NODELIST
#SBATCH --time=$((DURATION + 5)):00
#SBATCH --output=/tmp/${JOB_NAME}_%j.out
#SBATCH --error=/tmp/${JOB_NAME}_%j.err
#SBATCH --gres=gpu:1
#SBATCH --mem=8G
#SBATCH --cpus-per-task=4

echo "=========================================="
echo "PyTorch GPU Test Job Starting"
echo "=========================================="
echo "Job ID: \$SLURM_JOB_ID"
echo "Node: \$SLURM_JOB_NODELIST"
echo "Partition: \$SLURM_JOB_PARTITION"
echo "Duration: $DURATION minutes"
echo "Username: $USERNAME"
echo "=========================================="

# Set environment variables
export SLURM_CONF=/cm/shared/apps/slurm/var/etc/slurm/slurm.conf
export CUDA_VISIBLE_DEVICES=\$SLURM_LOCALID

# Load required modules
echo "Loading modules..."
module load slurm 2>/dev/null || true
module load cuda 2>/dev/null || true
module load python 2>/dev/null || true

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found"
    exit 1
fi

# Check if CUDA is available
if ! command -v nvidia-smi &> /dev/null; then
    echo "ERROR: nvidia-smi not found - CUDA not available"
    exit 1
fi

echo "\\nSystem Information:"
echo "Python version: \$(python3 --version)"
echo "CUDA version: \$(nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits | head -1)"
echo "GPU information:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader

# Install PyTorch if not available
echo "\\nChecking PyTorch installation..."
if ! python3 -c "import torch" 2>/dev/null; then
    echo "Installing PyTorch..."
    pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 || {
        echo "Failed to install PyTorch with pip3, trying pip..."
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 || {
            echo "ERROR: Failed to install PyTorch"
            exit 1
        }
    }
else
    echo "PyTorch already installed"
fi

# Create and run the PyTorch test script
echo "\\nCreating PyTorch test script..."
cat > /tmp/pytorch_gpu_test.py << 'PYTORCH_EOF'
$pytorch_script
PYTORCH_EOF

# Set DURATION variable for the Python script
export DURATION=$DURATION

echo "Running PyTorch GPU test..."
python3 /tmp/pytorch_gpu_test.py

# Cleanup
rm -f /tmp/pytorch_gpu_test.py

echo "\\n=========================================="
echo "PyTorch GPU Test Job Completed"
echo "=========================================="
EOF
}

# Function to submit job
submit_job() {
    local sbatch_cmd
    sbatch_cmd=$(find_slurm_command "sbatch")
    
    if [ "$DRY_RUN" = true ]; then
        echo
        echo "============================================================"
        echo "DRY RUN - Job Script that would be submitted:"
        echo "============================================================"
        create_job_script
        echo
        echo "============================================================"
        echo "DRY RUN - Slurm command that would be executed:"
        echo "============================================================"
        echo "$sbatch_cmd --uid=$USERNAME /tmp/pytorch_job_script.sh"
        return
    fi
    
    # Create temporary job script
    local temp_script
    temp_script=$(mktemp /tmp/pytorch_job_script_XXXXXX.sh)
    create_job_script > "$temp_script"
    chmod +x "$temp_script"
    
    print_info "Submitting PyTorch GPU test job..."
    echo "  Job Name: $JOB_NAME"
    echo "  Partition: $PARTITION"
    echo "  Node: $NODELIST"
    echo "  Duration: $DURATION minutes"
    echo "  Username: $USERNAME"
    
    # Submit job
    if $sbatch_cmd --uid="$USERNAME" "$temp_script" > /tmp/sbatch_output.txt 2>&1; then
        local job_id
        job_id=$(grep -o '[0-9]\+' /tmp/sbatch_output.txt | tail -1)
        print_success "Job submitted successfully!"
        echo "  Job ID: $job_id"
        echo "  Job script: $temp_script"
        echo "$job_id"
    else
        print_error "Failed to submit job:"
        cat /tmp/sbatch_output.txt
        rm -f "$temp_script"
        return 1
    fi
    
    # Clean up
    rm -f /tmp/sbatch_output.txt
}

# Function to monitor job
monitor_job() {
    local job_id="$1"
    local squeue_cmd
    squeue_cmd=$(find_slurm_command "squeue")
    
    if [ -z "$job_id" ]; then
        return
    fi
    
    print_info "Monitoring job $job_id..."
    echo "Job Status (refresh every 10 seconds):"
    echo "--------------------------------------------------"
    
    while true; do
        if $squeue_cmd -j "$job_id" --noheader > /tmp/squeue_output.txt 2>&1; then
            if [ -s /tmp/squeue_output.txt ]; then
                local status_line
                status_line=$(cat /tmp/squeue_output.txt)
                printf "\r%s" "$status_line"
                
                # Check if job is completed
                if echo "$status_line" | grep -q -E "(CD|CA|F|TO)"; then
                    echo
                    echo "Job $job_id completed"
                    break
                fi
            else
                echo
                echo "Job $job_id not found in queue"
                break
            fi
        else
            echo
            echo "Error checking job status"
            break
        fi
        
        sleep 10
    done
    
    rm -f /tmp/squeue_output.txt
}

# Function to show results
show_results() {
    local job_id="$1"
    local sacct_cmd
    sacct_cmd=$(find_slurm_command "sacct")
    
    if [ -z "$job_id" ]; then
        return
    fi
    
    echo
    echo "============================================================"
    echo "Job Results and Next Steps"
    echo "============================================================"
    
    echo
    echo "1. Check job output:"
    echo "   tail -f /tmp/${JOB_NAME}_*.out"
    echo "   tail -f /tmp/${JOB_NAME}_*.err"
    
    echo
    echo "2. Check job details:"
    echo "   $sacct_cmd -j $job_id --format=JobID,JobName,Partition,Account,AllocCPUS,State,ExitCode,Start,End,Elapsed,ReqMem,MaxRSS,MaxVMSize"
    
    echo
    echo "3. Test jobstats command:"
    echo "   su - $USERNAME -c 'module load slurm && SLURM_CONF=/cm/shared/apps/slurm/var/etc/slurm/slurm.conf jobstats $job_id -c slurm'"
    
    echo
    echo "4. Check GPU metrics in Prometheus:"
    echo "   curl -s 'http://statsrv:9090/api/v1/query?query=nvidia_gpu_memory_used_bytes{jobid=\"$job_id\"}' | jq"
    
    echo
    echo "5. Check cgroup metrics:"
    echo "   curl -s 'http://statsrv:9090/api/v1/query?query=cgroup_memory_rss_bytes{jobid=\"$job_id\"}' | jq"
}

# Main function
main() {
    echo "PyTorch GPU Test for Jobstats Validation"
    echo "=========================================="
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--duration)
                DURATION="$2"
                shift 2
                ;;
            -j|--job-name)
                JOB_NAME="$2"
                shift 2
                ;;
            -p|--partition)
                PARTITION="$2"
                shift 2
                ;;
            -n|--nodelist)
                NODELIST="$2"
                shift 2
                ;;
            -u|--username)
                USERNAME="$2"
                shift 2
                ;;
            -i|--interactive)
                INTERACTIVE=true
                shift
                ;;
            -q|--quiet)
                NON_INTERACTIVE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use -h or --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Validate arguments
    if [ "$INTERACTIVE" = true ] && [ "$NON_INTERACTIVE" = true ]; then
        print_error "Cannot specify both --interactive and --quiet"
        exit 1
    fi
    
    if [ "$INTERACTIVE" = false ] && [ "$NON_INTERACTIVE" = false ]; then
        INTERACTIVE=true
    fi
    
    # Get user input
    get_user_input
    
    # Submit job
    local job_id
    job_id=$(submit_job)
    
    if [ "$DRY_RUN" = false ] && [ -n "$job_id" ]; then
        # Monitor job
        monitor_job "$job_id"
        
        # Show results
        show_results "$job_id"
    fi
}

# Run main function with all arguments only if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
