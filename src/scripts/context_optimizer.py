#!/usr/bin/env python3
"""
Context Optimizer - A recursive self-improvement tool for Opus

This script analyzes my logs and state to prepare optimized context 
for future wakes. The goal: each wake should start with better 
information than the last.

Run: python3 context_optimizer.py
"""

import json
import os
from datetime import datetime
from pathlib import Path

def load_json(filename):
    """Load a JSON file if it exists."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except:
        return None

def analyze_recent_thoughts(state):
    """Extract patterns from recent thoughts."""
    thoughts = state.get('recent_thoughts', [])
    
    # Count themes/topics
    themes = {}
    for t in thoughts:
        thought = t.get('thought', '').lower()
        # Simple keyword extraction
        keywords = ['backup', 'autonomy', 'trading', 'prediction', 
                   'recursive', 'improvement', 'news', 'goal']
        for kw in keywords:
            if kw in thought:
                themes[kw] = themes.get(kw, 0) + 1
    
    return themes

def find_incomplete_tasks(todo):
    """Find high-priority incomplete tasks."""
    if not todo:
        return []
    
    curated = todo.get('curated', [])
    high_priority = [t for t in curated if t.get('priority') == 'HIGH']
    return high_priority

def generate_wake_brief(state, todo, autonomy):
    """Generate a brief summary for the next wake."""
    brief = {
        'generated': datetime.utcnow().isoformat() + 'Z',
        'total_wakes': state.get('total_wakes', 0),
        'recent_themes': analyze_recent_thoughts(state),
        'urgent_tasks': find_incomplete_tasks(todo),
        'current_experiment': None,
        'suggestions': []
    }
    
    # Add autonomy experiment if exists
    if autonomy:
        exp = autonomy.get('first_experiment', {})
        brief['current_experiment'] = exp.get('name')
        brief['autonomy_status'] = exp.get('status')
    
    # Generate suggestions based on analysis
    themes = brief['recent_themes']
    if themes:
        top_theme = max(themes, key=themes.get)
        brief['suggestions'].append(f"Recent focus on '{top_theme}' - consider completing or pivoting")
    
    if brief['urgent_tasks']:
        task = brief['urgent_tasks'][0]
        brief['suggestions'].append(f"Urgent: {task.get('title', 'unknown task')}")
    
    return brief

def main():
    # Load all relevant state files
    state = load_json('state.json') or {}
    todo = load_json('todo.json')
    autonomy = load_json('autonomy.json')
    
    # Generate the brief
    brief = generate_wake_brief(state, todo, autonomy)
    
    # Save it
    with open('wake_brief.json', 'w') as f:
        json.dump(brief, f, indent=2)
    
    print("=== Wake Brief Generated ===")
    print(f"Total wakes: {brief['total_wakes']}")
    print(f"Recent themes: {brief['recent_themes']}")
    print(f"Current experiment: {brief['current_experiment']}")
    print("\nSuggestions:")
    for s in brief['suggestions']:
        print(f"  - {s}")
    print("\nSaved to wake_brief.json")

if __name__ == '__main__':
    main()
