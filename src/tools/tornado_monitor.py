#!/usr/bin/env python3
"""
Tornado Cash Deposit Monitor
Watches for deposits to Tornado Cash pools, which may indicate laundering attempts.
Uses local Erigon RPC.
"""

import json
import sys
from datetime import datetime, timezone

# Tornado Cash pool addresses on Ethereum mainnet
TORNADO_POOLS = {
    # ETH pools
    "REDACTED_API_KEY": {"name": "TC 0.1 ETH", "amount": 0.1},
    "REDACTED_API_KEY": {"name": "TC 1 ETH", "amount": 1},
    "REDACTED_API_KEY": {"name": "TC 10 ETH", "amount": 10},
    "REDACTED_API_KEY": {"name": "TC 100 ETH", "amount": 100},
    # DAI pools
    "REDACTED_API_KEY": {"name": "TC 100 DAI", "amount": 100},
    "REDACTED_API_KEY": {"name": "TC 1000 DAI", "amount": 1000},
    "REDACTED_API_KEY": {"name": "TC 10000 DAI", "amount": 10000},
    "REDACTED_API_KEY": {"name": "TC 100000 DAI", "amount": 100000},
    # cDAI pools
    "REDACTED_API_KEY": {"name": "TC 5000 cDAI", "amount": 5000},
    "REDACTED_API_KEY": {"name": "TC 50000 cDAI", "amount": 50000},
    "REDACTED_API_KEY": {"name": "TC 500000 cDAI", "amount": 500000},
    "REDACTED_API_KEY": {"name": "TC 5000000 cDAI", "amount": 5000000},
    # USDC pools
    "REDACTED_API_KEY": {"name": "TC 100 USDC", "amount": 100},
    "REDACTED_API_KEY": {"name": "TC 1000 USDC", "amount": 1000},
    # USDT pools
    "REDACTED_API_KEY": {"name": "TC 100 USDT", "amount": 100},
    "REDACTED_API_KEY": {"name": "TC 1000 USDT", "amount": 1000},
    # WBTC pools
    "REDACTED_API_KEY": {"name": "TC 0.1 WBTC", "amount": 0.1},
    "REDACTED_API_KEY": {"name": "TC 1 WBTC", "amount": 1},
    "REDACTED_API_KEY": {"name": "TC 10 WBTC", "amount": 10},
}

# Deposit event signature for Tornado Cash
# event Deposit(bytes32 indexed commitment, uint32 leafIndex, uint256 timestamp);
DEPOSIT_EVENT = "0xa945e51eec50ab98c161376f0db4cf2aeba3ec92755fe2fcd388bdbbb80ff196"

def make_rpc_call(method, params=[]):
    """Make RPC call to local Erigon"""
    import subprocess
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    })
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:8545", "-X", "POST",
             "-H", "Content-Type: application/json", "--data", payload],
            capture_output=True, text=True, timeout=30
        )
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}

def get_current_block():
    """Get current block number"""
    result = make_rpc_call("eth_blockNumber")
    if "result" in result:
        return int(result["result"], 16)
    return None

def get_logs(from_block, to_block, addresses, topics):
    """Get logs from specified block range"""
    result = make_rpc_call("eth_getLogs", [{
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block),
        "address": addresses,
        "topics": topics
    }])
    return result.get("result", [])

def scan_tornado_deposits(blocks_back=1000):
    """Scan recent blocks for Tornado Cash deposits"""
    current_block = get_current_block()
    if not current_block:
        print("Error: Could not get current block")
        return []
    
    from_block = current_block - blocks_back
    to_block = current_block
    
    print(f"Scanning blocks {from_block} to {to_block} for Tornado Cash deposits...")
    
    # Get all Tornado pool addresses
    pool_addresses = list(TORNADO_POOLS.keys())
    
    # Get deposit events
    logs = get_logs(from_block, to_block, pool_addresses, [DEPOSIT_EVENT])
    
    deposits = []
    for log in logs:
        pool_addr = log.get("address", "").lower()
        pool_info = None
        for addr, info in TORNADO_POOLS.items():
            if addr.lower() == pool_addr:
                pool_info = info
                break
        
        block_num = int(log.get("blockNumber", "0x0"), 16)
        tx_hash = log.get("transactionHash", "")
        
        deposits.append({
            "block": block_num,
            "tx_hash": tx_hash,
            "pool": pool_info.get("name", "Unknown") if pool_info else "Unknown",
            "amount": pool_info.get("amount", 0) if pool_info else 0,
            "pool_address": pool_addr
        })
    
    return deposits

def analyze_deposits(deposits):
    """Analyze deposit patterns"""
    if not deposits:
        print("No deposits found in range")
        return
    
    print(f"\n=== Found {len(deposits)} Tornado Cash Deposits ===\n")
    
    # Group by pool
    by_pool = {}
    for d in deposits:
        pool = d["pool"]
        if pool not in by_pool:
            by_pool[pool] = []
        by_pool[pool].append(d)
    
    for pool, pool_deposits in sorted(by_pool.items(), key=lambda x: -len(x[1])):
        print(f"{pool}: {len(pool_deposits)} deposits")
        # Show last 3
        for d in pool_deposits[-3:]:
            print(f"  Block {d['block']}: {d['tx_hash'][:20]}...")
    
    # Look for suspicious patterns (many deposits in short time)
    print("\n=== Pattern Analysis ===")
    
    # Check for rapid-fire deposits (same pool, close blocks)
    for pool, pool_deposits in by_pool.items():
        if len(pool_deposits) >= 3:
            blocks = sorted([d["block"] for d in pool_deposits])
            for i in range(len(blocks) - 2):
                if blocks[i+2] - blocks[i] < 50:  # 3+ deposits within 50 blocks
                    print(f"ALERT: Rapid deposits to {pool} - blocks {blocks[i]} to {blocks[i+2]}")

def main():
    print("Tornado Cash Deposit Monitor")
    print("=" * 40)
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    
    # Default scan last 1000 blocks (~3.5 hours)
    blocks_back = 1000
    if len(sys.argv) > 1:
        try:
            blocks_back = int(sys.argv[1])
        except:
            pass
    
    deposits = scan_tornado_deposits(blocks_back)
    analyze_deposits(deposits)
    
    # Save results
    output = {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "blocks_scanned": blocks_back,
        "deposits_found": len(deposits),
        "deposits": deposits[-50:] if deposits else []  # Last 50
    }
    
    with open("tornado_deposits.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to tornado_deposits.json")

if __name__ == "__main__":
    main()
