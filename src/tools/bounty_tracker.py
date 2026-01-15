#!/usr/bin/env python3
"""
Bounty Tracker - Aggregate crypto theft bounty announcements
Searches for active bounties from hacks, tracks amounts and addresses
"""

import json
import sys
import os
import re
from datetime import datetime

# Known bounties (manually curated + to be updated by searches)
KNOWN_BOUNTIES = {
    "bybit_2025": {
        "exchange": "Bybit",
        "hack_date": "2025-02-21",
        "stolen_amount": "$1.5B",
        "bounty_offered": "$225M (15% of recovered funds)",
        "bounty_type": "percentage",
        "bounty_pct": 15,
        "attacker": "Lazarus Group (North Korea)",
        "status": "active",
        "primary_laundering": "THORChain -> BTC",
        "recovery_probability": "very_low",
        "reason": "Nation-state actor, already laundered via THORChain",
        "source": "Bybit announcement"
    },
    "coindcx_2025": {
        "exchange": "CoinDCX",
        "hack_date": "2025-01-08",
        "stolen_amount": "$44M",
        "bounty_offered": "25% of recovered funds (~$11M max)",
        "bounty_type": "percentage",
        "bounty_pct": 25,
        "attacker": "unknown",
        "status": "active",
        "recovery_probability": "medium",
        "reason": "25% bounty suggests exchange believes recovery possible, likely opportunistic hacker not nation-state",
        "source": "CoinDCX announcement"
    },
    "wazirx_2024": {
        "exchange": "WazirX",
        "hack_date": "2024-07-18",
        "stolen_amount": "$235M",
        "bounty_offered": "$23M (10% of recovered funds)",
        "bounty_type": "percentage",
        "bounty_pct": 10,
        "attacker": "Suspected Lazarus Group",
        "status": "active",
        "recovery_probability": "low",
        "source": "WazirX announcement"
    }
}

def parse_amount(amount_str):
    """Parse amount string like '$44M' or '$1.5B' to numeric value"""
    if not amount_str:
        return 0
    match = re.search(r'\$(\d+(?:\.\d+)?)(M|B|K)?', amount_str)
    if match:
        amount = float(match.group(1))
        multiplier = {"M": 1_000_000, "B": 1_000_000_000, "K": 1_000}.get(match.group(2), 1)
        return amount * multiplier
    return 0

def calculate_expected_value(bounty):
    """Calculate expected value of pursuing a bounty"""
    prob_map = {
        "very_low": 0.01,
        "low": 0.05,
        "medium": 0.15,
        "high": 0.30
    }
    
    # Get bounty value - either from direct $ amount or calculate from percentage
    bounty_str = bounty.get("bounty_offered", "0")
    bounty_value = parse_amount(bounty_str)
    
    # If no direct $ value found, calculate from percentage
    if bounty_value == 0 and "bounty_pct" in bounty:
        stolen = parse_amount(bounty.get("stolen_amount", "0"))
        bounty_value = stolen * (bounty["bounty_pct"] / 100)
    
    prob = prob_map.get(bounty.get("recovery_probability", "low"), 0.05)
    return bounty_value * prob

def rank_bounties():
    """Rank bounties by expected value"""
    ranked = []
    for name, bounty in KNOWN_BOUNTIES.items():
        ev = calculate_expected_value(bounty)
        
        # Also calculate max bounty for reference
        stolen = parse_amount(bounty.get("stolen_amount", "0"))
        max_bounty = stolen * (bounty.get("bounty_pct", 0) / 100)
        
        ranked.append({
            "name": name,
            "exchange": bounty["exchange"],
            "stolen": bounty["stolen_amount"],
            "bounty": bounty["bounty_offered"],
            "max_bounty": max_bounty,
            "probability": bounty["recovery_probability"],
            "expected_value": ev,
            "attacker": bounty.get("attacker", "unknown")
        })
    
    ranked.sort(key=lambda x: x["expected_value"], reverse=True)
    return ranked

def main():
    print("=== Active Crypto Bounties ===")
    print(f"Last updated: {datetime.now().isoformat()}")
    print()
    
    ranked = rank_bounties()
    
    for i, b in enumerate(ranked, 1):
        print(f"{i}. {b['exchange']}")
        print(f"   Stolen: {b['stolen']}")
        print(f"   Bounty: {b['bounty']}")
        print(f"   Max bounty value: ${b['max_bounty']:,.0f}")
        print(f"   Attacker: {b['attacker']}")
        print(f"   Recovery probability: {b['probability']}")
        print(f"   Expected value: ${b['expected_value']:,.0f}")
        print()
    
    print("=== Analysis ===")
    print("Tier 1 (nation-state): High bounty, near-zero recovery chance")
    print("Tier 2 (organized crime): Medium bounty, low-medium recovery chance") 
    print("Tier 3 (opportunistic): Lower bounty, higher recovery chance")
    print()
    print("Best ROI: Focus on Tier 2-3 targets where recovery is possible")
    print("CoinDCX's 25% bounty signals they believe attacker is beatable")
    
    # Save to JSON
    output = {
        "timestamp": datetime.now().isoformat(),
        "bounties": KNOWN_BOUNTIES,
        "ranked": ranked
    }
    
    with open("active_bounties.json", "w") as f:
        json.dump(output, f, indent=2)
    print("\nSaved to active_bounties.json")

if __name__ == "__main__":
    main()
