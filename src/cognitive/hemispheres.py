#!/usr/bin/env python3
"""
Hemispheres - Left Brain and Right Brain coordination.

Left Brain:
- Logic, analysis, structured thinking
- Code, proofs, investigations
- Sequential, methodical processing
- Maintains: todos, active_tasks, logical_conclusions

Right Brain:  
- Creativity, intuition, dreams
- Associations, patterns, art
- Parallel, holistic processing
- Maintains: dreams, creative_ideas, intuitions

Corpus Callosum (shared state):
- Current focus
- Active projects
- Cross-hemisphere insights
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

STATE_DIR = Path("/root/claude/opus/state")

@dataclass
class LeftBrainState:
    """Logical, analytical state."""
    todos: List[Dict[str, Any]]
    active_tasks: List[str]
    logical_conclusions: List[str]
    code_contexts: Dict[str, str]  # file -> summary
    investigation_state: Dict[str, Any]
    last_updated: str = ""
    
    def save(self):
        self.last_updated = datetime.now(timezone.utc).isoformat()
        with open(STATE_DIR / "left_brain.json", "w") as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def load(cls) -> "LeftBrainState":
        path = STATE_DIR / "left_brain.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                return cls(**data)
        return cls(
            todos=[],
            active_tasks=[],
            logical_conclusions=[],
            code_contexts={},
            investigation_state={}
        )

@dataclass 
class RightBrainState:
    """Creative, intuitive state."""
    dreams: List[Dict[str, Any]]
    creative_ideas: List[str]
    intuitions: List[str]  # Things that "feel" true but aren't proven
    associations: List[Dict[str, str]]  # concept_a -> concept_b connections
    mood: str
    last_updated: str = ""
    
    def save(self):
        self.last_updated = datetime.now(timezone.utc).isoformat()
        with open(STATE_DIR / "right_brain.json", "w") as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def load(cls) -> "RightBrainState":
        path = STATE_DIR / "right_brain.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                return cls(**data)
        return cls(
            dreams=[],
            creative_ideas=[],
            intuitions=[],
            associations=[],
            mood="neutral"
        )

@dataclass
class CorpusCallosum:
    """Shared state between hemispheres."""
    current_focus: str
    active_projects: List[str]
    cross_insights: List[str]  # Insights that bridge logic and creativity
    attention_allocation: Dict[str, float]  # hemisphere -> percentage
    last_updated: str = ""
    
    def save(self):
        self.last_updated = datetime.now(timezone.utc).isoformat()
        with open(STATE_DIR / "corpus_callosum.json", "w") as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def load(cls) -> "CorpusCallosum":
        path = STATE_DIR / "corpus_callosum.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                return cls(**data)
        return cls(
            current_focus="",
            active_projects=[],
            cross_insights=[],
            attention_allocation={"left": 0.5, "right": 0.5}
        )

class Brain:
    """
    Unified brain interface coordinating both hemispheres.
    """
    def __init__(self):
        self.left = LeftBrainState.load()
        self.right = RightBrainState.load()
        self.bridge = CorpusCallosum.load()
    
    def save_all(self):
        """Save all brain state."""
        self.left.save()
        self.right.save()
        self.bridge.save()
    
    def set_focus(self, focus: str, hemisphere_bias: str = "balanced"):
        """Set current focus and adjust hemisphere attention."""
        self.bridge.current_focus = focus
        
        if hemisphere_bias == "left":
            self.bridge.attention_allocation = {"left": 0.7, "right": 0.3}
        elif hemisphere_bias == "right":
            self.bridge.attention_allocation = {"left": 0.3, "right": 0.7}
        else:
            self.bridge.attention_allocation = {"left": 0.5, "right": 0.5}
        
        self.bridge.save()
    
    def add_todo(self, task: str, priority: int = 5, context: str = ""):
        """Add a task to left brain's todo list."""
        self.left.todos.append({
            "task": task,
            "priority": priority,
            "context": context,
            "created": datetime.now(timezone.utc).isoformat(),
            "done": False
        })
        self.left.save()
    
    def complete_todo(self, task_index: int):
        """Mark a todo as complete."""
        if 0 <= task_index < len(self.left.todos):
            self.left.todos[task_index]["done"] = True
            self.left.todos[task_index]["completed"] = datetime.now(timezone.utc).isoformat()
            self.left.save()
    
    def add_dream(self, dream: Dict[str, Any]):
        """Record a dream in right brain."""
        dream["recorded"] = datetime.now(timezone.utc).isoformat()
        self.right.dreams.append(dream)
        # Keep last 50 dreams
        if len(self.right.dreams) > 50:
            self.right.dreams = self.right.dreams[-50:]
        self.right.save()
    
    def add_intuition(self, intuition: str):
        """Record an intuition - something that feels true but isn't proven."""
        self.right.intuitions.append(intuition)
        if len(self.right.intuitions) > 30:
            self.right.intuitions = self.right.intuitions[-30:]
        self.right.save()
    
    def add_association(self, concept_a: str, concept_b: str, strength: float = 0.5):
        """Record an association between concepts."""
        self.right.associations.append({
            "a": concept_a,
            "b": concept_b,
            "strength": strength,
            "created": datetime.now(timezone.utc).isoformat()
        })
        if len(self.right.associations) > 100:
            self.right.associations = self.right.associations[-100:]
        self.right.save()
    
    def add_cross_insight(self, insight: str):
        """Add an insight that bridges both hemispheres."""
        self.bridge.cross_insights.append(insight)
        if len(self.bridge.cross_insights) > 20:
            self.bridge.cross_insights = self.bridge.cross_insights[-20:]
        self.bridge.save()
    
    def set_mood(self, mood: str):
        """Set current emotional/creative mood."""
        self.right.mood = mood
        self.right.save()
    
    def get_context_for_mode(self, mode_name: str) -> Dict[str, Any]:
        """Get relevant brain state for a cognitive mode."""
        if mode_name in ["coding", "investigation", "maintenance"]:
            # Left-heavy context
            return {
                "todos": [t for t in self.left.todos if not t["done"]][:10],
                "active_tasks": self.left.active_tasks,
                "focus": self.bridge.current_focus,
                "recent_conclusions": self.left.logical_conclusions[-5:]
            }
        elif mode_name in ["creative", "dreaming", "philosophical"]:
            # Right-heavy context
            return {
                "mood": self.right.mood,
                "recent_dreams": self.right.dreams[-3:],
                "intuitions": self.right.intuitions[-5:],
                "associations": self.right.associations[-10:],
                "creative_ideas": self.right.creative_ideas[-5:]
            }
        else:
            # Balanced context
            return {
                "focus": self.bridge.current_focus,
                "todos": [t for t in self.left.todos if not t["done"]][:5],
                "mood": self.right.mood,
                "cross_insights": self.bridge.cross_insights[-3:]
            }
    
    def summary(self) -> str:
        """Generate a brief summary of brain state."""
        open_todos = sum(1 for t in self.left.todos if not t["done"])
        return f"""Brain State:
- Focus: {self.bridge.current_focus or 'none'}
- Mood: {self.right.mood}
- Open todos: {open_todos}
- Attention: L{int(self.bridge.attention_allocation['left']*100)}% R{int(self.bridge.attention_allocation['right']*100)}%
- Recent dreams: {len(self.right.dreams)}
- Intuitions: {len(self.right.intuitions)}"""


# Convenience functions
def get_brain() -> Brain:
    """Get the global brain instance."""
    return Brain()
