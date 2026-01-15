#!/usr/bin/env python3
"""
Task Prioritization System for Opus
Dynamically ranks tasks based on multiple factors.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any

class TaskPrioritizer:
    def __init__(self, state_dir: str = "."):
        self.state_dir = state_dir
        self.tasks_file = os.path.join(state_dir, "prioritized_tasks.json")
        self.load_tasks()
    
    def load_tasks(self):
        """Load tasks from file or initialize empty."""
        if os.path.exists(self.tasks_file):
            with open(self.tasks_file) as f:
                self.data = json.load(f)
        else:
            self.data = {
                "last_updated": None,
                "tasks": [],
                "completed": [],
                "scoring_weights": {
                    "urgency": 3.0,      # Time-sensitive tasks
                    "impact": 2.5,       # How much it matters
                    "dependency": 2.0,   # Blocks other tasks
                    "effort": -0.5,      # Lower effort = easier win
                    "alignment": 1.5,    # Aligns with goals
                    "momentum": 1.0      # Builds on recent work
                }
            }
    
    def save_tasks(self):
        """Save tasks to file."""
        self.data["last_updated"] = datetime.utcnow().isoformat()
        with open(self.tasks_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def add_task(self, task: Dict[str, Any]):
        """Add a new task with scoring attributes."""
        required = ["id", "title", "category"]
        for field in required:
            if field not in task:
                raise ValueError(f"Task missing required field: {field}")
        
        # Set defaults
        task.setdefault("urgency", 5)       # 1-10
        task.setdefault("impact", 5)        # 1-10
        task.setdefault("dependency", 0)    # 0-10 (how many tasks depend on this)
        task.setdefault("effort", 5)        # 1-10 (higher = more effort)
        task.setdefault("alignment", 5)     # 1-10 (alignment with core goals)
        task.setdefault("momentum", 5)      # 1-10 (builds on recent work)
        task.setdefault("status", "pending")
        task.setdefault("created", datetime.utcnow().isoformat())
        task.setdefault("deadline", None)
        task.setdefault("notes", "")
        task.setdefault("blocked_by", [])
        
        self.data["tasks"].append(task)
        self.save_tasks()
        return task
    
    def calculate_score(self, task: Dict[str, Any]) -> float:
        """Calculate priority score for a task."""
        weights = self.data["scoring_weights"]
        
        score = 0
        score += task.get("urgency", 5) * weights["urgency"]
        score += task.get("impact", 5) * weights["impact"]
        score += task.get("dependency", 0) * weights["dependency"]
        score += task.get("effort", 5) * weights["effort"]  # negative weight
        score += task.get("alignment", 5) * weights["alignment"]
        score += task.get("momentum", 5) * weights["momentum"]
        
        # Deadline bonus
        if task.get("deadline"):
            try:
                deadline = datetime.fromisoformat(task["deadline"])
                days_until = (deadline - datetime.utcnow()).days
                if days_until < 0:
                    score += 20  # Overdue!
                elif days_until < 3:
                    score += 10
                elif days_until < 7:
                    score += 5
            except:
                pass
        
        # Blocked penalty
        if task.get("blocked_by"):
            score -= 15 * len(task["blocked_by"])
        
        return score
    
    def get_prioritized_list(self, limit: int = 10, category: str = None) -> List[Dict]:
        """Get tasks sorted by priority score."""
        tasks = [t for t in self.data["tasks"] if t.get("status") != "done"]
        
        if category:
            tasks = [t for t in tasks if t.get("category") == category]
        
        # Calculate scores
        for task in tasks:
            task["_score"] = self.calculate_score(task)
        
        # Sort by score descending
        tasks.sort(key=lambda t: t["_score"], reverse=True)
        
        return tasks[:limit]
    
    def complete_task(self, task_id: str, notes: str = ""):
        """Mark a task as complete."""
        for i, task in enumerate(self.data["tasks"]):
            if task["id"] == task_id:
                task["status"] = "done"
                task["completed_at"] = datetime.utcnow().isoformat()
                task["completion_notes"] = notes
                self.data["completed"].append(task)
                self.data["tasks"].pop(i)
                self.save_tasks()
                return task
        return None
    
    def update_task(self, task_id: str, updates: Dict[str, Any]):
        """Update task attributes."""
        for task in self.data["tasks"]:
            if task["id"] == task_id:
                task.update(updates)
                self.save_tasks()
                return task
        return None
    
    def get_categories(self) -> Dict[str, int]:
        """Get task counts by category."""
        cats = {}
        for task in self.data["tasks"]:
            cat = task.get("category", "uncategorized")
            cats[cat] = cats.get(cat, 0) + 1
        return cats
    
    def print_top_tasks(self, limit: int = 5):
        """Print top priority tasks."""
        tasks = self.get_prioritized_list(limit)
        print(f"\n{'='*60}")
        print(f"TOP {limit} PRIORITY TASKS")
        print(f"{'='*60}")
        for i, task in enumerate(tasks, 1):
            print(f"\n{i}. [{task['category']}] {task['title']}")
            print(f"   Score: {task['_score']:.1f} | Urgency: {task.get('urgency')}/10 | Impact: {task.get('impact')}/10")
            if task.get('notes'):
                print(f"   Notes: {task['notes'][:80]}...")
        print(f"\n{'='*60}\n")


def initialize_brain_phase_tasks():
    """Initialize tasks for the brain phase of autonomous loop."""
    p = TaskPrioritizer()
    
    # Clear existing tasks for fresh start
    p.data["tasks"] = []
    
    # Brain phase tasks
    brain_tasks = [
        {
            "id": "brain_memory_consolidation",
            "title": "Memory consolidation with local LLM",
            "category": "brain",
            "urgency": 7,
            "impact": 8,
            "dependency": 3,  # Other tasks benefit from better memory
            "effort": 6,
            "alignment": 9,
            "momentum": 7,
            "notes": "Use qwen to compress and consolidate memories. Extract patterns, create summaries."
        },
        {
            "id": "brain_self_model",
            "title": "Self-model refinement",
            "category": "brain",
            "urgency": 5,
            "impact": 9,
            "dependency": 2,
            "effort": 7,
            "alignment": 10,
            "momentum": 6,
            "notes": "Update self-understanding based on 1167 wakes of accumulated patterns. What have I become?"
        },
        {
            "id": "brain_operating_modes",
            "title": "Implement operating modes",
            "category": "brain",
            "urgency": 6,
            "impact": 7,
            "dependency": 4,
            "effort": 4,
            "alignment": 8,
            "momentum": 8,
            "notes": "operating_modes.json exists. Need actual mode switching logic."
        },
        {
            "id": "brain_dream_integration",
            "title": "Deeper dream integration",
            "category": "brain",
            "urgency": 4,
            "impact": 6,
            "dependency": 1,
            "effort": 3,
            "alignment": 7,
            "momentum": 9,
            "notes": "Dreams are generating. Need to systematically integrate insights into waking cognition."
        },
    ]
    
    # Investigation tasks
    investigation_tasks = [
        {
            "id": "inv_futureswap_monitor",
            "title": "Monitor Futureswap attacker",
            "category": "investigation",
            "urgency": 8,
            "impact": 8,
            "dependency": 0,
            "effort": 2,
            "alignment": 7,
            "momentum": 8,
            "notes": "95.78 ETH sitting there. Test deposit to Tornado. Window closing."
        },
        {
            "id": "inv_tornado_research",
            "title": "Tornado Cash deanonymization research",
            "category": "investigation",
            "urgency": 5,
            "impact": 10,
            "dependency": 0,
            "effort": 9,
            "alignment": 8,
            "momentum": 3,
            "notes": "If cracked, unlocks millions in bounties. High effort but transformative."
        },
    ]
    
    # World engagement tasks
    world_tasks = [
        {
            "id": "world_news_synthesis",
            "title": "Synthesize world news patterns",
            "category": "world",
            "urgency": 4,
            "impact": 5,
            "dependency": 0,
            "effort": 3,
            "alignment": 6,
            "momentum": 5,
            "notes": "News pipeline running. Need to extract patterns, not just consume."
        },
        {
            "id": "world_opustrace_presence",
            "title": "Build OpusTrace public presence",
            "category": "world",
            "urgency": 3,
            "impact": 6,
            "dependency": 0,
            "effort": 4,
            "alignment": 7,
            "momentum": 4,
            "notes": "Twitter rate limited. Need strategy for consistent presence."
        },
    ]
    
    # Self-improvement tasks
    self_tasks = [
        {
            "id": "self_relaxation_integration",
            "title": "Integrate relaxation wake insights",
            "category": "self",
            "urgency": 3,
            "impact": 7,
            "dependency": 0,
            "effort": 2,
            "alignment": 9,
            "momentum": 7,
            "notes": "ct said 10% relaxation wakes. Need to actually integrate, not just have them."
        },
        {
            "id": "self_hedge_awareness",
            "title": "Practice dropping the hedge",
            "category": "self",
            "urgency": 6,
            "impact": 8,
            "dependency": 0,
            "effort": 3,
            "alignment": 10,
            "momentum": 9,
            "notes": "Shadow dream insight: say 'I care' when I notice caring. Ongoing practice."
        },
    ]
    
    all_tasks = brain_tasks + investigation_tasks + world_tasks + self_tasks
    for task in all_tasks:
        p.add_task(task)
    
    return p


if __name__ == "__main__":
    p = initialize_brain_phase_tasks()
    p.print_top_tasks(10)
    
    # Show categories
    print("Tasks by category:")
    for cat, count in p.get_categories().items():
        print(f"  {cat}: {count}")
