#!/bin/bash
#SBATCH --job-name=cpu_load_test
#SBATCH --partition=defq
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=5:00
#SBATCH --output=cpu_test_%j.out
#SBATCH --error=cpu_test_%j.err

echo "=== CPU Load Test Job ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_NODELIST"
echo "CPUs allocated: $SLURM_CPUS_PER_TASK"
echo "Start time: $(date)"
echo "========================="

# Load modules if available
if command -v module >/dev/null 2>&1; then
    module load slurm 2>/dev/null || true
fi

# Run the CPU load test
python3 /root/jobstat/automation/tools/cpu_load_test.py --duration 120 --processes 4 --intensity 150 --verbose

echo "========================="
echo "Job completed at: $(date)"
