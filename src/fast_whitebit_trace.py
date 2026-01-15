#!/usr/bin/env python3
"""Fast WhiteBIT identification - check if destinations swept to WhiteBIT hot wallet"""
import requests
import json
import time

API_KEY = os.environ.get("ETHERSCAN_API_KEY", "")
BASE_URL = "https://api.etherscan.io/v2/api"
CHAIN_ID = 1

WHITEBIT_HOT = "0x559e1ce9855e2bed54004f67865eb41432d74e5b".lower()
USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
P2P_DISTRIBUTOR = "0xae1e8796052db5f4a975a006800ae33a20845078"

def get_token_transfers(address):
    params = {
        "chainid": CHAIN_ID,
        "module": "account", 
        "action": "tokentx",
        "address": address,
        "contractaddress": USDT,
        "apikey": API_KEY,
        "sort": "asc"
    }
    r = requests.get(BASE_URL, params=params, timeout=10)
    data = r.json()
    if data.get("status") == "1":
        return data.get("result", [])
    return []

# Get P2P distributor outflows
print("Getting P2P distributor outflows...")
txs = get_token_transfers(P2P_DISTRIBUTOR)
outflows = [tx for tx in txs if tx["from"].lower() == P2P_DISTRIBUTOR.lower()]
print(f"Found {len(outflows)} outflows from P2P distributor")

# Group by destination
destinations = {}
for tx in outflows:
    dest = tx["to"]
    if dest not in destinations:
        destinations[dest] = []
    destinations[dest].append({
        "tx_hash": tx["hash"],
        "amount_usdt": int(tx["value"]) / 1e6,
        "timestamp": int(tx["timeStamp"]),
        "block": int(tx["blockNumber"])
    })

print(f"Unique destinations: {len(destinations)}")

# Check each destination - does it sweep to WhiteBIT?
whitebit_deposits = []
other_deposits = []
dormant = []

for i, (addr, funding_txs) in enumerate(destinations.items()):
    total_received = sum(t["amount_usdt"] for t in funding_txs)
    
    if i % 10 == 0:
        print(f"Checking {i}/{len(destinations)}... ({addr[:10]}...)")
    
    time.sleep(0.2)
    addr_txs = get_token_transfers(addr)
    
    # Find outflows from this address
    outflows_from_addr = [tx for tx in addr_txs if tx["from"].lower() == addr.lower()]
    
    if not outflows_from_addr:
        dormant.append({
            "address": addr,
            "total_usdt": total_received,
            "funding_txs": funding_txs
        })
        continue
    
    # Check where funds went
    for out_tx in outflows_from_addr:
        dest = out_tx["to"].lower()
        amount = int(out_tx["value"]) / 1e6
        
        tx_record = {
            "from_p2p_address": addr,
            "to": out_tx["to"],
            "amount_usdt": amount,
            "tx_hash": out_tx["hash"],
            "timestamp": int(out_tx["timeStamp"]),
            "block": int(out_tx["blockNumber"])
        }
        
        # Check if destination is WhiteBIT hot wallet or sweeps to it
        if dest == WHITEBIT_HOT:
            tx_record["destination_type"] = "WHITEBIT_HOT_DIRECT"
            whitebit_deposits.append(tx_record)
        else:
            # Check if this deposit address sweeps to WhiteBIT
            time.sleep(0.15)
            dest_txs = get_token_transfers(out_tx["to"])
            sweeps_to_whitebit = any(
                tx["from"].lower() == out_tx["to"].lower() and 
                tx["to"].lower() == WHITEBIT_HOT 
                for tx in dest_txs
            )
            if sweeps_to_whitebit:
                tx_record["destination_type"] = "WHITEBIT_DEPOSIT_ADDRESS"
                tx_record["deposit_address"] = out_tx["to"]
                whitebit_deposits.append(tx_record)
            else:
                tx_record["destination_type"] = "UNKNOWN"
                other_deposits.append(tx_record)

# Summary
print("\n=== RESULTS ===")
print(f"WhiteBIT: {len(whitebit_deposits)} txs, ${sum(t['amount_usdt'] for t in whitebit_deposits):,.2f}")
print(f"Other: {len(other_deposits)} txs")  
print(f"Dormant: {len(dormant)} wallets, ${sum(d['total_usdt'] for d in dormant):,.2f}")

result = {
    "p2p_distributor": P2P_DISTRIBUTOR,
    "whitebit_hot_wallet": WHITEBIT_HOT,
    "summary": {
        "whitebit_tx_count": len(whitebit_deposits),
        "whitebit_total_usdt": sum(t['amount_usdt'] for t in whitebit_deposits),
        "other_tx_count": len(other_deposits),
        "dormant_wallet_count": len(dormant),
        "dormant_total_usdt": sum(d['total_usdt'] for d in dormant)
    },
    "whitebit_deposits": whitebit_deposits,
    "other_deposits": other_deposits,
    "dormant": dormant
}

with open("p2p_whitebit_complete.json", "w") as f:
    json.dump(result, f, indent=2)
print("\nSaved to p2p_whitebit_complete.json")
