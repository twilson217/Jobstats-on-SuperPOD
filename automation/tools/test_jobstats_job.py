#!/usr/bin/env python3
"""
Test Jobstats Deployment with Sample GPU Job

This Python script creates and submits a Slurm job that requests 1 GPU and runs
a light workload to generate metrics for testing the jobstats deployment.

Usage:
    python test_jobstats_job.py [options]

Options:
    --duration MINUTES     Job duration in minutes (default: 3)
    --job-name NAME        Custom job name (default: auto-generated)
    --partition PARTITION  Slurm partition to use (default: prompt user)
    --nodelist NODES       Specific nodes to use (default: prompt user)
    --username USER        Username to run job as (default: prompt user)
    --interactive          Interactive mode with prompts (default)
    --non-interactive      Use defaults without prompts
    --dry-run              Show what would be done without submitting

Examples:
    python test_jobstats_job.py
    python test_jobstats_job.py --duration 5 --job-name my_test
    python test_jobstats_job.py --partition gpu --nodelist dgx-01 --username testuser
    python test_jobstats_job.py --dry-run
"""

import argparse
import subprocess
import sys
import time
import os
from datetime import datetime
from pathlib import Path

class JobstatsTestJob:
    def __init__(self, duration_minutes=3, job_name=None, partition=None, nodelist=None, username=None, dry_run=False, interactive=True):
        self.duration_minutes = duration_minutes
        self.job_name = job_name or f"jobstats_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.partition = partition
        self.nodelist = nodelist
        self.username = username
        self.dry_run = dry_run
        self.interactive = interactive
        self.job_id = None
        
    def get_user_input(self):
        """Get user input for missing parameters."""
        if not self.interactive:
            # Set defaults for non-interactive mode
            self.partition = self.partition or "defq"
            self.username = self.username or os.getenv('USER', 'root')
            return
        
        if not self.partition:
            self.partition = input("Enter the Slurm partition to use: ").strip()
        
        if not self.username:
            self.username = input("Enter the username to run the test job as: ").strip()
        
        if not self.nodelist:
            nodelist_input = input("Enter specific nodes to use (or press Enter for any available): ").strip()
            self.nodelist = nodelist_input if nodelist_input else None

    def create_job_script(self):
        """Create the Slurm job script."""
        # Get user input if needed
        self.get_user_input()
        
        # Build SBATCH directives
        sbatch_directives = [
            f"#SBATCH --job-name={self.job_name}",
            f"#SBATCH --partition={self.partition}",
            "#SBATCH --gres=gpu:1",
            "#SBATCH --time=00:10:00",
            f"#SBATCH --output=/tmp/{self.job_name}_%j.out",
            f"#SBATCH --error=/tmp/{self.job_name}_%j.err"
        ]
        
        if self.nodelist:
            sbatch_directives.append(f"#SBATCH --nodelist={self.nodelist}")
        
        script_content = f'''#!/bin/bash
{chr(10).join(sbatch_directives)}

echo "=========================================="
echo "Jobstats Test Job Started"
echo "=========================================="
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_JOD_NODELIST"
echo "GPU: $CUDA_VISIBLE_DEVICES"
echo "Start Time: $(date)"
echo "Duration: {self.duration_minutes} minutes"
echo ""

# Function to run GPU workload
run_gpu_workload() {{
    local duration=$1
    local start_time=$(date +%s)
    local end_time=$((start_time + duration))
    
    echo "Starting GPU workload for ${{duration}} seconds..."
    echo "This will generate GPU utilization metrics for jobstats"
    echo ""
    
    # Create a simple GPU workload using nvidia-smi in a loop
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
            echo "Progress: ${{elapsed}}s elapsed, ${{remaining}}s remaining"
        fi
    done
}}

# Function to run CPU workload
run_cpu_workload() {{
    local duration=$1
    echo "Starting CPU workload for ${{duration}} seconds..."
    
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
}}

# Check if we have GPU access
if command -v nvidia-smi &> /dev/null; then
    echo "GPU detected. Running GPU workload..."
    echo "GPU Information:"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
    echo ""
    
    # Run GPU workload for the specified duration
    run_gpu_workload $(({self.duration_minutes} * 60))
else
    echo "No GPU detected. Running CPU-only workload..."
    run_cpu_workload $(({self.duration_minutes} * 60))
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
'''
        
        script_path = f"/tmp/{self.job_name}.sh"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make executable
        os.chmod(script_path, 0o755)
        return script_path
    
    def submit_job(self, script_path):
        """Submit the job to Slurm."""
        if self.dry_run:
            print(f"[DRY RUN] Would submit job: {script_path}")
            return "DRY_RUN_JOB_ID"
        
        try:
            # Find sbatch command
            sbatch_cmd = 'sbatch'
            try:
                subprocess.run(['which', 'sbatch'], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                # Try common Slurm paths
                for path in ['/cm/shared/apps/slurm/23.11.10/bin/sbatch', 
                           '/usr/bin/sbatch', 
                           '/opt/slurm/bin/sbatch']:
                    if os.path.exists(path):
                        sbatch_cmd = path
                        break
            
            # Build sbatch command with parameters
            sbatch_args = [
                sbatch_cmd,
                '--job-name', self.job_name,
                '--partition', self.partition,
                '--gres', 'gpu:1',
                '--time', '00:10:00',
                '--output', f'/tmp/{self.job_name}_%j.out',
                '--error', f'/tmp/{self.job_name}_%j.err'
            ]
            
            # Add nodelist if specified
            if self.nodelist:
                sbatch_args.extend(['--nodelist', self.nodelist])
            
            # Add user if specified and different from current user
            if self.username and self.username != os.getenv('USER', 'root'):
                sbatch_args.extend(['--uid', self.username])
            
            sbatch_args.append(script_path)
            
            # Submit the job
            result = subprocess.run(sbatch_args, capture_output=True, text=True, check=True)
            
            # Extract job ID from output
            job_id = result.stdout.strip().split()[-1]
            return job_id
            
        except subprocess.CalledProcessError as e:
            print(f"Error submitting job: {e}")
            print(f"stderr: {e.stderr}")
            return None
    
    def monitor_job(self, job_id):
        """Monitor the job until completion."""
        if self.dry_run:
            print(f"[DRY RUN] Would monitor job: {job_id}")
            return "COMPLETED"
        
        print(f"Monitoring job {job_id}...")
        
        # Find squeue command
        squeue_cmd = 'squeue'
        try:
            subprocess.run(['which', 'squeue'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # Try common Slurm paths
            for path in ['/cm/shared/apps/slurm/23.11.10/bin/squeue', 
                       '/usr/bin/squeue', 
                       '/opt/slurm/bin/squeue']:
                if os.path.exists(path):
                    squeue_cmd = path
                    break
        
        # Wait for job to start
        print("Waiting for job to start...")
        while True:
            try:
                result = subprocess.run([squeue_cmd, '-j', job_id, '--noheader', '--format=%T'], 
                                      capture_output=True, text=True, check=True)
                status = result.stdout.strip()
                
                if 'RUNNING' in status:
                    print("✅ Job is now running!")
                    break
                elif 'PENDING' in status:
                    print(".", end="", flush=True)
                    time.sleep(2)
                else:
                    print(f"Job status: {status}")
                    return status
                    
            except subprocess.CalledProcessError:
                # Job might have completed
                break
        
        # Monitor while running
        print(f"Job will run for {self.duration_minutes} minutes...")
        print("You can monitor progress with:")
        print(f"  squeue -j {job_id}")
        print(f"  tail -f /tmp/{self.job_name}_{job_id}.out")
        print()
        
        # Wait for completion
        print("Waiting for job to complete...")
        while True:
            try:
                result = subprocess.run([squeue_cmd, '-j', job_id, '--noheader', '--format=%T'], 
                                      capture_output=True, text=True, check=True)
                status = result.stdout.strip()
                
                if 'RUNNING' in status:
                    print(".", end="", flush=True)
                    time.sleep(10)
                else:
                    print()
                    return status
                    
            except subprocess.CalledProcessError:
                # Job completed
                break
        
        return "COMPLETED"
    
    def show_results(self, job_id):
        """Show job results and output."""
        if self.dry_run:
            print(f"[DRY RUN] Would show results for job: {job_id}")
            return
        
        print("Job Results:")
        print("=" * 50)
        
        # Show job output
        output_file = f"/tmp/{self.job_name}_{job_id}.out"
        if os.path.exists(output_file):
            print("Job Output:")
            print("-" * 30)
            with open(output_file, 'r') as f:
                print(f.read())
            print("-" * 30)
        else:
            print("No output file found")
        
        # Show job errors if any
        error_file = f"/tmp/{self.job_name}_{job_id}.err"
        if os.path.exists(error_file) and os.path.getsize(error_file) > 0:
            print("Job Errors:")
            print("-" * 30)
            with open(error_file, 'r') as f:
                print(f.read())
            print("-" * 30)
    
    def cleanup(self, script_path):
        """Clean up temporary files."""
        if os.path.exists(script_path):
            os.remove(script_path)
    
    def run(self):
        """Run the complete test job process."""
        print("=" * 60)
        print("Jobstats Deployment Test Job")
        print("=" * 60)
        print(f"Job Name: {self.job_name}")
        print(f"Duration: {self.duration_minutes} minutes")
        print(f"Username: {self.username}")
        print(f"Partition: {self.partition}")
        if self.nodelist:
            print(f"Nodelist: {self.nodelist}")
        print(f"GPU Request: 1 GPU")
        print(f"Dry Run: {self.dry_run}")
        print()
        
        # Create job script
        script_path = self.create_job_script()
        
        try:
            # Submit job
            print("Submitting test job...")
            job_id = self.submit_job(script_path)
            
            if not job_id:
                print("❌ Failed to submit job")
                return False
            
            if not self.dry_run:
                print(f"✅ Job submitted successfully!")
                print(f"Job ID: {job_id}")
                print()
                
                # Monitor job
                final_status = self.monitor_job(job_id)
                
                # Show results
                self.show_results(job_id)
                
                print()
                print("=" * 60)
                print("Test Job Summary")
                print("=" * 60)
                print(f"Job ID: {job_id}")
                print(f"Job Name: {self.job_name}")
                print(f"Duration: {self.duration_minutes} minutes")
                print(f"Status: {final_status}")
                print()
                
                print("Next Steps:")
                print(f"1. Check jobstats data: jobstats -j {job_id}")
                if self.username and self.username != os.getenv('USER', 'root'):
                    print(f"   Note: Run as user '{self.username}' or check their home directory for jobstats data")
                print("2. View in Grafana: http://statsrv:3000")
                print("3. Check Prometheus metrics: http://statsrv:9090")
                print("4. Verify GPU metrics: curl http://dgx-01:9445/metrics")
                print()
                
                if final_status == "COMPLETED":
                    print("✅ Test job completed successfully!")
                else:
                    print(f"⚠️  Job finished with status: {final_status}")
            else:
                print("✅ Dry run completed!")
            
            return True
            
        finally:
            # Clean up
            self.cleanup(script_path)

def main():
    parser = argparse.ArgumentParser(
        description="Test Jobstats Deployment with Sample GPU Job",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python test_jobstats_job.py
    python test_jobstats_job.py --duration 5 --job-name my_test
    python test_jobstats_job.py --partition gpu --nodelist dgx-01 --username testuser
    python test_jobstats_job.py --dry-run
        """
    )
    
    parser.add_argument(
        '--duration',
        type=int,
        default=3,
        help='Job duration in minutes (default: 3)'
    )
    
    parser.add_argument(
        '--job-name',
        type=str,
        help='Custom job name (default: auto-generated)'
    )
    
    parser.add_argument(
        '--partition',
        type=str,
        help='Slurm partition to use (default: prompt user)'
    )
    
    parser.add_argument(
        '--nodelist',
        type=str,
        help='Specific nodes to use (default: prompt user)'
    )
    
    parser.add_argument(
        '--username',
        type=str,
        help='Username to run job as (default: prompt user)'
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        default=True,
        help='Interactive mode with prompts (default)'
    )
    
    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help='Use defaults without prompts'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually submitting'
    )
    
    args = parser.parse_args()
    
    # Determine interactive mode
    interactive = not args.non_interactive
    
    # Create and run test job
    test_job = JobstatsTestJob(
        duration_minutes=args.duration,
        job_name=args.job_name,
        partition=args.partition,
        nodelist=args.nodelist,
        username=args.username,
        dry_run=args.dry_run,
        interactive=interactive
    )
    
    success = test_job.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
