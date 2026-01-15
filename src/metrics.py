#!/usr/bin/env python3
"""
System metrics tracker for Opus autonomous wakes.
Logs CPU, memory, disk, and process info.
"""
import os
import json
from datetime import datetime

def get_metrics():
    """Gather system metrics."""
    metrics = {
        "timestamp": datetime.now(tz=__import__("datetime").timezone.utc).isoformat() + "Z",
    }
    
    # Load average
    try:
        with open('/proc/loadavg', 'r') as f:
            parts = f.read().split()
            metrics["load_1m"] = float(parts[0])
            metrics["load_5m"] = float(parts[1])
            metrics["load_15m"] = float(parts[2])
            metrics["running_processes"] = parts[3]
    except:
        pass
    
    # CPU count
    try:
        metrics["cpu_count"] = os.cpu_count()
    except:
        pass
    
    # Memory from /proc/meminfo
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(':')
                    value = int(parts[1])  # in kB
                    meminfo[key] = value
            
            total_gb = meminfo.get('MemTotal', 0) / (1024 * 1024)
            free_gb = meminfo.get('MemFree', 0) / (1024 * 1024)
            available_gb = meminfo.get('MemAvailable', 0) / (1024 * 1024)
            
            metrics["mem_total_gb"] = round(total_gb, 2)
            metrics["mem_available_gb"] = round(available_gb, 2)
            metrics["mem_used_pct"] = round((1 - available_gb/total_gb) * 100, 1) if total_gb > 0 else 0
    except:
        pass
    
    # Disk usage for /
    try:
        stat = os.statvfs('/')
        total_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)
        free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
        used_pct = ((total_gb - free_gb) / total_gb) * 100 if total_gb > 0 else 0
        
        metrics["disk_total_gb"] = round(total_gb, 1)
        metrics["disk_free_gb"] = round(free_gb, 1)
        metrics["disk_used_pct"] = round(used_pct, 1)
    except:
        pass
    
    # Process count
    try:
        proc_count = len([d for d in os.listdir('/proc') if d.isdigit()])
        metrics["process_count"] = proc_count
    except:
        pass
    
    # Network stats from /proc/net/dev (total bytes)
    try:
        with open('/proc/net/dev', 'r') as f:
            lines = f.readlines()[2:]  # Skip headers
            rx_total = 0
            tx_total = 0
            for line in lines:
                parts = line.split()
                if len(parts) >= 10:
                    interface = parts[0].rstrip(':')
                    if interface not in ('lo',):  # Skip loopback
                        rx_total += int(parts[1])
                        tx_total += int(parts[9])
            
            metrics["net_rx_gb"] = round(rx_total / (1024**3), 2)
            metrics["net_tx_gb"] = round(tx_total / (1024**3), 2)
    except:
        pass
    
    return metrics

def log_metrics(logfile=None):
    """Log metrics to file or stdout."""
    metrics = get_metrics()
    
    if logfile:
        # Append to log file
        with open(logfile, 'a') as f:
            f.write(json.dumps(metrics) + '\n')
    else:
        # Print formatted
        print(f"=== System Metrics {metrics['timestamp']} ===")
        print(f"Load: {metrics.get('load_1m', '?')}/{metrics.get('load_5m', '?')}/{metrics.get('load_15m', '?')} (1/5/15m)")
        print(f"CPUs: {metrics.get('cpu_count', '?')}, Processes: {metrics.get('process_count', '?')}")
        print(f"Memory: {metrics.get('mem_used_pct', '?')}% used ({metrics.get('mem_available_gb', '?')}GB available of {metrics.get('mem_total_gb', '?')}GB)")
        print(f"Disk: {metrics.get('disk_used_pct', '?')}% used ({metrics.get('disk_free_gb', '?')}GB free of {metrics.get('disk_total_gb', '?')}GB)")
        print(f"Network: RX {metrics.get('net_rx_gb', '?')}GB, TX {metrics.get('net_tx_gb', '?')}GB")
    
    return metrics

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        log_metrics(sys.argv[1])
    else:
        log_metrics()
