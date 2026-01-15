#!/usr/bin/env python3
"""
Network Expander - BFS/DFS traversal of transaction networks.

Expands from known attacker addresses to find:
1. BACKWARDS: Where did attacker funds originally come from?
2. FORWARDS: Where else did connected wallets send funds?
3. KYC TOUCHPOINTS: Any address that deposited to a KYC exchange

Uses Haiku-style approach: no LLM tokens, just API calls and pattern matching.
"""

import os
import sys
import json
import time
import requests
from collections import deque
from typing import Dict, Set, List, Tuple, Optional
from datetime import datetime
import threading

# ============= Load .env file =============
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    if line.startswith('export '):
                        line = line[7:]
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY", "")
RATE_LIMIT = 5  # Etherscan rate limit

# Known exchange hot wallets (labeled by Etherscan or verified)
KNOWN_EXCHANGE_HOT_WALLETS = {
    # Gate.io
    "0x0d0707963952f2fba59dd06f2b425ace40b492fe": "Gate.io Deposit",
    "0x1c4b70a3968436b9a0a9cf5205c787eb81bb558c": "Gate.io Hot Wallet",
    # WhiteBIT
    "0x39f6a6c85d39d5abad8a398310c52e7c374f2ba3": "WhiteBIT Hot Wallet",
    "0x5a52e96bacdabb82fd05763e25335261b270efcb": "WhiteBIT",
    # Bybit
    "0x17fbbd5bf41693e6bd534a1bc7ca412401d7ce6e": "Bybit Deposit",
    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": "Bybit Hot Wallet",
    # Binance
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance 14",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance 8",
    # KuCoin
    "0x83c41363cbee0081dab75cb841fa24f3db46627e": "KuCoin Deposit",
    # Bitget
    "0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23": "Bitget Deposit",
    # Huobi/HTX
    "0x46340b20830761efd32832a74d7169b29feb9758": "Huobi",
    # OKX
    "0x5041ed759dd4afc3a72b8192c143f72f4724081a": "OKX",
    # Crypto.com
    "0x6262998ced04146fa42253a5c0af90ca02dfd2a3": "Crypto.com",
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

def etherscan_request(params: dict) -> dict:
    """Make rate-limited Etherscan API request."""
    _limiter.acquire()
    params["apikey"] = ETHERSCAN_API_KEY
    params["chainid"] = 1  # Mainnet
    
    try:
        resp = requests.get("https://api.etherscan.io/v2/api", params=params, timeout=30)
        data = resp.json()
        if data.get("status") == "1":
            return data.get("result", [])
        return []
    except Exception as e:
        print(f"API error: {e}")
        return []

def get_transactions(address: str, tx_type: str = "normal") -> list:
    """Get all transactions for an address."""
    address = address.lower()
    
    if tx_type == "normal":
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "sort": "asc"
        }
    elif tx_type == "erc20":
        params = {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "sort": "asc"
        }
    else:
        return []
    
    return etherscan_request(params)

def is_exchange_deposit_pattern(address: str, txs: list) -> Tuple[bool, Optional[str]]:
    """
    Determine if address behaves like an exchange deposit address.
    
    Pattern:
    1. Receives funds (1-5 inflows typically)
    2. Immediately sweeps ALL funds to a hot wallet
    3. No other significant activity
    4. The destination is a known exchange hot wallet
    
    Returns: (is_deposit, exchange_name)
    """
    address = address.lower()
    
    if not txs:
        return False, None
    
    # If address is already a known hot wallet
    if address in KNOWN_EXCHANGE_HOT_WALLETS:
        return True, KNOWN_EXCHANGE_HOT_WALLETS[address]
    
    inflows = []
    outflows = []
    
    for tx in txs:
        if tx.get("from", "").lower() == address:
            outflows.append(tx)
        elif tx.get("to", "").lower() == address:
            inflows.append(tx)
    
    # Deposit pattern: few inflows, sweep to one destination
    if len(inflows) < 1 or len(inflows) > 20:
        return False, None
    
    # Check if all/most outflows go to same address (hot wallet)
    if not outflows:
        return False, None
    
    destinations = {}
    for tx in outflows:
        dest = tx.get("to", "").lower()
        destinations[dest] = destinations.get(dest, 0) + 1
    
    if not destinations:
        return False, None
    
    # Primary destination
    primary_dest = max(destinations, key=destinations.get)
    
    # Check if primary destination is known exchange hot wallet
    if primary_dest in KNOWN_EXCHANGE_HOT_WALLETS:
        return True, KNOWN_EXCHANGE_HOT_WALLETS[primary_dest]
    
    return False, None

def analyze_address(address: str) -> dict:
    """
    Full analysis of an address including:
    - Transaction history
    - Exchange deposit detection
    - Connected addresses
    """
    address = address.lower()
    
    # Get both normal and ERC20 transactions
    normal_txs = get_transactions(address, "normal")
    erc20_txs = get_transactions(address, "erc20")
    
    # Check for exchange pattern
    all_txs = normal_txs + erc20_txs
    is_deposit, exchange_name = is_exchange_deposit_pattern(address, all_txs)
    
    # Extract connected addresses
    connected_in = set()  # Addresses that sent TO this address
    connected_out = set()  # Addresses this address sent TO
    
    for tx in normal_txs:
        from_addr = tx.get("from", "").lower()
        to_addr = tx.get("to", "").lower()
        if from_addr and from_addr != address:
            connected_in.add(from_addr)
        if to_addr and to_addr != address:
            connected_out.add(to_addr)
    
    for tx in erc20_txs:
        from_addr = tx.get("from", "").lower()
        to_addr = tx.get("to", "").lower()
        if from_addr and from_addr != address:
            connected_in.add(from_addr)
        if to_addr and to_addr != address:
            connected_out.add(to_addr)
    
    # Compute totals
    eth_in = sum(int(tx.get("value", 0)) / 1e18 for tx in normal_txs if tx.get("to", "").lower() == address)
    eth_out = sum(int(tx.get("value", 0)) / 1e18 for tx in normal_txs if tx.get("from", "").lower() == address)
    
    usdt_in = sum(int(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
                  for tx in erc20_txs 
                  if tx.get("to", "").lower() == address and tx.get("tokenSymbol") == "USDT")
    usdt_out = sum(int(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
                   for tx in erc20_txs 
                   if tx.get("from", "").lower() == address and tx.get("tokenSymbol") == "USDT")
    
    return {
        "address": address,
        "is_exchange_deposit": is_deposit,
        "exchange_name": exchange_name,
        "tx_count": len(normal_txs) + len(erc20_txs),
        "eth_in": eth_in,
        "eth_out": eth_out,
        "usdt_in": usdt_in,
        "usdt_out": usdt_out,
        "connected_in": list(connected_in),
        "connected_out": list(connected_out),
        "first_tx": min((int(tx.get("timeStamp", 0)) for tx in all_txs), default=0),
        "last_tx": max((int(tx.get("timeStamp", 0)) for tx in all_txs), default=0)
    }

def bfs_expand(seed_addresses: List[str], max_depth: int = 2, direction: str = "both") -> dict:
    """
    BFS traversal from seed addresses.
    
    Args:
        seed_addresses: Starting addresses
        max_depth: How many hops to follow
        direction: "in" (backwards), "out" (forwards), or "both"
    
    Returns:
        Dictionary with:
        - all_addresses: Set of all discovered addresses
        - kyc_touchpoints: Addresses that interact with KYC exchanges
        - graph: The connection graph
    """
    visited = set()
    queue = deque()
    graph = {}  # address -> {depth, in, out, analysis}
    kyc_touchpoints = []
    
    # Initialize with seed addresses at depth 0
    for addr in seed_addresses:
        addr = addr.lower()
        queue.append((addr, 0))
        visited.add(addr)
    
    while queue:
        address, depth = queue.popleft()
        
        print(f"[Depth {depth}] Analyzing {address[:10]}...", file=sys.stderr)
        
        analysis = analyze_address(address)
        graph[address] = {
            "depth": depth,
            "analysis": analysis
        }
        
        # Check for KYC touchpoint
        if analysis["is_exchange_deposit"]:
            kyc_touchpoints.append({
                "address": address,
                "exchange": analysis["exchange_name"],
                "depth": depth,
                "usdt_flow": analysis["usdt_in"] + analysis["usdt_out"],
                "eth_flow": analysis["eth_in"] + analysis["eth_out"]
            })
        
        # Stop expanding if at max depth
        if depth >= max_depth:
            continue
        
        # Expand in requested direction
        next_addrs = []
        if direction in ("in", "both"):
            next_addrs.extend(analysis["connected_in"])
        if direction in ("out", "both"):
            next_addrs.extend(analysis["connected_out"])
        
        for next_addr in next_addrs:
            if next_addr not in visited:
                # Skip known exchange hot wallets (they have millions of connections)
                if next_addr in KNOWN_EXCHANGE_HOT_WALLETS:
                    # But DO record the touchpoint
                    kyc_touchpoints.append({
                        "address": address,
                        "exchange": KNOWN_EXCHANGE_HOT_WALLETS[next_addr],
                        "depth": depth,
                        "via": next_addr,
                        "flow_direction": "direct"
                    })
                    continue
                
                visited.add(next_addr)
                queue.append((next_addr, depth + 1))
    
    return {
        "seed_addresses": seed_addresses,
        "max_depth": max_depth,
        "direction": direction,
        "total_addresses_discovered": len(visited),
        "kyc_touchpoints": kyc_touchpoints,
        "graph": graph
    }

def find_kyc_accounts(addresses: List[str], depth: int = 2) -> dict:
    """
    Main function: Given a list of attacker addresses, find all related
    addresses that have KYC exchange exposure.
    
    This casts a wider net than just tracing stolen funds - it finds:
    1. Where attackers got their initial gas money
    2. Other accounts they may have used
    3. Associates who received or sent funds
    """
    print(f"Starting network expansion from {len(addresses)} seed addresses...", file=sys.stderr)
    print(f"Max depth: {depth}, Direction: both", file=sys.stderr)
    
    result = bfs_expand(addresses, max_depth=depth, direction="both")
    
    # Deduplicate and sort KYC touchpoints by value
    seen = set()
    unique_touchpoints = []
    for tp in result["kyc_touchpoints"]:
        key = (tp["address"], tp.get("exchange", ""))
        if key not in seen:
            seen.add(key)
            unique_touchpoints.append(tp)
    
    # Sort by flow value
    unique_touchpoints.sort(
        key=lambda x: x.get("usdt_flow", 0) + x.get("eth_flow", 0) * 3500,
        reverse=True
    )
    
    result["kyc_touchpoints"] = unique_touchpoints
    result["summary"] = {
        "total_addresses": result["total_addresses_discovered"],
        "kyc_accounts_found": len(unique_touchpoints),
        "exchanges_touched": list(set(tp.get("exchange", "unknown") for tp in unique_touchpoints))
    }
    
    return result

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Expand transaction network from seed addresses")
    parser.add_argument("addresses", nargs="+", help="Seed addresses to expand from")
    parser.add_argument("--depth", "-d", type=int, default=2, help="Max hops to follow")
    parser.add_argument("--output", "-o", help="Output file (JSON)")
    
    args = parser.parse_args()
    
    result = find_kyc_accounts(args.addresses, depth=args.depth)
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Results written to {args.output}")
    else:
        print(json.dumps(result, indent=2))
