#!/usr/bin/env python3
"""
THORChain Router Monitor v2
Watches for deposits to THORChain Router from suspicious/new addresses.
Lazarus pattern: Fresh wallets -> 1-2 hops -> THORChain Router

Now distinguishes:
- Legitimate users: funded BY THORChain (swap in, then swap out)
- Suspicious: funded by OTHER sources, then send to THORChain

Usage:
    python3 thorchain_monitor.py --check      # One-time check
    python3 thorchain_monitor.py --daemon     # Continuous monitoring
"""

import json
import urllib.request
import urllib.error
import time
import sys
from datetime import datetime

# THORChain Router on Ethereum
THORCHAIN_ROUTER = "REDACTED_API_KEYD7146".lower()
ERIGON_RPC = "http://localhost:8545"
BLOCKSCOUT_API = "https://eth.blockscout.com/api/v2"

# Known suspicious addresses (from bounty watchlist)
KNOWN_SUSPICIOUS = {
    "REDACTED_API_KEY2": "Bybit primary",
    "REDACTED_API_KEY": "Bybit dispersal 1",
    "REDACTED_API_KEY": "Bybit dispersal 2",
    "REDACTED_API_KEY": "Bybit dispersal 3",
    "REDACTED_API_KEY": "Bybit dispersal 4",
    "REDACTED_API_KEY": "Bybit dispersal 5",
}

def http_get(url, timeout=30):
    """GET request using urllib"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return None

def http_post(url, data, timeout=30):
    """POST request using urllib"""
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return None

def get_router_transactions_blockscout(limit=50):
    """Fetch recent transactions to THORChain Router via Blockscout"""
    url = f"{BLOCKSCOUT_API}/addresses/{THORCHAIN_ROUTER}/transactions?filter=to"
    data = http_get(url)
    return data.get("items", []) if data else []

def check_funding_source(address):
    """Check where this address got its funds from"""
    address = address.lower()
    
    # Get internal transactions (shows contract calls that sent ETH)
    url = f"{BLOCKSCOUT_API}/addresses/{address}/internal-transactions"
    data = http_get(url, timeout=15)
    
    if data and "items" in data:
        for tx in data["items"][:20]:
            from_addr = tx.get("from", {}).get("hash", "").lower()
            to_addr = tx.get("to", {})
            to_addr = to_addr.get("hash", "").lower() if isinstance(to_addr, dict) else ""
            value = int(tx.get("value", "0")) / 1e18
            
            # If this address received ETH from THORChain Router, it's a legit user
            if to_addr == address and from_addr == THORCHAIN_ROUTER and value > 0.01:
                return {
                    "source": "thorchain",
                    "amount": value,
                    "legitimate": True
                }
    
    # Check regular transactions
    url = f"{BLOCKSCOUT_API}/addresses/{address}/transactions"
    data = http_get(url, timeout=15)
    
    if data and "items" in data:
        for tx in data["items"][:20]:
            to_addr = tx.get("to", {})
            to_addr = to_addr.get("hash", "").lower() if isinstance(to_addr, dict) else ""
            value = int(tx.get("value", "0")) / 1e18
            
            # If receiving large amounts, note the source
            if to_addr == address and value > 0.1:
                from_addr = tx.get("from", {}).get("hash", "unknown")
                return {
                    "source": from_addr,
                    "amount": value,
                    "legitimate": False  # Not from THORChain
                }
    
    return {"source": "unknown", "legitimate": False}

def analyze_sender(address):
    """Check if sender is suspicious"""
    address = address.lower()
    
    # Check known suspicious
    if address in KNOWN_SUSPICIOUS:
        return {
            "suspicious": True,
            "reason": f"Known: {KNOWN_SUSPICIOUS[address]}",
            "confidence": "HIGH"
        }
    
    # Check funding source
    funding = check_funding_source(address)
    if funding.get("legitimate"):
        return {
            "suspicious": False,
            "reason": f"Funded by THORChain ({funding['amount']:.2f} ETH) - legitimate swap user"
        }
    
    # Check wallet age/tx count via Blockscout
    url = f"{BLOCKSCOUT_API}/addresses/{address}"
    data = http_get(url, timeout=10)
    
    if data:
        tx_count = data.get("transactions_count", 0)
        
        # New wallet with few txs, NOT funded by THORChain = suspicious
        if tx_count < 10 and not funding.get("legitimate"):
            return {
                "suspicious": True,
                "reason": f"New wallet ({tx_count} txs), funded by {funding.get('source', 'unknown')[:20]}...",
                "confidence": "MEDIUM",
                "funding_source": funding.get("source")
            }
        
        return {
            "suspicious": False,
            "tx_count": tx_count
        }
    
    return {"suspicious": False, "reason": "Could not analyze"}

def check_router():
    """Check recent transactions to THORChain Router"""
    print(f"\n{'='*60}")
    print(f"THORChain Router Monitor v2 - {datetime.now().isoformat()}")
    print(f"Router: {THORCHAIN_ROUTER}")
    print(f"{'='*60}\n")
    
    txs = get_router_transactions_blockscout(limit=20)
    
    if not txs:
        print("No transactions found or API error")
        return []
    
    suspicious = []
    
    for tx in txs:
        from_info = tx.get("from", {})
        sender = from_info.get("hash", "unknown") if isinstance(from_info, dict) else str(from_info)
        value_wei = int(tx.get("value", "0"))
        value_eth = value_wei / 1e18
        tx_hash = tx.get("hash", "unknown")
        timestamp = tx.get("timestamp", "unknown")
        
        # Only care about significant deposits (> 1 ETH)
        if value_eth < 1:
            continue
        
        analysis = analyze_sender(sender)
        
        status = "⚠️ SUSPICIOUS" if analysis.get("suspicious") else "✓ Normal"
        print(f"{status} | {value_eth:.2f} ETH | {sender[:20]}...")
        print(f"         Tx: {tx_hash[:20]}... | Time: {timestamp}")
        
        if analysis.get("suspicious"):
            print(f"         Reason: {analysis.get('reason')} | Confidence: {analysis.get('confidence')}")
            suspicious.append({
                "tx_hash": tx_hash,
                "sender": sender,
                "value_eth": value_eth,
                "timestamp": timestamp,
                "analysis": analysis
            })
        else:
            print(f"         {analysis.get('reason', 'Established wallet')}")
        print()
    
    return suspicious

def run_daemon(interval=60):
    """Run continuous monitoring"""
    print("Starting THORChain Router daemon...")
    print(f"Checking every {interval} seconds")
    
    seen_txs = set()
    alerts = []
    
    while True:
        try:
            suspicious = check_router()
            for s in suspicious:
                if s["tx_hash"] not in seen_txs:
                    seen_txs.add(s["tx_hash"])
                    alerts.append(s)
                    print(f"\n🚨 NEW ALERT: {s['value_eth']:.2f} ETH from suspicious address!")
                    print(f"   Sender: {s['sender']}")
                    print(f"   Reason: {s['analysis'].get('reason')}")
                    
                    # Save alerts
                    with open("thorchain_alerts.json", "w") as f:
                        json.dump(alerts, f, indent=2)
            
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopping daemon...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(interval)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        run_daemon()
    else:
        # One-time check
        suspicious = check_router()
        if suspicious:
            print(f"\n⚠️ Found {len(suspicious)} suspicious transactions!")
            with open("thorchain_alerts.json", "w") as f:
                json.dump(suspicious, f, indent=2)
            print("Saved to thorchain_alerts.json")
        else:
            print("\n✓ No suspicious transactions in recent deposits")
