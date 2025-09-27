#!/bin/bash

echo "=== DGX Jobstats Verification Script ==="
echo "Date: $(date)"
echo

# Check systemd services
echo "1. Checking systemd services..."
services=("cgroup_exporter" "node_exporter" "nvidia_gpu_prometheus_exporter" "prometheus" "grafana-server")
for service in "${services[@]}"; do
    if systemctl is-active --quiet "$service"; then
        echo "✅ $service is running"
    else
        echo "❌ $service is not running"
    fi
done
echo

# Check ports
echo "2. Checking service ports..."
ports=("9100:node_exporter" "9306:cgroup_exporter" "9445:nvidia_gpu_exporter" "9090:prometheus" "3000:grafana")
for port_info in "${ports[@]}"; do
    port=$(echo $port_info | cut -d: -f1)
    service=$(echo $port_info | cut -d: -f2)
    if netstat -tlnp | grep -q ":$port "; then
        echo "✅ Port $port ($service) is listening"
    else
        echo "❌ Port $port ($service) is not listening"
    fi
done
echo

# Check metrics endpoints
echo "3. Checking metrics endpoints..."
endpoints=("http://localhost:9100/metrics:node_exporter" "http://localhost:9306/metrics:cgroup_exporter" "http://localhost:9445/metrics:nvidia_gpu_exporter")
for endpoint_info in "${endpoints[@]}"; do
    url=$(echo $endpoint_info | cut -d: -f1-3)
    service=$(echo $endpoint_info | cut -d: -f4)
    if curl -s "$url" | head -1 | grep -q "# HELP"; then
        echo "✅ $service metrics endpoint is responding"
    else
        echo "❌ $service metrics endpoint is not responding"
    fi
done
echo

# Check Prometheus targets
echo "4. Checking Prometheus targets..."
if curl -s http://localhost:9090/api/v1/targets | jq -r '.data.activeTargets[].health' | grep -q "up"; then
    echo "✅ Prometheus has healthy targets"
    echo "   Targets:"
    curl -s http://localhost:9090/api/v1/targets | jq -r '.data.activeTargets[] | "   - \(.labels.job): \(.health)"'
else
    echo "❌ Prometheus targets are not healthy"
fi
echo

# Check jobstats command
echo "5. Checking jobstats command..."
if command -v jobstats >/dev/null 2>&1; then
    echo "✅ jobstats command is available"
    echo "   Version: $(jobstats --help | head -1)"
else
    echo "❌ jobstats command is not available"
fi
echo

# Check Slurm integration
echo "6. Checking Slurm integration..."
if [ -f "/etc/slurm/prolog.d/gpustats_helper.sh" ] && [ -f "/etc/slurm/epilog.d/gpustats_helper.sh" ]; then
    echo "✅ GPU tracking scripts are installed"
else
    echo "❌ GPU tracking scripts are missing"
fi

if [ -f "/usr/local/sbin/slurmctldepilog.sh" ]; then
    echo "✅ Job summary script is installed"
else
    echo "❌ Job summary script is missing"
fi
echo

# Check BCM configuration requirement
echo "7. BCM Configuration Requirements:"
echo "   ⚠️  The following lines need to be added to slurm.conf via BCM:"
echo "      Prolog=/etc/slurm/prolog.d/*.sh"
echo "      Epilog=/etc/slurm/epilog.d/*.sh"
echo "      EpilogSlurmctld=/usr/local/sbin/slurmctldepilog.sh"
echo

echo "=== Verification Complete ==="
