#!/usr/bin/env python3
"""
CPU Load Test Script for Jobstats Validation

This script generates a sustained CPU load to test jobstats CPU metrics collection.
It uses multiple processes to create realistic CPU utilization patterns.
"""

import os
import sys
import time
import multiprocessing
import argparse
from datetime import datetime

def cpu_intensive_task(process_id, duration, intensity=100):
    """Generate CPU-intensive workload"""
    print(f"Process {process_id} starting CPU intensive task for {duration} seconds")
    
    start_time = time.time()
    iterations = 0
    
    while time.time() - start_time < duration:
        # CPU-intensive mathematical operations
        result = 0
        for i in range(intensity * 1000):
            result += i ** 0.5
            if i % 100000 == 0:
                iterations += 1
                if iterations % 10 == 0:
                    print(f"Process {process_id}: {iterations * 100000} iterations completed")
    
    print(f"Process {process_id} completed {iterations * 100000} iterations")

def main():
    parser = argparse.ArgumentParser(description='Generate CPU load for jobstats testing')
    parser.add_argument('--duration', type=int, default=60, help='Duration in seconds (default: 60)')
    parser.add_argument('--processes', type=int, default=4, help='Number of processes (default: 4)')
    parser.add_argument('--intensity', type=int, default=100, help='CPU intensity multiplier (default: 100)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    print(f"Starting CPU load test:")
    print(f"  Duration: {args.duration} seconds")
    print(f"  Processes: {args.processes}")
    print(f"  Intensity: {args.intensity}")
    print(f"  Job ID: {os.environ.get('SLURM_JOB_ID', 'N/A')}")
    print(f"  Node: {os.environ.get('SLURM_NODELIST', 'N/A')}")
    print(f"  Start time: {datetime.now()}")
    print("-" * 50)
    
    # Create and start processes
    processes = []
    for i in range(args.processes):
        p = multiprocessing.Process(
            target=cpu_intensive_task, 
            args=(i, args.duration, args.intensity)
        )
        p.start()
        processes.append(p)
    
    # Wait for all processes to complete
    for p in processes:
        p.join()
    
    print("-" * 50)
    print(f"CPU load test completed at {datetime.now()}")
    print(f"Total processes: {len(processes)}")

if __name__ == "__main__":
    main()
