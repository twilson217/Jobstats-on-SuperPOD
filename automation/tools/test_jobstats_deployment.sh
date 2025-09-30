#!/bin/bash
#
# Test Jobstats Deployment with Sample GPU Job
#
# This script submits a sample Slurm job that requests 1 GPU and runs a light
# workload to generate metrics for testing the jobstats deployment.
#
# Usage:
#     ./test_jobstats_deployment.sh [options]
#
# Options:
#     --job-name NAME        Custom job name (default: auto-generated)
#     --duration MINUTES     Job duration in minutes (default: 3)
#     --partition PARTITION  Slurm partition to use (default: prompt user)
#     --nodelist NODES       Specific nodes to use (default: prompt user)
#     --username USER        Username to run job as (default: prompt user)
#     --interactive          Interactive mode with prompts (default)
#     --non-interactive      Use defaults without prompts
#
# Examples:
#     ./test_jobstats_deployment.sh
#     ./test_jobstats_deployment.sh --job-name my_test --duration 5
#     ./test_jobstats_deployment.sh --partition gpu --nodelist dgx-01 --username testuser
#

set -euo pipefail

# Default values
JOB_NAME=""
DURATION_MINUTES=3
PARTITION=""
NODELIST=""
USERNAME=""
INTERACTIVE=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --job-name)
            JOB_NAME="$2"
            shift 2
            ;;
        --duration)
            DURATION_MINUTES="$2"
            shift 2
            ;;
        --partition)
            PARTITION="$2"
            shift 2
            ;;
        --nodelist)
            NODELIST="$2"
            shift 2
            ;;
        --username)
            USERNAME="$2"
            shift 2
            ;;
        --interactive)
            INTERACTIVE=true
            shift
            ;;
        --non-interactive)
            INTERACTIVE=false
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --job-name NAME        Custom job name (default: auto-generated)"
            echo "  --duration MINUTES     Job duration in minutes (default: 3)"
            echo "  --partition PARTITION  Slurm partition to use (default: prompt user)"
            echo "  --nodelist NODES       Specific nodes to use (default: prompt user)"
            echo "  --username USER        Username to run job as (default: prompt user)"
            echo "  --interactive          Interactive mode with prompts (default)"
            echo "  --non-interactive      Use defaults without prompts"
            echo "  -h, --help             Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Set defaults if not provided
if [ -z "$JOB_NAME" ]; then
    JOB_NAME="jobstats_test_$(date +%Y%m%d_%H%M%S)"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
END='\033[0m'

# Interactive prompts if not provided
if [ "$INTERACTIVE" = true ]; then
    if [ -z "$USERNAME" ]; then
        echo -e "${YELLOW}Enter the username to run the test job as:${END}"
        read -p "Username: " USERNAME
    fi
    
    if [ -z "$PARTITION" ]; then
        echo -e "${YELLOW}Enter the Slurm partition to use:${END}"
        read -p "Partition: " PARTITION
    fi
    
    if [ -z "$NODELIST" ]; then
        echo -e "${YELLOW}Enter specific nodes to use (or press Enter for any available):${END}"
        read -p "Nodelist: " NODELIST
    fi
else
    # Set defaults for non-interactive mode
    USERNAME="${USERNAME:-$(whoami)}"
    PARTITION="${PARTITION:-defq}"
    NODELIST="${NODELIST:-}"
fi

echo -e "${BOLD}${BLUE}================================================${END}"
echo -e "${BOLD}${WHITE}Jobstats Deployment Test Job${END}"
echo -e "${BOLD}${BLUE}================================================${END}"
echo ""
echo -e "${CYAN}Job Name:${END} ${WHITE}${JOB_NAME}${END}"
echo -e "${CYAN}Duration:${END} ${WHITE}${DURATION_MINUTES} minutes${END}"
echo -e "${CYAN}Username:${END} ${WHITE}${USERNAME}${END}"
echo -e "${CYAN}Partition:${END} ${WHITE}${PARTITION}${END}"
if [ -n "$NODELIST" ]; then
    echo -e "${CYAN}Nodelist:${END} ${WHITE}${NODELIST}${END}"
fi
echo -e "${CYAN}GPU Request:${END} ${WHITE}1 GPU${END}"
echo ""

# Create the job script
JOB_SCRIPT="/tmp/${JOB_NAME}.sh"
cat > "$JOB_SCRIPT" << EOF
#!/bin/bash
#SBATCH --job-name=${JOB_NAME}
#SBATCH --partition=${PARTITION}
#SBATCH --gres=gpu:1
#SBATCH --time=00:10:00
#SBATCH --output=/tmp/${JOB_NAME}_%j.out
#SBATCH --error=/tmp/${JOB_NAME}_%j.err

echo "=========================================="
echo "Jobstats Test Job Started"
echo "=========================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_JOD_NODELIST"
echo "GPU: $CUDA_VISIBLE_DEVICES"
echo "Start Time: $(date)"
echo ""

# Function to run GPU workload
run_gpu_workload() {
    local duration=$1
    local start_time=$(date +%s)
    local end_time=$((start_time + duration))
    
    echo "Starting GPU workload for ${duration} seconds..."
    echo "This will generate GPU utilization metrics for jobstats"
    echo ""
    
    # Create a simple GPU workload using nvidia-smi in a loop
    # This will generate GPU utilization without heavy computation
    while [ $(date +%s) -lt $end_time ]; do
        # Run nvidia-smi to generate some GPU activity
        nvidia-smi --query-gpu=timestamp,name,temperature.gpu,utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader,nounits
        
        # Small delay to avoid overwhelming the system
        sleep 2
        
        # Show progress
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        local remaining=$((duration - elapsed))
        if [ $remaining -gt 0 ]; then
            echo "Progress: ${elapsed}s elapsed, ${remaining}s remaining"
        fi
    done
}

# Function to run CPU workload
run_cpu_workload() {
    local duration=$1
    echo "Starting CPU workload for ${duration} seconds..."
    
    # Create some CPU activity with a simple calculation
    local start_time=$(date +%s)
    local end_time=$((start_time + duration))
    local counter=0
    
    while [ $(date +%s) -lt $end_time ]; do
        # Simple CPU-intensive calculation
        result=$(echo "scale=10; $counter * 3.14159 / 1000" | bc -l 2>/dev/null || echo "0")
        counter=$((counter + 1))
        
        # Show progress every 10 iterations
        if [ $((counter % 10)) -eq 0 ]; then
            echo "CPU calculation: iteration $counter, result: $result"
        fi
        
        # Small delay
        sleep 0.1
    done
}

# Check if we have GPU access
if command -v nvidia-smi &> /dev/null; then
    echo "GPU detected. Running GPU workload..."
    echo "GPU Information:"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
    echo ""
    
    # Run GPU workload for the specified duration
    run_gpu_workload $((DURATION_MINUTES * 60))
else
    echo "No GPU detected. Running CPU-only workload..."
    run_cpu_workload $((DURATION_MINUTES * 60))
fi

echo ""
echo "=========================================="
echo "Jobstats Test Job Completed"
echo "=========================================="
echo "End Time: $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo ""

# Show final resource usage
echo "Final Resource Usage:"
if command -v nvidia-smi &> /dev/null; then
    echo "GPU Status:"
    nvidia-smi --query-gpu=timestamp,name,utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader
fi

echo "Memory Usage:"
free -h

echo "CPU Usage:"
uptime

echo ""
echo "This job should have generated metrics for:"
echo "- GPU utilization (if GPU available)"
echo "- CPU usage"
echo "- Memory consumption"
echo "- Job duration and resource allocation"
echo ""
echo "Check jobstats with: jobstats -j $SLURM_JOB_ID"
EOF

# Make the script executable
chmod +x "$JOB_SCRIPT"

# Replace the duration variable in the script
sed -i "s/DURATION_MINUTES/$DURATION_MINUTES/g" "$JOB_SCRIPT"

echo -e "${YELLOW}Submitting test job...${END}"
echo ""

# Load Slurm module if available, otherwise use full path
if command -v module &> /dev/null; then
    module load slurm 2>/dev/null || true
fi

# Set SLURM_CONF if not already set
export SLURM_CONF="${SLURM_CONF:-/cm/shared/apps/slurm/var/etc/slurm/slurm.conf}"

# Find sbatch command
SBATCH_CMD="sbatch"
if ! command -v sbatch &> /dev/null; then
    SBATCH_CMD="/cm/shared/apps/slurm/23.11.10/bin/sbatch"
fi

# Build sbatch command with optional parameters
SBATCH_ARGS=(
    --job-name="$JOB_NAME"
    --partition="$PARTITION"
    --gres=gpu:1
    --time=00:10:00
    --output="/tmp/${JOB_NAME}_%j.out"
    --error="/tmp/${JOB_NAME}_%j.err"
)

# Add nodelist if specified
if [ -n "$NODELIST" ]; then
    SBATCH_ARGS+=(--nodelist="$NODELIST")
fi

# Add user if specified and different from current user
if [ -n "$USERNAME" ] && [ "$USERNAME" != "$(whoami)" ]; then
    SBATCH_ARGS+=(--uid="$USERNAME")
fi

# Submit the job
JOB_ID=$($SBATCH_CMD "${SBATCH_ARGS[@]}" "$JOB_SCRIPT" | awk '{print $4}')

if [ -z "$JOB_ID" ]; then
    echo -e "${RED}❌ Failed to submit job${END}"
    exit 1
fi

echo -e "${GREEN}✅ Job submitted successfully!${END}"
echo -e "${CYAN}Job ID:${END} ${WHITE}${JOB_ID}${END}"
echo ""

# Monitor job status
echo -e "${YELLOW}Monitoring job status...${END}"
echo ""

# Find squeue command
SQUEUE_CMD="squeue"
if ! command -v squeue &> /dev/null; then
    SQUEUE_CMD="/cm/shared/apps/slurm/23.11.10/bin/squeue"
fi

# Wait for job to start
echo -e "${BLUE}Waiting for job to start...${END}"
while $SQUEUE_CMD -j "$JOB_ID" --noheader --format="%T" | grep -q "PENDING"; do
    echo -n "."
    sleep 2
done
echo ""

# Check if job is running
if $SQUEUE_CMD -j "$JOB_ID" --noheader --format="%T" | grep -q "RUNNING"; then
    echo -e "${GREEN}✅ Job is now running!${END}"
    echo ""
    
    # Show job details
    echo -e "${CYAN}Job Details:${END}"
    $SQUEUE_CMD -j "$JOB_ID" --format="%.18i %.9P %.8j %.8u %.2t %.10M %.6D %R"
    echo ""
    
    # Show job output location
    echo -e "${CYAN}Job Output Files:${END}"
    echo -e "  ${WHITE}STDOUT:${END} /tmp/${JOB_NAME}_${JOB_ID}.out"
    echo -e "  ${WHITE}STDERR:${END} /tmp/${JOB_NAME}_${JOB_ID}.err"
    echo ""
    
    echo -e "${YELLOW}Job will run for ${DURATION_MINUTES} minutes...${END}"
    echo -e "${BLUE}You can monitor progress with:${END}"
    echo -e "  ${WHITE}$SQUEUE_CMD -j $JOB_ID${END}"
    echo -e "  ${WHITE}tail -f /tmp/${JOB_NAME}_${JOB_ID}.out${END}"
    echo ""
    
    # Wait for job to complete
    echo -e "${YELLOW}Waiting for job to complete...${END}"
    while $SQUEUE_CMD -j "$JOB_ID" --noheader --format="%T" | grep -q "RUNNING"; do
        echo -n "."
        sleep 10
    done
    echo ""
    
    # Check final status
    FINAL_STATUS=$($SQUEUE_CMD -j "$JOB_ID" --noheader --format="%T" 2>/dev/null || echo "COMPLETED")
    
    if [ "$FINAL_STATUS" = "COMPLETED" ]; then
        echo -e "${GREEN}✅ Job completed successfully!${END}"
    else
        echo -e "${YELLOW}⚠️  Job finished with status: $FINAL_STATUS${END}"
    fi
    
    echo ""
    echo -e "${CYAN}Job Output:${END}"
    echo "----------------------------------------"
    if [ -f "/tmp/${JOB_NAME}_${JOB_ID}.out" ]; then
        cat "/tmp/${JOB_NAME}_${JOB_ID}.out"
    else
        echo "No output file found"
    fi
    echo "----------------------------------------"
    
    if [ -f "/tmp/${JOB_NAME}_${JOB_ID}.err" ] && [ -s "/tmp/${JOB_NAME}_${JOB_ID}.err" ]; then
        echo -e "${YELLOW}Job Errors:${END}"
        echo "----------------------------------------"
        cat "/tmp/${JOB_NAME}_${JOB_ID}.err"
        echo "----------------------------------------"
    fi
    
else
    echo -e "${RED}❌ Job failed to start or was rejected${END}"
    echo -e "${YELLOW}Check job status with: $SQUEUE_CMD -j $JOB_ID${END}"
    exit 1
fi

echo ""
echo -e "${BOLD}${GREEN}================================================${END}"
echo -e "${BOLD}${WHITE}Test Job Summary${END}"
echo -e "${BOLD}${GREEN}================================================${END}"
echo -e "${CYAN}Job ID:${END} ${WHITE}${JOB_ID}${END}"
echo -e "${CYAN}Job Name:${END} ${WHITE}${JOB_NAME}${END}"
echo -e "${CYAN}Duration:${END} ${WHITE}${DURATION_MINUTES} minutes${END}"
echo -e "${CYAN}Status:${END} ${WHITE}${FINAL_STATUS}${END}"
echo ""

echo -e "${BOLD}${YELLOW}Next Steps:${END}"
echo -e "1. ${WHITE}Check jobstats data:${END} jobstats -j $JOB_ID"
if [ -n "$USERNAME" ] && [ "$USERNAME" != "$(whoami)" ]; then
    echo -e "   ${YELLOW}Note: Run as user '$USERNAME' or check their home directory for jobstats data${END}"
fi
echo -e "2. ${WHITE}View in Grafana:${END} http://statsrv:3000"
echo -e "3. ${WHITE}Check Prometheus metrics:${END} http://statsrv:9090"
echo -e "4. ${WHITE}Verify GPU metrics:${END} curl http://dgx-01:9445/metrics"
echo ""

# Clean up
rm -f "$JOB_SCRIPT"

echo -e "${GREEN}✅ Test job completed! Check the metrics in Grafana and Prometheus.${END}"
