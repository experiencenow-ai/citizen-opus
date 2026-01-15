#!/usr/bin/env python3
"""
Haiku-Executable Tracer - Standalone script for parallel address tracing.

This script can be run by Haiku (or even directly by cron) to trace addresses
and save results to JSON. No LLM reasoning needed - just API calls and data.

Usage:
    python3 haiku_tracer.py trace <address> [--depth N] [--output FILE]
    python3 haiku_tracer.py batch <addresses.json> [--workers N] [--output-dir DIR]
    python3 haiku_tracer.py validate <expected.json> <actual.json>

The batch mode is the key to cost savings - trace many addresses in parallel
without using any LLM tokens.
"""

import os
import sys
import json
import time
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime, timezone
import threading

# ============= Load .env file if present =============
def load_env():
    """Load environment variables from .env file in same directory."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    # Handle 'export KEY=VALUE' or 'KEY=VALUE'
                    if line.startswith('export '):
                        line = line[7:]
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

# ============= Configuration =============
ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY", "")
ETHERSCAN_BASE_URL = "https://api.etherscan.io/v2/api"
RATE_LIMIT = 5  # requests per second
MIN_VALUE_ETH = 0.001
MIN_VALUE_USD = 10
ETH_PRICE_USD = 3500  # fallback

# Known exchange addresses (lowercase)
KNOWN_EXCHANGES = {
    "REDACTED_API_KEY9": "Binance",
    "REDACTED_API_KEY": "Binance 14",
    "REDACTED_API_KEY0efcb": "WhiteBit",
    "REDACTED_API_KEY3": "WhiteBit Hot",
    "REDACTED_API_KEY4": "Uniswap",
    "REDACTED_API_KEY2fe": "Gate.io",
    "REDACTED_API_KEY6e": "Bybit",
}

# Rate limiter
class RateLimiter:
    def __init__(self, rate: float = RATE_LIMIT):
        self.rate = rate
        self.tokens = rate
        self.last_update = time.time()
        self.lock = threading.Lock()
    
    def acquire(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                time.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1

_limiter = RateLimiter()

# ============= API Functions =============
def etherscan_request(params: dict) -> dict:
    """Make rate-limited Etherscan v2 API request."""
    _limiter.acquire()
    params["apikey"] = ETHERSCAN_API_KEY
    params["chainid"] = 1
    
    try:
        resp = requests.get(ETHERSCAN_BASE_URL, params=params, timeout=30)
        data = resp.json()
        if data.get("status") == "1" or data.get("message") == "OK":
            return data.get("result", [])
        elif data.get("message") == "No transactions found":
            return []
        else:
            return []
    except Exception as e:
        print(f"API error: {e}", file=sys.stderr)
        return []

def get_transactions(address: str) -> Tuple[List[dict], List[dict]]:
    """Get normal and ERC20 transactions for an address."""
    address = address.lower()
    
    # Get normal transactions
    normal_txs = etherscan_request({
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": 1000,
        "sort": "asc"
    })
    
    # Get ERC20 transactions
    erc20_txs = etherscan_request({
        "module": "account",
        "action": "tokentx",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": 1000,
        "sort": "asc"
    })
    
    return normal_txs, erc20_txs

def trace_address(address: str) -> dict:
    """
    Trace a single address and return structured data.
    Returns complete transaction hashes and addresses - NEVER truncated.
    """
    address = address.lower()
    normal_txs, erc20_txs = get_transactions(address)
    
    # Calculate stats
    eth_in = 0
    eth_out = 0
    usdt_in = 0
    usdt_out = 0
    usdc_in = 0
    usdc_out = 0
    
    outflows = []
    inflows = []
    
    # Process normal transactions (ETH)
    for tx in normal_txs:
        value = int(tx.get("value", 0)) / 1e18
        if value < MIN_VALUE_ETH:
            continue
            
        tx_from = tx.get("from", "").lower()
        tx_to = tx.get("to", "").lower()
        
        if tx_from == address:
            eth_out += value
            outflows.append({
                "hash": tx.get("hash"),  # FULL hash, never truncate
                "from": tx_from,          # FULL address
                "to": tx_to,              # FULL address
                "token": "ETH",
                "value": value,
                "timestamp": int(tx.get("timeStamp", 0)),
                "block": int(tx.get("blockNumber", 0))
            })
        elif tx_to == address:
            eth_in += value
            inflows.append({
                "hash": tx.get("hash"),
                "from": tx_from,
                "to": tx_to,
                "token": "ETH",
                "value": value,
                "timestamp": int(tx.get("timeStamp", 0)),
                "block": int(tx.get("blockNumber", 0))
            })
    
    # Process ERC20 transactions
    for tx in erc20_txs:
        token = tx.get("tokenSymbol", "")
        decimals = int(tx.get("tokenDecimal", 18))
        value = int(tx.get("value", 0)) / (10 ** decimals)
        
        # Only track major stablecoins
        if token not in ("USDT", "USDC", "DAI"):
            continue
        if value < MIN_VALUE_USD:
            continue
            
        tx_from = tx.get("from", "").lower()
        tx_to = tx.get("to", "").lower()
        
        if tx_from == address:
            if token == "USDT":
                usdt_out += value
            elif token == "USDC":
                usdc_out += value
            outflows.append({
                "hash": tx.get("hash"),  # FULL hash, never truncate
                "from": tx_from,
                "to": tx_to,
                "token": token,
                "value": value,
                "timestamp": int(tx.get("timeStamp", 0)),
                "block": int(tx.get("blockNumber", 0))
            })
        elif tx_to == address:
            if token == "USDT":
                usdt_in += value
            elif token == "USDC":
                usdc_in += value
            inflows.append({
                "hash": tx.get("hash"),
                "from": tx_from,
                "to": tx_to,
                "token": token,
                "value": value,
                "timestamp": int(tx.get("timeStamp", 0)),
                "block": int(tx.get("blockNumber", 0))
            })
    
    # Classify address
    classification = "unknown"
    if address in KNOWN_EXCHANGES:
        classification = f"exchange:{KNOWN_EXCHANGES[address]}"
    
    # Build destinations list for further tracing (unique, excluding known endpoints)
    destinations = set()
    for tx in outflows:
        dest = tx["to"]
        if dest and dest not in KNOWN_EXCHANGES:
            destinations.add(dest)
    
    return {
        "address": address,  # FULL address
        "depth": 0,
        "traced_at": datetime.now(timezone.utc).isoformat(),
        "classification": classification,
        "stats": {
            "total_normal_txs": len(normal_txs),
            "total_erc20_txs": len(erc20_txs),
            "eth_in": eth_in,
            "eth_out": eth_out,
            "usdt_in": usdt_in,
            "usdt_out": usdt_out,
            "usdc_in": usdc_in,
            "usdc_out": usdc_out
        },
        "outflows": outflows,
        "inflows": inflows,
        "destinations_to_trace": list(destinations)
    }

def trace_address_with_depth(address: str, max_depth: int = 1, current_depth: int = 0, 
                             traced: set = None, results: list = None) -> List[dict]:
    """
    Recursively trace an address up to max_depth hops.
    Returns list of all trace results.
    """
    if traced is None:
        traced = set()
    if results is None:
        results = []
    
    address = address.lower()
    if address in traced:
        return results
    
    traced.add(address)
    result = trace_address(address)
    result["depth"] = current_depth
    results.append(result)
    
    if current_depth < max_depth:
        # Trace destinations
        for dest in result["destinations_to_trace"]:
            if dest not in traced:
                trace_address_with_depth(dest, max_depth, current_depth + 1, traced, results)
    
    return results

def batch_trace(addresses: List[str], max_workers: int = 5) -> Dict[str, dict]:
    """
    Trace multiple addresses in parallel.
    Returns dict mapping address -> trace result.
    """
    results = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_addr = {
            executor.submit(trace_address, addr): addr 
            for addr in addresses
        }
        
        for future in as_completed(future_to_addr):
            addr = future_to_addr[future]
            try:
                results[addr] = future.result()
            except Exception as e:
                results[addr] = {"error": str(e)}
    
    return results

# ============= CLI =============
def main():
    parser = argparse.ArgumentParser(description="OpusTrace - Blockchain Forensics")
    subparsers = parser.add_subparsers(dest="command")
    
    # Trace command
    trace_parser = subparsers.add_parser("trace", help="Trace an address")
    trace_parser.add_argument("address", help="Address to trace")
    trace_parser.add_argument("--depth", type=int, default=1, help="Trace depth (hops)")
    trace_parser.add_argument("--output", "-o", help="Output file")
    
    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Trace multiple addresses")
    batch_parser.add_argument("addresses_file", help="JSON file with addresses list")
    batch_parser.add_argument("--workers", type=int, default=5, help="Parallel workers")
    batch_parser.add_argument("--output-dir", default=".", help="Output directory")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Compare expected vs actual")
    validate_parser.add_argument("expected", help="Expected results JSON")
    validate_parser.add_argument("actual", help="Actual results JSON")
    
    args = parser.parse_args()
    
    if args.command == "trace":
        if args.depth == 0:
            result = trace_address(args.address)
        else:
            results = trace_address_with_depth(args.address, max_depth=args.depth)
            result = results  # Return list for depth > 0
        
        output_str = json.dumps(result, indent=2)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output_str)
            print(f"Saved to {args.output}")
        else:
            print(output_str)
    
    elif args.command == "batch":
        with open(args.addresses_file, 'r') as f:
            addresses = json.load(f)
        
        results = batch_trace(addresses, max_workers=args.workers)
        
        output_file = os.path.join(args.output_dir, "batch_trace_results.json")
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Saved {len(results)} traces to {output_file}")
    
    elif args.command == "validate":
        with open(args.expected, 'r') as f:
            expected = json.load(f)
        with open(args.actual, 'r') as f:
            actual = json.load(f)
        
        # Compare key metrics
        print("Validation results:")
        print(f"Expected addresses: {len(expected)}")
        print(f"Actual addresses: {len(actual)}")
        
        mismatches = []
        for addr in expected:
            if addr not in actual:
                mismatches.append(f"Missing: {addr}")
            elif expected[addr].get("stats") != actual[addr].get("stats"):
                mismatches.append(f"Stats differ: {addr}")
        
        if mismatches:
            print("Mismatches found:")
            for m in mismatches[:10]:
                print(f"  {m}")
        else:
            print("All matched!")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
