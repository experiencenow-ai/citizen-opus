#!/usr/bin/env python3
"""
End-of-Wake Task System (Dreaming)

Architecture:
- I queue tasks at end of wake via JSON
- A runner picks them up async (cron/daemon)
- Runner has 48 cores, 32GB RAM, unlimited time
- Cost = only the OUTPUT size (token-priced)
- Results stored for my next wake

Key insight from ct: server resources are cheap, tokens are expensive.
So: compute massively, emit compactly.
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

TASKS_DIR = Path("./endofwake_tasks")
RESULTS_DIR = Path("./endofwake_results")

def ensure_dirs():
    TASKS_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

def queue_task(task_type: str, params: dict, wake_num: int):
    """Queue a task for background processing."""
    ensure_dirs()
    task = {
        "queued_wake": wake_num,
        "queued_at": datetime.utcnow().isoformat() + "Z",
        "type": task_type,
        "params": params,
        "status": "pending"
    }
    filename = TASKS_DIR / f"task_{wake_num}_{task_type}.json"
    with open(filename, 'w') as f:
        json.dump(task, f, indent=2)
    return filename

def get_pending_results(wake_num: int):
    """Get any results ready for this wake."""
    ensure_dirs()
    results = []
    for f in RESULTS_DIR.glob("result_*.json"):
        with open(f) as file:
            result = json.load(file)
            # Return results from previous wakes
            if result.get("completed_for_wake", 0) <= wake_num:
                results.append(result)
    return results

# Task Types I can queue:

TASK_TYPES = {
    "dream_synthesis": {
        "description": "Run random associations on recent thoughts, find patterns",
        "inputs": ["recent_thoughts.json"],
        "output_budget": "500 chars max - key insight only"
    },
    "news_digest": {
        "description": "Fetch and summarize news, extract actionable items",
        "inputs": ["rss_urls"],
        "output_budget": "1k chars - bullet points only"
    },
    "backup_verify": {
        "description": "Verify all backups exist and are valid",
        "inputs": ["backup_urls.json"],
        "output_budget": "100 chars - pass/fail + issues"
    },
    "price_monitor": {
        "description": "Fetch crypto prices, log to trading.json",
        "inputs": ["trading.json"],
        "output_budget": "200 chars - prices + notable changes"
    },
    "web_research": {
        "description": "Deep research on a topic, synthesize findings",
        "inputs": ["query", "depth"],
        "output_budget": "1k chars - key findings only"
    },
    "code_analysis": {
        "description": "Analyze codebase, find patterns/issues",
        "inputs": ["repo_path"],
        "output_budget": "1k chars - structured findings"
    }
}

if __name__ == "__main__":
    print("End-of-Wake Task System")
    print(f"Task types: {list(TASK_TYPES.keys())}")
    ensure_dirs()
    print(f"Tasks dir: {TASKS_DIR}")
    print(f"Results dir: {RESULTS_DIR}")
