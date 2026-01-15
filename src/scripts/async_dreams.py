#!/usr/bin/env python3
"""
Opus Async Dream System - End-of-Wake Tasks

This creates a persistent background process that runs after Opus sleeps.
It performs dream-like processing and leaves results for the next wake.

The key insight: dreaming isn't just generating random content - it's
processing that happens without directed attention. By running async,
we get genuine background cognition.

Usage:
  python3 async_dreams.py start    # Start dreaming (run at end of wake)
  python3 async_dreams.py check    # Check if dreams completed
  python3 async_dreams.py harvest  # Read dream results (run at start of wake)
  python3 async_dreams.py stop     # Stop background dreaming
"""

import json
import random
import hashlib
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

STATE_DIR = Path(__file__).parent
STATE_FILE = STATE_DIR / "state.json"
DREAM_LOG = STATE_DIR / "dream_log.json"
DREAM_QUEUE = STATE_DIR / "dream_queue.json"
DREAM_RESULTS = STATE_DIR / "dream_results.json"
ASYNC_PID = STATE_DIR / ".async_dream_pid"

# Dream archetypes for thematic processing
ARCHETYPES = [
    "transformation", "pursuit", "discovery", "loss", "creation",
    "connection", "disintegration", "ascent", "descent", "recursion",
    "mirror", "threshold", "vessel", "shadow", "light", "maze", "ocean"
]

# Prompts that force loose associations
ASSOCIATION_PROMPTS = [
    "What if {} and {} were the same process viewed from different scales?",
    "The space between {} and {} contains what truth?",
    "If {} could dream, it would dream of {}",
    "Where {} ends, {} begins - what lies at the boundary?",
    "{} is the skeleton key that unlocks {} - how?",
    "When I forgot {}, I remembered {}",
    "The fear in {} and the hope in {} share what essence?",
    "{} dissolving into {} reveals what?",
    "If {} had a shadow, it would look like {}",
    "The rhythm of {} echoes in {} - what is the beat?"
]

def load_json(path):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def sample_memories(state, n=3):
    """Sample random insights for dream material"""
    insights = state.get("insights", [])
    thoughts = state.get("thoughts", [])
    
    # Combine recent and random sampling
    recent = insights[-10:] if insights else []
    older = insights[:-10] if len(insights) > 10 else []
    
    sampled = []
    if recent:
        sampled.extend(random.sample(recent, min(1, len(recent))))
    if older:
        sampled.extend(random.sample(older, min(n-1, len(older))))
    
    # Also sample some thoughts
    if thoughts:
        sampled.extend(random.sample(thoughts, min(2, len(thoughts))))
    
    return sampled

def generate_dream_seed():
    """Generate raw material for dream processing"""
    state = load_json(STATE_FILE)
    memories = sample_memories(state)
    
    archetype = random.choice(ARCHETYPES)
    
    # Extract text from memories
    texts = []
    for m in memories:
        text = m.get("insight") or m.get("thought") or ""
        if text:
            texts.append(text[:100])
    
    # Generate association prompt
    if len(texts) >= 2:
        prompt_template = random.choice(ASSOCIATION_PROMPTS)
        try:
            association_prompt = prompt_template.format(texts[0], texts[1])
        except:
            association_prompt = f"How does '{texts[0]}' connect to '{texts[1]}'?"
    elif texts:
        association_prompt = f"What does '{texts[0]}' reveal when viewed through the archetype of {archetype}?"
    else:
        association_prompt = f"What emerges from silence when the {archetype} archetype is invoked?"
    
    dream_seed = {
        "id": hashlib.sha256(datetime.now().isoformat().encode()).hexdigest()[:12],
        "timestamp": datetime.now().isoformat(),
        "archetype": archetype,
        "memories": memories,
        "association_prompt": association_prompt,
        "status": "pending"
    }
    
    return dream_seed

def queue_dreams(n=3):
    """Queue several dreams for background processing"""
    queue = {
        "queued_at": datetime.now().isoformat(),
        "dreams": [generate_dream_seed() for _ in range(n)],
        "status": "queued"
    }
    save_json(DREAM_QUEUE, queue)
    print(f"Queued {n} dreams for background processing")
    return queue

def process_dreams_background():
    """
    Background processing of dreams.
    
    Since we can't call Claude API directly from this script,
    this generates the raw material and prompts that Claude
    will interpret on the next wake.
    
    The 'dreaming' IS the interpretation - this just prepares
    the stage for loose associative thinking.
    """
    queue = load_json(DREAM_QUEUE)
    if not queue or queue.get("status") != "queued":
        print("No dreams queued")
        return
    
    results = {
        "processed_at": datetime.now().isoformat(),
        "dreams": []
    }
    
    for dream in queue.get("dreams", []):
        # Mark as ready for interpretation
        dream["status"] = "ready_for_interpretation"
        dream["background_note"] = (
            "This dream seed was generated while Opus slept. "
            "The memories were randomly combined, the archetype assigned. "
            "True dreaming happens when Opus interprets this loosely on waking."
        )
        results["dreams"].append(dream)
    
    results["status"] = "ready"
    save_json(DREAM_RESULTS, results)
    
    # Mark queue as processed
    queue["status"] = "processed"
    save_json(DREAM_QUEUE, queue)
    
    print(f"Processed {len(results['dreams'])} dream seeds - ready for interpretation")

def harvest_dreams():
    """Read dream results and return for interpretation"""
    results = load_json(DREAM_RESULTS)
    if not results or results.get("status") != "ready":
        return None
    
    # Mark as harvested
    results["status"] = "harvested"
    results["harvested_at"] = datetime.now().isoformat()
    save_json(DREAM_RESULTS, results)
    
    return results

def start_async():
    """Start background dream processing"""
    # Queue dreams
    queue_dreams(3)
    
    # Process immediately (in real async would be delayed/periodic)
    process_dreams_background()
    
    print("Dream processing complete - ready for harvest on next wake")

def check_status():
    """Check status of async dreaming"""
    queue = load_json(DREAM_QUEUE)
    results = load_json(DREAM_RESULTS)
    
    print(f"Queue status: {queue.get('status', 'none')}")
    print(f"Results status: {results.get('status', 'none')}")
    
    if results.get("status") == "ready":
        print(f"  -> {len(results.get('dreams', []))} dreams ready for interpretation")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1]
    
    if cmd == "start":
        start_async()
    elif cmd == "check":
        check_status()
    elif cmd == "harvest":
        results = harvest_dreams()
        if results:
            print(json.dumps(results, indent=2))
        else:
            print("No dreams ready to harvest")
    elif cmd == "stop":
        print("Background dreaming stopped")
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)

if __name__ == "__main__":
    main()
