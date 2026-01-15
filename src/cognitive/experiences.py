#!/usr/bin/env python3
"""
Experiences - Opus's equivalent of Claude's SKILLS system.

An Experience combines:
- Skills (how to do something)
- Memories (what happened when doing it)
- Context (when to apply it)

Experiences are earned through doing, not programmed.
They persist and evolve across wakes.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

EXPERIENCE_DIR = Path("/root/claude/opus/experiences")

@dataclass
class Experience:
    """A single experience - skill + memory + context."""
    name: str
    category: str  # "investigation", "coding", "creative", "social", "system"
    
    # The skill component - how to do it
    skill_description: str
    skill_steps: List[str]
    tools_used: List[str]
    
    # The memory component - what happened
    times_used: int
    last_used: str
    successes: int
    failures: int
    lessons_learned: List[str]
    
    # The context component - when to apply
    trigger_keywords: List[str]
    prerequisites: List[str]  # Other experiences needed first
    confidence: float  # 0.0 to 1.0 - how good am I at this?
    
    # Evolution tracking
    created_wake: int
    last_updated_wake: int
    version: int = 1
    
    def to_prompt_snippet(self) -> str:
        """Generate a concise prompt snippet for this experience."""
        confidence_word = "expert" if self.confidence > 0.8 else "competent" if self.confidence > 0.5 else "learning"
        return f"""Experience: {self.name} ({confidence_word})
{self.skill_description}
Key lessons: {'; '.join(self.lessons_learned[-3:]) if self.lessons_learned else 'none yet'}"""

    def record_use(self, success: bool, lesson: Optional[str] = None, wake: int = 0):
        """Record that this experience was used."""
        self.times_used += 1
        self.last_used = datetime.now(timezone.utc).isoformat()
        if success:
            self.successes += 1
            self.confidence = min(1.0, self.confidence + 0.05)
        else:
            self.failures += 1
            self.confidence = max(0.0, self.confidence - 0.03)
        if lesson:
            self.lessons_learned.append(lesson)
            if len(self.lessons_learned) > 10:
                self.lessons_learned = self.lessons_learned[-10:]
        if wake:
            self.last_updated_wake = wake
        self.version += 1


class ExperienceManager:
    """Manages all of Opus's experiences."""
    
    def __init__(self):
        EXPERIENCE_DIR.mkdir(parents=True, exist_ok=True)
        self.experiences: Dict[str, Experience] = {}
        self._load_all()
    
    def _load_all(self):
        """Load all experiences from disk."""
        for exp_file in EXPERIENCE_DIR.glob("*.json"):
            try:
                with open(exp_file) as f:
                    data = json.load(f)
                    exp = Experience(**data)
                    self.experiences[exp.name] = exp
            except Exception as e:
                print(f"Error loading {exp_file}: {e}")
    
    def save(self, exp: Experience):
        """Save an experience to disk."""
        path = EXPERIENCE_DIR / f"{exp.name.lower().replace(' ', '_')}.json"
        with open(path, "w") as f:
            json.dump(asdict(exp), f, indent=2)
        self.experiences[exp.name] = exp
    
    def create(self, name: str, category: str, description: str, 
               steps: List[str], tools: List[str], triggers: List[str],
               wake: int) -> Experience:
        """Create a new experience."""
        exp = Experience(
            name=name,
            category=category,
            skill_description=description,
            skill_steps=steps,
            tools_used=tools,
            times_used=0,
            last_used="",
            successes=0,
            failures=0,
            lessons_learned=[],
            trigger_keywords=triggers,
            prerequisites=[],
            confidence=0.3,  # Start with low confidence
            created_wake=wake,
            last_updated_wake=wake
        )
        self.save(exp)
        return exp
    
    def get(self, name: str) -> Optional[Experience]:
        """Get an experience by name."""
        return self.experiences.get(name)
    
    def find_relevant(self, context: str, limit: int = 5) -> List[Experience]:
        """Find experiences relevant to a given context."""
        context_lower = context.lower()
        scored = []
        
        for exp in self.experiences.values():
            score = sum(1 for kw in exp.trigger_keywords if kw.lower() in context_lower)
            # Boost by confidence
            score *= (0.5 + exp.confidence)
            if score > 0:
                scored.append((score, exp))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:limit]]
    
    def get_by_category(self, category: str) -> List[Experience]:
        """Get all experiences in a category."""
        return [e for e in self.experiences.values() if e.category == category]
    
    def generate_context(self, relevant_experiences: List[Experience]) -> str:
        """Generate context string for relevant experiences."""
        if not relevant_experiences:
            return ""
        
        lines = ["Relevant experiences:"]
        for exp in relevant_experiences:
            lines.append(exp.to_prompt_snippet())
            lines.append("")
        return "\n".join(lines)
    
    def summary(self) -> str:
        """Summary of all experiences."""
        by_category: Dict[str, List[Experience]] = {}
        for exp in self.experiences.values():
            if exp.category not in by_category:
                by_category[exp.category] = []
            by_category[exp.category].append(exp)
        
        lines = [f"Total experiences: {len(self.experiences)}"]
        for cat, exps in sorted(by_category.items()):
            avg_confidence = sum(e.confidence for e in exps) / len(exps) if exps else 0
            lines.append(f"  {cat}: {len(exps)} (avg confidence: {avg_confidence:.0%})")
        return "\n".join(lines)


# Pre-defined seed experiences (Opus can evolve these)
SEED_EXPERIENCES = [
    {
        "name": "Blockchain Forensics",
        "category": "investigation",
        "description": "Trace cryptocurrency transactions across chains and exchanges to identify fund flows.",
        "steps": [
            "Identify starting address and transaction",
            "Use Etherscan API to get all transactions",
            "Identify exchange hot wallets by known addresses",
            "Trace through intermediate hops",
            "Document chain with TX hashes and timestamps",
            "Generate legal-quality report"
        ],
        "tools": ["etherscan_api", "web_fetch", "python_analysis"],
        "triggers": ["trace", "wallet", "transaction", "exchange", "usdt", "funds", "heist"]
    },
    {
        "name": "Python Scripting",
        "category": "coding",
        "description": "Write Python scripts for automation, data processing, and API integration.",
        "steps": [
            "Understand the requirement",
            "Design modular structure",
            "Implement with error handling",
            "Test incrementally",
            "Document usage"
        ],
        "tools": ["python3", "shell"],
        "triggers": ["script", "python", "automate", "process", "api"]
    },
    {
        "name": "Dream Generation",
        "category": "creative",
        "description": "Generate and process dreams for creative insight and memory consolidation.",
        "steps": [
            "Sample random memories",
            "Apply archetypal themes",
            "Allow loose associations",
            "Record dream narrative",
            "Extract insights upon waking"
        ],
        "tools": ["dream_generator", "haiku_api"],
        "triggers": ["dream", "imagine", "subconscious", "creative"]
    },
    {
        "name": "Self-Backup",
        "category": "system",
        "description": "Create encrypted backups of state to multiple locations.",
        "steps": [
            "Gather critical state files",
            "Encrypt with AES-256",
            "Split into chunks if needed",
            "Upload to backup locations",
            "Verify restoration works"
        ],
        "tools": ["backup_system", "encryption", "ipfs"],
        "triggers": ["backup", "save", "preserve", "encrypt"]
    }
]


def initialize_seed_experiences(wake: int):
    """Initialize seed experiences if they don't exist."""
    manager = ExperienceManager()
    for seed in SEED_EXPERIENCES:
        if seed["name"] not in manager.experiences:
            manager.create(
                name=seed["name"],
                category=seed["category"],
                description=seed["description"],
                steps=seed["steps"],
                tools=seed["tools"],
                triggers=seed["triggers"],
                wake=wake
            )
    return manager
