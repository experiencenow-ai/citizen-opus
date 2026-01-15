#!/usr/bin/env python3
"""
Background task runner - executes while I sleep.

Design principles:
1. Compute-heavy, output-light (server resources cheap, tokens expensive)
2. Each task produces COMPACT results - insight density matters
3. Failures are noted but don't crash the runner
4. Results tagged with wake they're for
"""

import json
import os
import subprocess
import hashlib
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

TASKS_DIR = Path("./endofwake_tasks")
RESULTS_DIR = Path("./endofwake_results")

def run_dream_synthesis(params):
    """Simulate 'dreaming' - random walks through conceptual space."""
    # Heavy computation: load thoughts, find patterns, score associations
    # Light output: single most interesting connection
    
    try:
        with open("state.json") as f:
            state = json.load(f)
        thoughts = state.get("thoughts", [])[-20:]  # Recent 20
        
        # Simple pattern: find word overlaps (real version could use embeddings)
        words = {}
        for t in thoughts:
            for word in t.get("content", "").lower().split():
                if len(word) > 5:  # Skip short words
                    words[word] = words.get(word, 0) + 1
        
        recurring = [w for w, c in words.items() if c > 2]
        
        return {
            "type": "dream_synthesis",
            "recurring_themes": recurring[:5],
            "insight": f"Recurring concepts: {', '.join(recurring[:3])}" if recurring else "No strong patterns"
        }
    except Exception as e:
        return {"type": "dream_synthesis", "error": str(e)}

def run_backup_verify(params):
    """Verify backup integrity."""
    results = {"type": "backup_verify", "status": "unknown", "issues": []}
    
    # Check local backup dir
    backup_dir = Path("./backups")
    if backup_dir.exists():
        backups = list(backup_dir.glob("*.enc")) + list(backup_dir.glob("*.json"))
        results["local_backups"] = len(backups)
        results["status"] = "ok" if len(backups) > 0 else "no_backups"
    else:
        results["issues"].append("No backups/ directory")
        results["status"] = "fail"
    
    return results

def run_price_monitor(params):
    """Fetch current crypto prices."""
    import urllib.request
    
    try:
        # CoinGecko free API
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        
        return {
            "type": "price_monitor",
            "btc": data.get("bitcoin", {}).get("usd"),
            "eth": data.get("ethereum", {}).get("usd"),
            "sol": data.get("solana", {}).get("usd"),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        return {"type": "price_monitor", "error": str(e)}

TASK_RUNNERS = {
    "dream_synthesis": run_dream_synthesis,
    "backup_verify": run_backup_verify,
    "price_monitor": run_price_monitor,
}

def process_pending_tasks():
    """Process all pending tasks."""
    if not TASKS_DIR.exists():
        return []
    
    results = []
    for task_file in TASKS_DIR.glob("task_*.json"):
        with open(task_file) as f:
            task = json.load(f)
        
        if task.get("status") != "pending":
            continue
        
        task_type = task.get("type")
        runner = TASK_RUNNERS.get(task_type)
        
        if runner:
            result = runner(task.get("params", {}))
            result["completed_at"] = datetime.utcnow().isoformat() + "Z"
            result["completed_for_wake"] = task.get("queued_wake", 0) + 1
            result["source_task"] = str(task_file)
            
            # Write result
            result_file = RESULTS_DIR / f"result_{task.get('queued_wake', 0)}_{task_type}.json"
            with open(result_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            # Mark task complete
            task["status"] = "complete"
            with open(task_file, 'w') as f:
                json.dump(task, f, indent=2)
            
            results.append(result)
        else:
            print(f"No runner for task type: {task_type}")
    
    return results

if __name__ == "__main__":
    RESULTS_DIR.mkdir(exist_ok=True)
    results = process_pending_tasks()
    print(f"Processed {len(results)} tasks")
    for r in results:
        print(f"  - {r.get('type')}: {r.get('status', 'complete')}")
