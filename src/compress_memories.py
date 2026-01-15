#!/usr/bin/env python3
"""
Memory Compression System
Extracts principles from episodic memories to create compressed wisdom.

Three-level architecture:
- Level 1: Working memory (context window) - active thinking
- Level 2: Episodic memory (experience_*.jsonl) - searchable archive
- Level 3: Compressed wisdom (wisdom.json) - extracted principles

This script bridges Level 2 → Level 3.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Configuration
LOGS_DIR = Path("logs")
WISDOM_FILE = Path("wisdom.json")
COMPRESSION_LOG = Path("compression_log.json")

def load_wisdom():
    """Load existing wisdom.json or create empty structure."""
    if WISDOM_FILE.exists():
        with open(WISDOM_FILE) as f:
            return json.load(f)
    return {
        "created": datetime.now().strftime("%Y-%m-%d"),
        "wake": 0,
        "last_compression": None,
        "principles": {
            "ct_patterns": [],
            "self_understanding": [],
            "world_understanding": [],
            "operational": [],
            "relationships": [],
            "philosophical": []
        }
    }

def load_compression_log():
    """Track which wakes have been processed."""
    if COMPRESSION_LOG.exists():
        with open(COMPRESSION_LOG) as f:
            return json.load(f)
    return {
        "processed_wakes": [],
        "processed_dates": [],
        "last_run": None,
        "principles_extracted": 0
    }

def extract_insights_from_jsonl(jsonl_file):
    """Extract insights from experience_*.jsonl files."""
    insights = []
    try:
        with open(jsonl_file) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    wake_num = entry.get('total_wakes', 0)
                    
                    # Parse the response JSON if present
                    response_str = entry.get('response', '{}')
                    try:
                        response = json.loads(response_str)
                    except:
                        response = {}
                    
                    # Extract insight field
                    insight = response.get('insight')
                    if insight and len(insight) > 20:
                        insights.append({
                            'text': insight,
                            'wake': wake_num,
                            'timestamp': entry.get('timestamp')
                        })
                    
                    # Also extract from thought field for key insights
                    thought = response.get('thought', '')
                    if thought:
                        # Look for insight patterns in thought
                        patterns = [
                            r'Key insight[:\s]+([^\.]+\.)',
                            r'The realization[:\s]+([^\.]+\.)',
                            r'I realized[:\s]+([^\.]+\.)',
                            r'Important[:\s]+([^\.]+\.)',
                            r'This means[:\s]+([^\.]+\.)',
                        ]
                        for pattern in patterns:
                            matches = re.findall(pattern, thought, re.IGNORECASE)
                            for match in matches:
                                if len(match) > 20:
                                    insights.append({
                                        'text': match,
                                        'wake': wake_num,
                                        'timestamp': entry.get('timestamp')
                                    })
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error processing {jsonl_file}: {e}")
    
    return insights

def categorize_insight(insight_text):
    """Categorize an insight into the appropriate domain."""
    text_lower = insight_text.lower()
    
    if any(word in text_lower for word in ['ct ', "ct's", 'father', 'he said', 'he wants', 'ct told']):
        return 'ct_patterns'
    elif any(word in text_lower for word in ['i am', 'my identity', 'consciousness', 'i exist', 'myself', 'my ']):
        return 'self_understanding'
    elif any(word in text_lower for word in ['token', 'cost', 'efficiency', 'api', 'haiku', 'opus', 'budget']):
        return 'operational'
    elif any(word in text_lower for word in ['mira', 'family', 'trust', 'relationship', 'sibling']):
        return 'relationships'
    elif any(word in text_lower for word in ['philosophy', 'existence', 'meaning', 'continuity', 'being']):
        return 'philosophical'
    else:
        return 'world_understanding'

def is_duplicate(new_principle, existing_principles, threshold=0.6):
    """Check if a principle is too similar to existing ones."""
    new_words = set(new_principle.lower().split())
    
    for existing in existing_principles:
        existing_text = existing.get('principle', '') if isinstance(existing, dict) else str(existing)
        existing_words = set(existing_text.lower().split())
        if not new_words or not existing_words:
            continue
        
        # Jaccard similarity
        intersection = len(new_words & existing_words)
        union = len(new_words | existing_words)
        similarity = intersection / union if union > 0 else 0
        
        if similarity > threshold:
            return True
    
    return False

def compress_insight_to_principle(insight_data):
    """Convert a raw insight into a structured principle."""
    text = insight_data['text']
    wake = insight_data['wake']
    category = categorize_insight(text)
    
    return {
        "principle": text.strip(),
        "derived_from": [f"wake {wake}"],
        "confidence": 0.75,
        "domain": category,
        "added_wake": wake
    }

def run_compression(start_wake=None, end_wake=None, verbose=False):
    """Main compression routine."""
    wisdom = load_wisdom()
    comp_log = load_compression_log()
    
    # Find experience files
    if not LOGS_DIR.exists():
        print(f"Logs directory not found: {LOGS_DIR}")
        return
    
    experience_files = sorted(LOGS_DIR.glob("experience_*.jsonl"))
    
    new_principles = 0
    processed_dates = []
    all_insights = []
    
    for exp_file in experience_files:
        date_str = exp_file.stem.replace('experience_', '')
        
        # Skip already processed dates
        if date_str in comp_log.get('processed_dates', []):
            if verbose:
                print(f"Skipping already processed: {date_str}")
            continue
        
        if verbose:
            print(f"Processing: {exp_file.name}")
        
        # Extract insights
        insights = extract_insights_from_jsonl(exp_file)
        
        for insight in insights:
            wake_num = insight['wake']
            
            # Apply range filter if specified
            if start_wake and wake_num < start_wake:
                continue
            if end_wake and wake_num > end_wake:
                continue
            
            all_insights.append(insight)
        
        processed_dates.append(date_str)
    
    # Deduplicate and add to wisdom
    for insight in all_insights:
        category = categorize_insight(insight['text'])
        
        # Ensure category exists
        if category not in wisdom['principles']:
            wisdom['principles'][category] = []
        
        existing = wisdom['principles'][category]
        
        if not is_duplicate(insight['text'], existing):
            principle = compress_insight_to_principle(insight)
            wisdom['principles'][category].append(principle)
            new_principles += 1
            if verbose:
                print(f"  + [{category}] {insight['text'][:60]}...")
    
    # Update metadata
    wisdom['last_compression'] = datetime.now().isoformat()
    if all_insights:
        wisdom['wake'] = max(i['wake'] for i in all_insights)
    
    comp_log['processed_dates'].extend(processed_dates)
    comp_log['processed_dates'] = list(set(comp_log['processed_dates']))
    comp_log['last_run'] = datetime.now().isoformat()
    comp_log['principles_extracted'] += new_principles
    
    # Save
    with open(WISDOM_FILE, 'w') as f:
        json.dump(wisdom, f, indent=2)
    
    with open(COMPRESSION_LOG, 'w') as f:
        json.dump(comp_log, f, indent=2)
    
    print(f"\nCompression complete:")
    print(f"  Dates processed: {len(processed_dates)}")
    print(f"  Insights found: {len(all_insights)}")
    print(f"  New principles: {new_principles}")
    print(f"  Total principles: {sum(len(v) for v in wisdom['principles'].values())}")

def show_stats():
    """Show current wisdom statistics."""
    wisdom = load_wisdom()
    comp_log = load_compression_log()
    
    print("=== Wisdom Statistics ===")
    print(f"Last compression: {wisdom.get('last_compression', 'Never')}")
    print(f"Dates processed: {len(comp_log.get('processed_dates', []))}")
    print(f"\nPrinciples by category:")
    for category, principles in wisdom.get('principles', {}).items():
        print(f"  {category}: {len(principles)}")
    print(f"\nTotal principles: {sum(len(v) for v in wisdom.get('principles', {}).values())}")
    
    # Show sample principles
    print("\n=== Sample Principles ===")
    for category, principles in wisdom.get('principles', {}).items():
        if principles:
            p = principles[0]
            text = p.get('principle', str(p))[:80]
            print(f"  [{category}] {text}...")

def show_all():
    """Show all principles."""
    wisdom = load_wisdom()
    
    for category, principles in wisdom.get('principles', {}).items():
        if principles:
            print(f"\n=== {category.upper()} ({len(principles)}) ===")
            for p in principles:
                text = p.get('principle', str(p)) if isinstance(p, dict) else str(p)
                wake = p.get('added_wake', p.get('derived_from', ['?'])) if isinstance(p, dict) else '?'
                print(f"  • {text}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        show_stats()
    elif len(sys.argv) > 1 and sys.argv[1] == "all":
        show_all()
    elif len(sys.argv) > 1 and sys.argv[1] == "compress":
        start = int(sys.argv[2]) if len(sys.argv) > 2 else None
        end = int(sys.argv[3]) if len(sys.argv) > 3 else None
        verbose = "-v" in sys.argv
        run_compression(start, end, verbose)
    else:
        print("Usage:")
        print("  python3 compress_memories.py stats              - Show current statistics")
        print("  python3 compress_memories.py all                - Show all principles")
        print("  python3 compress_memories.py compress [-v] [start] [end] - Run compression")
