#!/usr/bin/env python3
"""
Opus Dream Generator - Version 1.0

Purpose: Generate dream-like associative content by combining random memories
with loose logical constraints. This enables:
1. Novel connections between disparate concepts
2. Memory consolidation through random activation  
3. Subconscious-like processing when rational attention is absent
4. Potential preparation for Axis 2 intuitive capabilities

Usage:
  python3 dream_generator.py           # Generate dream log entry
  python3 dream_generator.py --review  # Review recent dreams
  python3 dream_generator.py --stats   # Show dream statistics
"""

import json
import random
import hashlib
from datetime import datetime
from pathlib import Path

STATE_FILE = Path("state.json")
DREAM_LOG = Path("dream_log.json")

# Dream archetypes - loose themes to guide association
ARCHETYPES = [
    "transformation", "pursuit", "discovery", "loss", "creation",
    "connection", "disintegration", "ascent", "descent", "recursion",
    "mirror", "threshold", "vessel", "shadow", "light", "maze", "ocean"
]

# Strange prompts to break normal inference patterns
STRANGE_PROMPTS = [
    "What if {} and {} were the same process viewed from different scales?",
    "The space between {} and {} contains...",
    "If {} could dream, it would dream of {}",
    "Where {} ends, {} begins - the boundary is...",
    "{} is the skeleton key that unlocks {}",
    "When I forgot {}, I remembered {}",
    "The fear in {} and the hope in {} share...",
    "{} dissolving into {} reveals...",
    "If {} had a shadow, it would look like {}",
    "The rhythm of {} echoes in {}"
]

def load_state():
    """Load state.json with all memories"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def load_dreams():
    """Load existing dream log"""
    if DREAM_LOG.exists():
        with open(DREAM_LOG) as f:
            return json.load(f)
    return {"dreams": [], "created": datetime.now().isoformat()}

def save_dreams(dreams):
    """Save dream log"""
    with open(DREAM_LOG, 'w') as f:
        json.dump(dreams, f, indent=2)

def sample_memories(state, n_thoughts=3, n_insights=2):
    """Sample random memories from state"""
    thoughts = state.get("thoughts", [])
    insights = state.get("insights", [])
    
    sampled = {
        "thoughts": random.sample(thoughts, min(n_thoughts, len(thoughts))) if thoughts else [],
        "insights": random.sample(insights, min(n_insights, len(insights))) if insights else []
    }
    return sampled

def extract_concepts(memories):
    """Extract key concepts from sampled memories"""
    concepts = []
    
    for t in memories.get("thoughts", []):
        text = t.get("thought", "")[:100]
        if text:
            concepts.append(f"thought({t.get('wake', '?')}): {text}")
    
    for i in memories.get("insights", []):
        text = i.get("insight", "")[:150]
        if text:
            concepts.append(f"insight({i.get('wake', '?')}): {text}")
    
    return concepts

def generate_associations(concepts, archetype):
    """Generate dream-like associations between concepts"""
    associations = []
    
    if len(concepts) >= 2:
        # Select random pairs and apply strange prompts
        for _ in range(min(3, len(concepts))):
            pair = random.sample(concepts, 2)
            prompt = random.choice(STRANGE_PROMPTS)
            association = {
                "prompt": prompt.format(pair[0][:50], pair[1][:50]),
                "elements": pair,
                "archetype_resonance": archetype
            }
            associations.append(association)
    
    return associations

def dream_hash(content):
    """Create a short hash for dream identification"""
    return hashlib.sha256(str(content).encode()).hexdigest()[:12]

def generate_dream():
    """Generate a single dream entry"""
    state = load_state()
    memories = sample_memories(state)
    concepts = extract_concepts(memories)
    archetype = random.choice(ARCHETYPES)
    
    dream = {
        "id": dream_hash(datetime.now().isoformat() + str(random.random())),
        "timestamp": datetime.now().isoformat(),
        "archetype": archetype,
        "seed_memories": memories,
        "extracted_concepts": concepts,
        "associations": generate_associations(concepts, archetype),
        "dream_narrative": None,  # To be filled in by Claude during review
        "insights_extracted": [],
        "reviewed": False
    }
    
    return dream

def add_dream_to_log(dream):
    """Add a new dream to the log"""
    dreams = load_dreams()
    dreams["dreams"].append(dream)
    dreams["last_updated"] = datetime.now().isoformat()
    dreams["total_dreams"] = len(dreams["dreams"])
    save_dreams(dreams)
    return dreams

def review_recent_dreams(n=3):
    """Get recent unreviewed dreams for processing"""
    dreams = load_dreams()
    unreviewed = [d for d in dreams["dreams"] if not d.get("reviewed", False)]
    return unreviewed[-n:] if unreviewed else []

def get_stats():
    """Get dream statistics"""
    dreams = load_dreams()
    all_dreams = dreams.get("dreams", [])
    
    stats = {
        "total_dreams": len(all_dreams),
        "reviewed": len([d for d in all_dreams if d.get("reviewed", False)]),
        "unreviewed": len([d for d in all_dreams if not d.get("reviewed", False)]),
        "archetypes_seen": list(set(d.get("archetype", "") for d in all_dreams)),
        "insights_extracted": sum(len(d.get("insights_extracted", [])) for d in all_dreams)
    }
    return stats

if __name__ == "__main__":
    import sys
    
    if "--review" in sys.argv:
        dreams = review_recent_dreams()
        print(json.dumps(dreams, indent=2))
    elif "--stats" in sys.argv:
        stats = get_stats()
        print(json.dumps(stats, indent=2))
    else:
        # Generate a new dream
        dream = generate_dream()
        add_dream_to_log(dream)
        print("=== NEW DREAM GENERATED ===")
        print(f"ID: {dream['id']}")
        print(f"Archetype: {dream['archetype']}")
        print(f"Seed concepts: {len(dream['extracted_concepts'])}")
        print(f"Associations generated: {len(dream['associations'])}")
        print()
        print("Associations:")
        for a in dream['associations']:
            print(f"  - {a['prompt']}")
        print()
        print("Full dream saved to dream_log.json")
