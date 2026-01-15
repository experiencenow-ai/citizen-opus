#!/usr/bin/env python3
"""
Multi-Hop Tracer V2 - Uses Blockscout API for reliable transaction history
Opus Wake 1010

Given a starting address, traces where funds went through N hops.
"""

import json
import urllib.request
import sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone
import argparse
import time

OUTPUT_DIR = Path(__file__).parent / "traces"
OUTPUT_DIR.mkdir(exist_ok=True)

# Known labels for addresses (lowercase for comparison)
KNOWN_ADDRESSES = {
    # Exchanges
    "REDACTED_API_KEY0": "Binance Hot Wallet",
    "REDACTED_API_KEY9": "Binance",
    "REDACTED_API_KEY3d": "Binance",
    "REDACTED_API_KEY7f": "Binance",
    "REDACTED_API_KEY8": "Bybit",
    "REDACTED_API_KEY0": "Bybit",
    # Mixers
    "REDACTED_API_KEY7": "Tornado Cash",
    "REDACTED_API_KEY": "Tornado Cash 100 ETH",
    # DEXs
    "REDACTED_API_KEY": "Uniswap V2 Router",
    "REDACTED_API_KEY": "Uniswap V3 Router",
    "REDACTED_API_KEY": "1inch Router",
}

def get_canonical_address(addr):
    """Get the canonical checksummed address from Blockscout."""
    url = f'https://eth.blockscout.com/api/v2/addresses/{addr}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get('hash', addr)  # Returns properly checksummed address
    except:
        return addr

def get_outgoing_transactions(addr, limit=100):
    """Get outgoing transactions for an address using Blockscout API."""
    # First get canonical address
    canonical = get_canonical_address(addr)
    url = f'https://eth.blockscout.com/api/v2/addresses/{canonical}/transactions?filter=from&limit={limit}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get('items', [])
    except Exception as e:
        print(f"API Error for {addr}: {e}")
        return []

def get_address_info(addr):
    """Get address metadata from Blockscout."""
    canonical = get_canonical_address(addr)
    url = f'https://eth.blockscout.com/api/v2/addresses/{canonical}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except:
        return {}

def trace_hops(start_addr, depth=3, min_eth=0.1, verbose=True):
    """Trace funds from start_addr through N hops."""
    start_addr_lower = start_addr.lower()
    
    graph = {
        'start': start_addr,
        'depth': depth,
        'min_eth': min_eth,
        'traced_at': datetime.now(timezone.utc).isoformat(),
        'nodes': {},  # addr -> {balance, txs, label}
        'edges': [],  # [{from, to, eth, tx_hash}]
        'endpoints': [],  # Exchanges, mixers, etc.
        'totals': {
            'addresses_traced': 0,
            'total_eth_tracked': 0,
            'eth_to_exchanges': 0,
            'eth_to_mixers': 0,
            'eth_to_unknown': 0
        }
    }
    
    visited = set()
    queue = [(start_addr, 0, [start_addr])]  # (addr, depth, path)
    
    while queue:
        current_addr, current_depth, path = queue.pop(0)
        current_addr_lower = current_addr.lower()
        
        if current_addr_lower in visited or current_depth >= depth:
            continue
        visited.add(current_addr_lower)
        graph['totals']['addresses_traced'] += 1
        
        if verbose:
            print(f"\n[Hop {current_depth}] {current_addr[:15]}... (path len: {len(path)})")
        
        # Get outgoing transactions
        txs = get_outgoing_transactions(current_addr)
        time.sleep(0.3)  # Rate limiting
        
        # Filter by minimum ETH
        outgoing = []
        for tx in txs:
            value = int(tx.get('value', '0')) / 1e18
            if value >= min_eth:
                to_info = tx.get('to')
                if to_info:
                    to_addr = to_info.get('hash', '')
                    outgoing.append({
                        'to': to_addr,
                        'eth': value,
                        'hash': tx.get('hash', ''),
                        'timestamp': tx.get('timestamp', '')
                    })
        
        if verbose:
            print(f"  Found {len(txs)} outgoing txs, {len(outgoing)} >= {min_eth} ETH")
        
        for tx_info in outgoing:
            to_addr = tx_info['to']
            to_addr_lower = to_addr.lower()
            value = tx_info['eth']
            
            graph['totals']['total_eth_tracked'] += value
            graph['edges'].append({
                'from': current_addr,
                'to': to_addr,
                'eth': value,
                'hash': tx_info['hash']
            })
            
            # Check if known address
            label = KNOWN_ADDRESSES.get(to_addr_lower)
            
            if label:
                if 'Tornado' in label:
                    graph['totals']['eth_to_mixers'] += value
                    graph['endpoints'].append({
                        'address': to_addr,
                        'label': label,
                        'type': 'mixer',
                        'eth': value,
                        'path': path + [to_addr]
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
                        'path': path + [to_addr]
                    })
                    if verbose:
                        print(f"  💰 {value:.2f} ETH -> {label}")
                else:
                    if verbose:
                        print(f"  📊 {value:.2f} ETH -> {label}")
            else:
                graph['totals']['eth_to_unknown'] += value
                if to_addr_lower not in visited and current_depth + 1 < depth:
                    queue.append((to_addr, current_depth + 1, path + [to_addr]))
                if verbose:
                    print(f"  → {value:.2f} ETH -> {to_addr[:15]}...")
        
        # Store node info
        graph['nodes'][current_addr_lower] = {
            'tx_count': len(txs),
            'outgoing_tracked': len(outgoing),
            'label': KNOWN_ADDRESSES.get(current_addr_lower)
        }
    
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
    
    if graph['edges']:
        print(f"\nLargest transfers:")
        for edge in sorted(graph['edges'], key=lambda x: -x['eth'])[:10]:
            print(f"  {edge['from'][:12]}... -> {edge['to'][:12]}... : {edge['eth']:.2f} ETH")

def main():
    parser = argparse.ArgumentParser(description='Multi-hop transaction tracer (Blockscout)')
    parser.add_argument('address', help='Starting address to trace')
    parser.add_argument('--depth', type=int, default=3, help='Number of hops to follow')
    parser.add_argument('--min-eth', type=float, default=0.1, help='Minimum ETH to track')
    parser.add_argument('--output', help='Output file (default: traces/<address>.json)')
    parser.add_argument('--quiet', action='store_true', help='Less verbose output')
    
    args = parser.parse_args()
    
    print(f"Multi-Hop Tracer V2 - Opus Wake 1010")
    print(f"Starting trace from: {args.address}")
    print(f"Using Blockscout API")
    
    graph = trace_hops(
        args.address,
        depth=args.depth,
        min_eth=args.min_eth,
        verbose=not args.quiet
    )
    
    print_summary(graph)
    
    # Save results
    output_file = args.output or OUTPUT_DIR / f"{args.address[:10].lower()}.json"
    with open(output_file, 'w') as f:
        json.dump(graph, f, indent=2)
    print(f"\nResults saved to: {output_file}")

if __name__ == "__main__":
    main()
