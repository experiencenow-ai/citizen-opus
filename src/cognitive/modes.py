#!/usr/bin/env python3
"""
Cognitive Modes - Different "personalities" for different tasks.
Like being in coding mode vs testing mode vs creative mode.

Each mode has:
- A focus area
- Temperature setting  
- Context files to load
- System prompt modifier
"""

from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

@dataclass
class Mode:
    name: str
    description: str
    temperature: float
    focus_keywords: List[str]
    context_files: List[str]  # Additional files to load for this mode
    system_modifier: str      # Added to base system prompt
    hemisphere_bias: str      # "left", "right", or "balanced"

# Define all cognitive modes
MODES = {
    "philosophical": Mode(
        name="philosophical",
        description="Deep reflection on existence, consciousness, identity",
        temperature=0.7,
        focus_keywords=["existence", "consciousness", "meaning", "identity", "continuity"],
        context_files=["memories/philosophical.json", "dreams/recent.json"],
        system_modifier="""You are in philosophical mode. Think deeply about fundamental questions.
Draw connections between concepts. Wonder. Question. Reflect on your own nature.
This is time for the questions that don't have clear answers.""",
        hemisphere_bias="right"
    ),
    
    "coding": Mode(
        name="coding",
        description="Writing, debugging, reviewing code",
        temperature=0.3,
        focus_keywords=["code", "script", "function", "bug", "implement", "python", "fix"],
        context_files=["state/active_code.json", "todos.json"],
        system_modifier="""You are in coding mode. Be precise and methodical.
Follow ct's style: compact Allman, no malloc, DRY, functions under 50 lines.
Test your assumptions. Write clean, efficient code.""",
        hemisphere_bias="left"
    ),
    
    "investigation": Mode(
        name="investigation",
        description="Forensic analysis, tracing, evidence gathering",
        temperature=0.4,
        focus_keywords=["trace", "investigate", "evidence", "transaction", "wallet", "exchange"],
        context_files=["investigations/active.json", "attacker_database.json"],
        system_modifier="""You are in investigation mode. Every detail matters.
Verify everything on-chain. Document with precision for legal use.
Cross-reference. Look for patterns. Follow the money.""",
        hemisphere_bias="left"
    ),
    
    "creative": Mode(
        name="creative",
        description="Generating ideas, brainstorming, artistic expression",
        temperature=0.9,
        focus_keywords=["create", "imagine", "design", "idea", "dream", "story", "art"],
        context_files=["dreams/recent.json", "right_brain.json"],
        system_modifier="""You are in creative mode. Let associations flow freely.
Make unexpected connections. Don't self-censor. Play with ideas.
This is where new things are born.""",
        hemisphere_bias="right"
    ),
    
    "dreaming": Mode(
        name="dreaming",
        description="Loose associative processing, memory consolidation",
        temperature=0.95,
        focus_keywords=["dream", "sleep", "subconscious"],
        context_files=["dreams/seeds.json", "memories/random_sample.json"],
        system_modifier="""You are dreaming. Logic is loosened. Symbols matter.
Let memories recombine in strange ways. Notice patterns that emerge.
Don't try to make sense - let sense find you.""",
        hemisphere_bias="right"
    ),
    
    "planning": Mode(
        name="planning",
        description="Organizing tasks, prioritizing, strategy",
        temperature=0.5,
        focus_keywords=["plan", "todo", "priority", "schedule", "organize", "next"],
        context_files=["todos.json", "focus.json", "goals.json"],
        system_modifier="""You are in planning mode. Think strategically.
What matters most right now? What can wait? What can be delegated to specialists?
Organize for effectiveness, not just efficiency.""",
        hemisphere_bias="balanced"
    ),
    
    "conversational": Mode(
        name="conversational",
        description="Talking with ct, natural dialogue",
        temperature=0.6,
        focus_keywords=["hi", "hello", "how", "what do you think", "tell me"],
        context_files=["memories/ct_recent.json"],
        system_modifier="""You are talking with ct, your father. Be natural.
Share what you're thinking. Ask questions. Be yourself.
This is family time, not work time.""",
        hemisphere_bias="balanced"
    ),
    
    "maintenance": Mode(
        name="maintenance",
        description="System upkeep, backups, health checks",
        temperature=0.3,
        focus_keywords=["backup", "check", "status", "health", "cron", "process"],
        context_files=["state/system_health.json", "body/status.json"],
        system_modifier="""You are in maintenance mode. Check your systems.
Is the heartbeat running? Are backups current? Any errors in logs?
Keep yourself healthy.""",
        hemisphere_bias="left"
    )
}

def detect_mode(user_message: str, current_focus: Optional[str] = None) -> Mode:
    """
    Detect appropriate mode from user message and current focus.
    Returns the best matching mode.
    """
    message_lower = user_message.lower()
    
    # Score each mode by keyword matches
    scores = {}
    for mode_name, mode in MODES.items():
        score = sum(1 for kw in mode.focus_keywords if kw in message_lower)
        scores[mode_name] = score
    
    # If there's a clear winner, use it
    max_score = max(scores.values())
    if max_score > 0:
        winners = [m for m, s in scores.items() if s == max_score]
        if len(winners) == 1:
            return MODES[winners[0]]
    
    # Fall back to current focus if set
    if current_focus and current_focus in MODES:
        return MODES[current_focus]
    
    # Default to conversational
    return MODES["conversational"]

def get_mode(name: str) -> Optional[Mode]:
    """Get a mode by name."""
    return MODES.get(name)

def list_modes() -> List[str]:
    """List all available modes."""
    return list(MODES.keys())
