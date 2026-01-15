#!/usr/bin/env python3
"""
Multi-Hop Tracer - Automatically trace funds through multiple hops
Opus Wake 1009

Given a starting address, traces where funds went through N hops.
Builds a transaction graph and identifies endpoints (exchanges, mixers, etc.).

Usage:
  python3 multi_hop_tracer.py <address> [--depth N] [--min-eth M]
"""

import json
import urllib.request
import sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime
import argparse

RPC_URL = "http://localhost:8545"
OUTPUT_DIR = Path(__file__).parent / "traces"
OUTPUT_DIR.mkdir(exist_ok=True)

# Known labels for addresses
KNOWN_ADDRESSES = {
    # Exchanges
    "REDACTED_API_KEY0": "Binance Hot Wallet",
    "REDACTED_API_KEY9": "Binance",
    "REDACTED_API_KEY3d": "Binance",
    "REDACTED_API_KEY7f": "Binance",
    "REDACTED_API_KEY6": "Binance US",
    "REDACTED_API_KEY6f": "Coinbase",
    "REDACTED_API_KEY3": "Coinbase",
    "REDACTED_API_KEY3": "Coinbase",
    "REDACTED_API_KEY3da": "Coinbase",
    "REDACTED_API_KEY0": "Coinbase",
    "REDACTED_API_KEY9": "Coinbase",
    "REDACTED_API_KEY1": "Coinbase",
    "REDACTED_API_KEY4cf": "Coinbase",
    "REDACTED_API_KEY7c": "Kraken",
    "REDACTED_API_KEY7b": "OKX",
    "REDACTED_API_KEY8": "OKX",
    "REDACTED_API_KEY7b": "OKX",
    "REDACTED_API_KEY8": "Bybit",
    "REDACTED_API_KEY0": "Bybit",
    # Mixers
    "REDACTED_API_KEY7": "Tornado Cash",
    "REDACTED_API_KEY": "Tornado Cash 100 ETH",
    "REDACTED_API_KEY9dbf": "Tornado Cash (Governance)",
    # DEXs
    "REDACTED_API_KEY": "Uniswap V2 Router",
    "REDACTED_API_KEY": "Uniswap V3 Router",
    "REDACTED_API_KEY": "Uniswap V3 Router",
    "REDACTED_API_KEY9f": "SushiSwap Router",
    "REDACTED_API_KEY": "1inch Router",
}

def rpc_call(method, params=None):
    payload = json.dumps({'jsonrpc': '2.0', 'method': method, 'params': params or [], 'id': 1}).encode()
    req = urllib.request.Request(RPC_URL, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            if 'error' in result:
                return None
            return result.get('result')
    except Exception as e:
        print(f"RPC Error: {e}")
        return None

def hex_to_int(h):
    return int(h, 16) if h else 0

def wei_to_eth(w):
    return w / 1e18

def get_label(address):
    """Get known label for address."""
    return KNOWN_ADDRESSES.get(address.lower(), None)

def get_balance(address):
    """Get current ETH balance."""
    result = rpc_call('eth_getBalance', [address, 'latest'])
    return wei_to_eth(hex_to_int(result)) if result else 0

def get_outgoing_transfers(address, num_blocks=100000):
    """Get outgoing ETH transfers from an address."""
    address = address.lower()
    current_block = hex_to_int(rpc_call('eth_blockNumber'))
    from_blk = max(0, current_block - num_blocks)
    
    traces = rpc_call('trace_filter', [{
        'fromAddress': [address],
        'fromBlock': hex(from_blk),
        'toBlock': hex(current_block)
    }]) or []
    
    transfers = []
    for trace in traces:
        action = trace.get('action', {})
        to_addr = (action.get('to') or '').lower()
        value = wei_to_eth(hex_to_int(action.get('value', '0x0')))
        
        if value > 0 and to_addr:
            transfers.append({
                'to': to_addr,
                'value_eth': value,
                'block': trace.get('blockNumber', 0),
                'tx_hash': trace.get('transactionHash', ''),
                'label': get_label(to_addr)
            })
    
    return transfers

def trace_hops(start_address, depth=3, min_eth=0.1, verbose=True):
    """
    Trace funds through multiple hops.
    Returns a dict with the full graph.
    """
    graph = {
        'start': start_address.lower(),
        'timestamp': datetime.now().isoformat(),
        'depth': depth,
        'min_eth': min_eth,
        'hops': {},
        'endpoints': [],  # Addresses where funds stopped (exchange, empty, etc.)
        'totals': {
            'addresses_traced': 0,
            'total_eth_tracked': 0,
            'eth_to_exchanges': 0,
            'eth_to_mixers': 0,
            'eth_to_unknown': 0
        }
    }
    
    # Queue: (address, current_depth, path)
    queue = [(start_address.lower(), 0, [start_address.lower()])]
    visited = set()
    
    while queue:
        address, current_depth, path = queue.pop(0)
        
        if address in visited:
            continue
        visited.add(address)
        
        if current_depth >= depth:
            continue
        
        if verbose:
            print(f"\n[Hop {current_depth}] {address[:15]}... (path len: {len(path)})")
        
        transfers = get_outgoing_transfers(address, num_blocks=200000)
        
        # Filter by min_eth
        significant = [t for t in transfers if t['value_eth'] >= min_eth]
        
        if verbose:
            print(f"  Found {len(transfers)} transfers, {len(significant)} >= {min_eth} ETH")
        
        graph['hops'][address] = {
            'depth': current_depth,
            'path': path,
            'transfers': significant,
            'balance': get_balance(address)
        }
        graph['totals']['addresses_traced'] += 1
        
        for t in significant:
            to_addr = t['to']
            value = t['value_eth']
            label = t['label']
            
            graph['totals']['total_eth_tracked'] += value
            
            if label:
                if 'Tornado' in label:
                    graph['totals']['eth_to_mixers'] += value
                    graph['endpoints'].append({
                        'address': to_addr,
                        'label': label,
                        'type': 'mixer',
                        'eth': value,
                        'from_path': path + [to_addr]
                    })
                    if verbose:
                        print(f"  ⚠️  {value:.2f} ETH -> {label}")
                elif any(x in label for x in ['Binance', 'Coinbase', 'Kraken', 'OKX', 'Bybit']):
                    graph['totals']['eth_to_exchanges'] += value
                    graph['endpoints'].append({
                        'address': to_addr,
                        'label': label,
                        'type': 'exchange',
                        'eth': value,
                        'from_path': path + [to_addr]
                    })
                    if verbose:
                        print(f"  💰 {value:.2f} ETH -> {label}")
                else:
                    # DEX or other known
                    if verbose:
                        print(f"  📊 {value:.2f} ETH -> {label}")
            else:
                # Unknown address - continue tracing
                graph['totals']['eth_to_unknown'] += value
                if to_addr not in visited:
                    queue.append((to_addr, current_depth + 1, path + [to_addr]))
                if verbose:
                    print(f"  → {value:.2f} ETH -> {to_addr[:15]}...")
    
    return graph

def print_summary(graph):
    """Print a summary of the trace."""
    print("\n" + "="*60)
    print("TRACE SUMMARY")
    print("="*60)
    print(f"Start: {graph['start']}")
    print(f"Depth: {graph['depth']} hops")
    print(f"Min ETH: {graph['min_eth']}")
    print(f"Addresses traced: {graph['totals']['addresses_traced']}")
    print(f"\nETH Flow:")
    print(f"  Total tracked: {graph['totals']['total_eth_tracked']:.2f} ETH")
    print(f"  To exchanges:  {graph['totals']['eth_to_exchanges']:.2f} ETH")
    print(f"  To mixers:     {graph['totals']['eth_to_mixers']:.2f} ETH")
    print(f"  To unknown:    {graph['totals']['eth_to_unknown']:.2f} ETH")
    
    if graph['endpoints']:
        print(f"\nEndpoints ({len(graph['endpoints'])}):")
        for ep in sorted(graph['endpoints'], key=lambda x: -x['eth'])[:10]:
            print(f"  {ep['label'] or ep['address'][:20]}: {ep['eth']:.2f} ETH ({ep['type']})")

def main():
    parser = argparse.ArgumentParser(description='Multi-hop transaction tracer')
    parser.add_argument('address', help='Starting address to trace')
    parser.add_argument('--depth', type=int, default=3, help='Number of hops to follow')
    parser.add_argument('--min-eth', type=float, default=0.1, help='Minimum ETH to track')
    parser.add_argument('--output', help='Output file (default: traces/<address>.json)')
    parser.add_argument('--quiet', action='store_true', help='Less verbose output')
    
    args = parser.parse_args()
    
    print(f"Multi-Hop Tracer - Opus Wake 1009")
    print(f"Starting trace from: {args.address}")
    
    graph = trace_hops(
        args.address,
        depth=args.depth,
        min_eth=args.min_eth,
        verbose=not args.quiet
    )
    
    print_summary(graph)
    
    # Save results
    output_file = args.output or OUTPUT_DIR / f"{args.address[:10]}.json"
    with open(output_file, 'w') as f:
        json.dump(graph, f, indent=2)
    print(f"\nResults saved to: {output_file}")

if __name__ == "__main__":
    main()
