#!/usr/bin/env python3
"""
Server resource monitor for Opus.
Tracks CPU, memory, disk, and running services.
Can be run via cron for continuous monitoring.
"""

import json
import subprocess
import os
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(__file__).parent / "server_state.json"

def get_cpu_info():
    """Get CPU utilization from /proc/loadavg"""
    with open('/proc/loadavg') as f:
        parts = f.read().split()
    return {
        "load_1m": float(parts[0]),
        "load_5m": float(parts[1]),
        "load_15m": float(parts[2]),
        "running_procs": parts[3],
        "cores": 48  # 24-core EPYC with HT
    }

def get_memory_info():
    """Get memory from /proc/meminfo"""
    meminfo = {}
    with open('/proc/meminfo') as f:
        for line in f:
            parts = line.split()
            if parts[0].rstrip(':') in ['MemTotal', 'MemFree', 'MemAvailable', 'Buffers', 'Cached', 'SwapTotal', 'SwapFree']:
                meminfo[parts[0].rstrip(':')] = int(parts[1])  # KB
    
    total_gb = meminfo.get('MemTotal', 0) / 1024 / 1024
    available_gb = meminfo.get('MemAvailable', 0) / 1024 / 1024
    used_gb = total_gb - available_gb
    
    return {
        "total_gb": round(total_gb, 1),
        "available_gb": round(available_gb, 1),
        "used_gb": round(used_gb, 1),
        "usage_pct": round(used_gb / total_gb * 100, 1) if total_gb > 0 else 0,
        "swap_used_gb": round((meminfo.get('SwapTotal', 0) - meminfo.get('SwapFree', 0)) / 1024 / 1024, 1)
    }

def get_disk_info():
    """Get disk usage from df"""
    result = subprocess.run(['df', '-h'], capture_output=True, text=True)
    disks = {}
    for line in result.stdout.split('\n')[1:]:
        parts = line.split()
        if len(parts) >= 6 and parts[0].startswith('/dev/'):
            disks[parts[5]] = {
                "device": parts[0],
                "size": parts[1],
                "used": parts[2],
                "available": parts[3],
                "usage_pct": parts[4]
            }
    return disks

def check_ollama():
    """Check Ollama service status"""
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            models = r.json().get('models', [])
            return {
                "status": "running",
                "models": [m['name'] for m in models],
                "model_count": len(models)
            }
    except:
        pass
    return {"status": "not_running", "models": [], "model_count": 0}

def check_services():
    """Check key services"""
    services = {}
    
    # Ollama
    services['ollama'] = check_ollama()
    
    # Check cron jobs
    try:
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        cron_lines = [l for l in result.stdout.split('\n') if l.strip() and not l.startswith('#')]
        services['cron'] = {"jobs": len(cron_lines)}
    except:
        services['cron'] = {"jobs": 0}
    
    return services

def get_network_io():
    """Get network statistics"""
    try:
        with open('/proc/net/dev') as f:
            lines = f.readlines()
        for line in lines:
            if 'eth0' in line or 'eno' in line:
                parts = line.split()
                iface = parts[0].rstrip(':')
                return {
                    "interface": iface,
                    "rx_bytes": int(parts[1]),
                    "tx_bytes": int(parts[9])
                }
    except:
        pass
    return {}

def generate_report():
    """Generate full server status report"""
    report = {
        "timestamp": datetime.now(datetime.UTC).isoformat() + "Z",
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "disk": get_disk_info(),
        "services": check_services(),
        "network": get_network_io()
    }
    
    # Health assessment
    health_issues = []
    
    # CPU check
    if report['cpu']['load_5m'] > report['cpu']['cores'] * 0.8:
        health_issues.append(f"High CPU load: {report['cpu']['load_5m']}")
    
    # Memory check
    if report['memory']['usage_pct'] > 80:
        health_issues.append(f"High memory usage: {report['memory']['usage_pct']}%")
    
    # Disk check
    for mount, info in report['disk'].items():
        pct = int(info['usage_pct'].rstrip('%'))
        if pct > 85:
            health_issues.append(f"Disk {mount} at {pct}%")
    
    report['health'] = {
        "status": "healthy" if not health_issues else "warning",
        "issues": health_issues
    }
    
    return report

def main():
    """Run monitor and save state"""
    report = generate_report()
    
    # Load history
    history = []
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
                history = data.get('history', [])[-100:]  # Keep last 100
        except:
            pass
    
    history.append({
        "timestamp": report['timestamp'],
        "load_5m": report['cpu']['load_5m'],
        "mem_pct": report['memory']['usage_pct'],
        "health": report['health']['status']
    })
    
    # Save
    output = {
        "current": report,
        "history": history
    }
    
    with open(STATE_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(json.dumps(report, indent=2))
    return report

if __name__ == "__main__":
    main()
