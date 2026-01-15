#!/usr/bin/env python3
"""
Transaction Tracer - Follow funds through the blockchain
Opus Wake 1006

Given an address, traces where funds came from and went to.
Builds a transaction graph for analysis.

Usage:
  python3 transaction_tracer.py <address> [--depth N] [--output FILE]
"""

import json
import urllib.request
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from collections import defaultdict

# ============================================================================
# Configuration
# ============================================================================

RPC_URL = "http://localhost:8545"
ETHERSCAN_API = "https://api.etherscan.io/v2/api"
ETHERSCAN_KEY = ""  # Add if available for faster queries

OUTPUT_DIR = Path(__file__).parent / "traces"
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_TRANSACTIONS = 100  # Per address
MAX_DEPTH = 3  # How many hops to follow

# ============================================================================
# Data Types
# ============================================================================

@dataclass
class Transaction:
    """Ethereum transaction."""
    hash: str
    block: int
    timestamp: str
    from_addr: str
    to_addr: str
    value_eth: float
    gas_used: int
    input_data: str
    
    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class AddressProfile:
    """Profile of an address."""
    address: str
    balance_eth: float
    tx_count: int
    first_seen: Optional[str]
    last_seen: Optional[str]
    total_received: float
    total_sent: float
    unique_senders: int
    unique_receivers: int
    is_contract: bool
    label: Optional[str]
    
    def to_dict(self) -> Dict:
        return asdict(self)

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
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            if "error" in result:
                print(f"RPC Error: {result['error']}")
                return None
            return result.get("result")
    except Exception as e:
        print(f"RPC Exception: {e}")
        return None

def hex_to_int(hex_str: str) -> int:
    if not hex_str:
        return 0
    return int(hex_str, 16)

def wei_to_eth(wei: int) -> float:
    return wei / 1e18

# ============================================================================
# Address Analysis
# ============================================================================

def get_balance(address: str) -> float:
    """Get ETH balance."""
    result = rpc_call("eth_getBalance", [address, "latest"])
    return wei_to_eth(hex_to_int(result)) if result else 0

def get_tx_count(address: str) -> int:
    """Get transaction count."""
    result = rpc_call("eth_getTransactionCount", [address, "latest"])
    return hex_to_int(result) if result else 0

def get_code(address: str) -> str:
    """Get contract code (empty string if EOA)."""
    result = rpc_call("eth_getCode", [address, "latest"])
    return result if result and result != "0x" else ""

def is_contract(address: str) -> bool:
    """Check if address is a contract."""
    return len(get_code(address)) > 0

def get_block(block_num: int) -> Dict:
    """Get block with transactions."""
    result = rpc_call("eth_getBlockByNumber", [hex(block_num), True])
    return result if result else {}

def get_transaction_receipt(tx_hash: str) -> Dict:
    """Get transaction receipt."""
    result = rpc_call("eth_getTransactionReceipt", [tx_hash])
    return result if result else {}

# ============================================================================
# Transaction Fetching via trace_filter (Erigon-specific)
# ============================================================================

def get_transactions_for_address(address: str, from_block: int = 0, to_block: str = "latest") -> List[Dict]:
    """
    Get all transactions involving an address using trace_filter.
    This is Erigon/OpenEthereum specific.
    """
    address = address.lower()
    
    # Get outgoing transactions
    outgoing = rpc_call("trace_filter", [{
        "fromAddress": [address],
        "fromBlock": hex(from_block),
        "toBlock": to_block
    }])
    
    # Get incoming transactions
    incoming = rpc_call("trace_filter", [{
        "toAddress": [address],
        "fromBlock": hex(from_block),
        "toBlock": to_block
    }])
    
    all_txs = []
    seen_hashes = set()
    
    for tx_list in [outgoing or [], incoming or []]:
        for trace in tx_list:
            tx_hash = trace.get("transactionHash")
            if tx_hash and tx_hash not in seen_hashes:
                seen_hashes.add(tx_hash)
                action = trace.get("action", {})
                all_txs.append({
                    "hash": tx_hash,
                    "block": hex_to_int(trace.get("blockNumber", "0x0")),
                    "from": action.get("from", "").lower(),
                    "to": action.get("to", "").lower(),
                    "value": wei_to_eth(hex_to_int(action.get("value", "0x0"))),
                    "type": trace.get("type", "call")
                })
    
    return sorted(all_txs, key=lambda x: x["block"])

# ============================================================================
# Graph Building
# ============================================================================

def trace_address(address: str, depth: int = 2, max_txs: int = 100) -> Dict:
    """
    Build a transaction graph starting from an address.
    
    Returns:
        {
            "root": address,
            "addresses": {addr: profile},
            "edges": [(from, to, value, tx_hash)],
            "depth": depth
        }
    """
    address = address.lower()
    
    graph = {
        "root": address,
        "generated": datetime.now(timezone.utc).isoformat(),
        "addresses": {},
        "edges": [],
        "depth": depth
    }
    
    to_process = [(address, 0)]  # (address, current_depth)
    processed = set()
    
    while to_process:
        current_addr, current_depth = to_process.pop(0)
        
        if current_addr in processed:
            continue
        processed.add(current_addr)
        
        print(f"Processing {current_addr[:10]}... (depth {current_depth})")
        
        # Get address profile
        profile = AddressProfile(
            address=current_addr,
            balance_eth=get_balance(current_addr),
            tx_count=get_tx_count(current_addr),
            first_seen=None,
            last_seen=None,
            total_received=0,
            total_sent=0,
            unique_senders=0,
            unique_receivers=0,
            is_contract=is_contract(current_addr),
            label=None
        )
        
        # Get transactions
        txs = get_transactions_for_address(current_addr)[:max_txs]
        
        senders = set()
        receivers = set()
        
        for tx in txs:
            from_addr = tx["from"]
            to_addr = tx["to"]
            value = tx["value"]
            
            # Add edge
            graph["edges"].append({
                "from": from_addr,
                "to": to_addr,
                "value_eth": value,
                "hash": tx["hash"],
                "block": tx["block"]
            })
            
            # Track flows
            if from_addr == current_addr:
                profile.total_sent += value
                receivers.add(to_addr)
                if current_depth < depth and to_addr and to_addr not in processed:
                    to_process.append((to_addr, current_depth + 1))
            else:
                profile.total_received += value
                senders.add(from_addr)
                if current_depth < depth and from_addr and from_addr not in processed:
                    to_process.append((from_addr, current_depth + 1))
        
        profile.unique_senders = len(senders)
        profile.unique_receivers = len(receivers)
        
        if txs:
            profile.first_seen = f"block {txs[0]['block']}"
            profile.last_seen = f"block {txs[-1]['block']}"
        
        graph["addresses"][current_addr] = profile.to_dict()
    
    return graph

# ============================================================================
# Analysis Functions
# ============================================================================

def find_large_transfers(graph: Dict, min_eth: float = 1.0) -> List[Dict]:
    """Find transfers above threshold."""
    return [e for e in graph["edges"] if e["value_eth"] >= min_eth]

def find_mixer_interactions(graph: Dict) -> List[Dict]:
    """Find interactions with known mixers."""
    KNOWN_MIXERS = [
        "REDACTED_API_KEY1b",  # Tornado Cash
        "REDACTED_API_KEY7",  # Tornado Cash old
    ]
    
    mixer_txs = []
    for edge in graph["edges"]:
        if edge["from"].lower() in KNOWN_MIXERS or edge["to"].lower() in KNOWN_MIXERS:
            mixer_txs.append(edge)
    return mixer_txs

def summarize_graph(graph: Dict) -> Dict:
    """Generate summary statistics."""
    total_volume = sum(e["value_eth"] for e in graph["edges"])
    
    # Find top receivers
    received = defaultdict(float)
    for edge in graph["edges"]:
        received[edge["to"]] += edge["value_eth"]
    
    top_receivers = sorted(received.items(), key=lambda x: -x[1])[:10]
    
    return {
        "root_address": graph["root"],
        "addresses_analyzed": len(graph["addresses"]),
        "total_transactions": len(graph["edges"]),
        "total_volume_eth": round(total_volume, 4),
        "top_receivers": [{"address": a, "received_eth": round(v, 4)} for a, v in top_receivers],
        "mixer_interactions": len(find_mixer_interactions(graph)),
        "large_transfers": len(find_large_transfers(graph, 10.0))
    }

# ============================================================================
# Main
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Trace transactions for an address")
    parser.add_argument("address", help="Ethereum address to trace")
    parser.add_argument("--depth", type=int, default=2, help="Trace depth (default: 2)")
    parser.add_argument("--output", help="Output file (default: traces/<address>.json)")
    
    args = parser.parse_args()
    
    address = args.address.lower()
    if not address.startswith("0x"):
        address = "0x" + address
    
    print(f"Tracing {address} to depth {args.depth}...")
    
    graph = trace_address(address, depth=args.depth)
    summary = summarize_graph(graph)
    
    output = {
        "summary": summary,
        "graph": graph
    }
    
    output_file = args.output or (OUTPUT_DIR / f"{address[:10]}.json")
    Path(output_file).write_text(json.dumps(output, indent=2))
    
    print(f"\nSummary:")
    print(f"  Addresses analyzed: {summary['addresses_analyzed']}")
    print(f"  Total transactions: {summary['total_transactions']}")
    print(f"  Total volume: {summary['total_volume_eth']} ETH")
    print(f"  Mixer interactions: {summary['mixer_interactions']}")
    print(f"\nFull trace saved to: {output_file}")

if __name__ == "__main__":
    main()
