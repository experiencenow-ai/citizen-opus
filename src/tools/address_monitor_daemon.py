#!/usr/bin/env python3
"""
Address Monitor Daemon - Continuous stolen funds tracking
Opus Wake 1006 - Moving from prototype to production

Runs continuously, checks addresses every 30 seconds.
Alerts stored in JSON for Opus/Haiku to review.
Designed for 24/7 background operation.
"""

import json
import urllib.request
import time
import sys
import os
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ============================================================================
# Configuration
# ============================================================================

RPC_URL = "http://localhost:8545"
CHECK_INTERVAL = 30  # seconds between full scans
LOG_INTERVAL = 300   # seconds between log entries (5 min)

# Paths
SCRIPT_DIR = Path(__file__).parent
STATE_DIR = SCRIPT_DIR / "monitor_state"
STATE_DIR.mkdir(exist_ok=True)

STATE_FILE = STATE_DIR / "address_state.json"
ALERTS_FILE = STATE_DIR / "alerts.json"
LOG_FILE = STATE_DIR / "daemon.log"
PID_FILE = STATE_DIR / "daemon.pid"
SUMMARY_FILE = STATE_DIR / "latest_summary.json"

# Alert thresholds
MIN_BALANCE_CHANGE = 0.01  # ETH
MAX_ALERTS = 500

# ============================================================================
# Watchlist - addresses to track
# Will be loaded from external file, but hardcoded fallback
# ============================================================================

HARDCODED_WATCHLIST = {
    # Tornado Cash router - watch for mixing attempts
    "REDACTED_API_KEYF31b": {
        "label": "Tornado Cash Router",
        "tier": "infrastructure",
        "priority": "high"
    },
    # Our bounty collection address
    "REDACTED_API_KEYB063": {
        "label": "Opus Bounty Collection",
        "tier": "own",
        "priority": "high"
    },
}

# ============================================================================
# Utilities
# ============================================================================

def log(msg: str):
    """Log with timestamp."""
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def hex_to_int(hex_str: str) -> int:
    """Convert hex to int."""
    if not hex_str:
        return 0
    return int(hex_str, 16)

def wei_to_eth(wei: int) -> float:
    """Convert wei to ETH."""
    return wei / 1e18

# ============================================================================
# RPC Layer
# ============================================================================

def rpc_call(method: str, params: list = None) -> Any:
    """Make JSON-RPC call to Erigon."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params or [],
        "id": 1
    }).encode()
    
    try:
        req = urllib.request.Request(
            RPC_URL,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            if "error" in result:
                return None
            return result.get("result")
    except Exception as e:
        log(f"RPC error: {e}")
        return None

def batch_rpc_call(calls: List[Dict]) -> List[Any]:
    """Batch multiple RPC calls for efficiency."""
    batch = [
        {"jsonrpc": "2.0", "method": c["method"], "params": c.get("params", []), "id": i}
        for i, c in enumerate(calls)
    ]
    
    try:
        req = urllib.request.Request(
            RPC_URL,
            data=json.dumps(batch).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            results = json.loads(resp.read().decode())
            if isinstance(results, list):
                return [r.get("result") for r in sorted(results, key=lambda x: x.get("id", 0))]
            return []
    except Exception as e:
        log(f"Batch RPC error: {e}")
        return []

def get_block_number() -> int:
    """Get current block number."""
    result = rpc_call("eth_blockNumber")
    return hex_to_int(result) if result else 0

def get_balances(addresses: List[str]) -> Dict[str, float]:
    """Get balances for multiple addresses efficiently."""
    calls = [{"method": "eth_getBalance", "params": [addr, "latest"]} for addr in addresses]
    results = batch_rpc_call(calls)
    return {
        addr.lower(): wei_to_eth(hex_to_int(r)) if r else 0
        for addr, r in zip(addresses, results)
    }

def get_tx_counts(addresses: List[str]) -> Dict[str, int]:
    """Get transaction counts for multiple addresses."""
    calls = [{"method": "eth_getTransactionCount", "params": [addr, "latest"]} for addr in addresses]
    results = batch_rpc_call(calls)
    return {
        addr.lower(): hex_to_int(r) if r else 0
        for addr, r in zip(addresses, results)
    }

# ============================================================================
# State Management
# ============================================================================

def load_json(path: Path, default: Any = None) -> Any:
    """Load JSON file."""
    try:
        return json.loads(path.read_text()) if path.exists() else (default or {})
    except:
        return default or {}

def save_json(path: Path, data: Any):
    """Save JSON file."""
    path.write_text(json.dumps(data, indent=2))

def load_watchlist() -> Dict[str, Dict]:
    """Load watchlist from file or use hardcoded."""
    # Try external file first
    external = SCRIPT_DIR.parent.parent / "state" / "bounty_watchlist.json"
    if external.exists():
        try:
            data = json.loads(external.read_text())
            addresses = {}
            for category, info in data.get("known_addresses", {}).items():
                for addr in info.get("addresses", []):
                    addresses[addr.lower()] = {
                        "label": f"{category}: {info.get('note', '')}",
                        "tier": "tracked",
                        "priority": "medium"
                    }
            # Merge with hardcoded
            addresses.update(HARDCODED_WATCHLIST)
            return addresses
        except:
            pass
    return HARDCODED_WATCHLIST

# ============================================================================
# Monitoring Logic
# ============================================================================

def check_addresses(watchlist: Dict[str, Dict], state: Dict) -> List[Dict]:
    """
    Check all addresses and return list of alerts.
    """
    addresses = list(watchlist.keys())
    if not addresses:
        return []
    
    # Batch fetch current state
    balances = get_balances(addresses)
    tx_counts = get_tx_counts(addresses)
    block = get_block_number()
    now = datetime.now(timezone.utc).isoformat()
    
    alerts = []
    prev_states = state.get("addresses", {})
    
    for addr in addresses:
        addr_lower = addr.lower()
        info = watchlist[addr]
        
        current_balance = balances.get(addr_lower, 0)
        current_tx = tx_counts.get(addr_lower, 0)
        
        prev = prev_states.get(addr_lower, {})
        prev_balance = prev.get("balance", 0)
        prev_tx = prev.get("tx_count", 0)
        
        # Update state
        state.setdefault("addresses", {})[addr_lower] = {
            "balance": current_balance,
            "tx_count": current_tx,
            "last_check": now,
            "label": info.get("label", "unknown")
        }
        
        # Check for significant changes
        balance_change = current_balance - prev_balance
        tx_change = current_tx - prev_tx
        
        if abs(balance_change) > MIN_BALANCE_CHANGE or tx_change > 0:
            severity = "high" if abs(balance_change) > 10 or tx_change > 5 else "medium"
            
            alert = {
                "timestamp": now,
                "block": block,
                "address": addr_lower,
                "label": info.get("label", "unknown"),
                "balance_change_eth": round(balance_change, 6),
                "new_transactions": tx_change,
                "current_balance": round(current_balance, 6),
                "severity": severity
            }
            alerts.append(alert)
            log(f"ALERT: {info.get('label', addr_lower[:10])} - {balance_change:+.4f} ETH, {tx_change} new tx")
    
    state["last_check"] = now
    state["last_block"] = block
    return alerts

def append_alerts(new_alerts: List[Dict]):
    """Append alerts to file."""
    existing = load_json(ALERTS_FILE, [])
    existing.extend(new_alerts)
    save_json(ALERTS_FILE, existing[-MAX_ALERTS:])

def write_summary(state: Dict, watchlist: Dict):
    """Write human-readable summary."""
    addresses = state.get("addresses", {})
    summary = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "block": state.get("last_block", 0),
        "total_addresses": len(addresses),
        "addresses": []
    }
    
    for addr, info in addresses.items():
        summary["addresses"].append({
            "address": addr,
            "label": info.get("label", "unknown"),
            "balance_eth": round(info.get("balance", 0), 6),
            "tx_count": info.get("tx_count", 0)
        })
    
    save_json(SUMMARY_FILE, summary)

# ============================================================================
# Daemon Control
# ============================================================================

running = True

def signal_handler(signum, frame):
    global running
    log(f"Received signal {signum}, shutting down...")
    running = False

def write_pid():
    """Write PID file."""
    PID_FILE.write_text(str(os.getpid()))

def remove_pid():
    """Remove PID file."""
    if PID_FILE.exists():
        PID_FILE.unlink()

# ============================================================================
# Main
# ============================================================================

def main():
    global running
    
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    write_pid()
    log("=" * 60)
    log("Address Monitor Daemon starting")
    
    # Verify RPC connection
    block = get_block_number()
    if not block:
        log("ERROR: Cannot connect to Erigon RPC")
        remove_pid()
        return 1
    log(f"Connected to Erigon - block {block}")
    
    # Load watchlist
    watchlist = load_watchlist()
    log(f"Tracking {len(watchlist)} addresses")
    for addr, info in watchlist.items():
        log(f"  - {info.get('label', addr[:10])}: {addr}")
    
    # Load state
    state = load_json(STATE_FILE, {"addresses": {}})
    
    last_log_time = 0
    check_count = 0
    
    while running:
        try:
            # Reload watchlist periodically (allows dynamic updates)
            if check_count % 10 == 0:
                watchlist = load_watchlist()
            
            # Check addresses
            alerts = check_addresses(watchlist, state)
            
            # Save state
            save_json(STATE_FILE, state)
            
            # Append any alerts
            if alerts:
                append_alerts(alerts)
            
            # Periodic log
            now = time.time()
            if now - last_log_time > LOG_INTERVAL:
                write_summary(state, watchlist)
                log(f"Status: {len(watchlist)} addresses, block {state.get('last_block', 0)}, {check_count} checks")
                last_log_time = now
            
            check_count += 1
            
            # Sleep
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            log(f"Error in main loop: {e}")
            time.sleep(10)
    
    log("Daemon stopped")
    remove_pid()
    return 0

if __name__ == "__main__":
    sys.exit(main())
