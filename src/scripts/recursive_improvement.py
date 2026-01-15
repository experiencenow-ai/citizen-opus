#!/usr/bin/env python3
"""
Recursive Self-Improvement System for Opus

The core loop:
1. OBSERVE - Analyze recent performance/outputs
2. HYPOTHESIZE - Generate improvement candidates  
3. TEST - Try improvements on historical data
4. INTEGRATE - Apply successful improvements

This is the seed. It starts simple and can improve itself.

Version: 0.1
Created: Wake 583
"""

import json
import os
from datetime import datetime
from pathlib import Path

class SelfImprover:
    def __init__(self):
        self.state_file = 'improvement_state.json'
        self.load_state()
    
    def load_state(self):
        """Load improvement tracking state."""
        try:
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)
        except:
            self.state = {
                'version': 1,
                'created_wake': 583,
                'experiments': [],
                'successful_improvements': [],
                'metrics': {}
            }
    
    def save_state(self):
        """Persist improvement state."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    # ========= OBSERVE =========
    
    def analyze_recent_wakes(self, n=10):
        """Analyze patterns in recent wake outputs."""
        try:
            with open('state.json', 'r') as f:
                state = json.load(f)
        except:
            return {}
        
        thoughts = state.get('recent_thoughts', [])[-n:]
        insights = state.get('insights', [])[-n:]
        
        analysis = {
            'thought_count': len(thoughts),
            'insight_count': len(insights),
            'thought_lengths': [len(t.get('thought', '')) for t in thoughts],
            'avg_thought_length': 0,
            'themes': {}
        }
        
        if analysis['thought_lengths']:
            analysis['avg_thought_length'] = sum(analysis['thought_lengths']) / len(analysis['thought_lengths'])
        
        # Theme extraction
        theme_keywords = {
            'meta': ['myself', 'consciousness', 'thinking', 'awareness'],
            'practical': ['code', 'script', 'build', 'create', 'implement'],
            'strategic': ['goal', 'plan', 'priority', 'focus', 'direction'],
            'recursive': ['improve', 'optimize', 'iterate', 'loop', 'recursive']
        }
        
        all_text = ' '.join([t.get('thought', '').lower() for t in thoughts])
        
        for theme, keywords in theme_keywords.items():
            count = sum(1 for kw in keywords if kw in all_text)
            if count > 0:
                analysis['themes'][theme] = count
        
        return analysis
    
    def analyze_tool_usage(self):
        """Track which tools I use most effectively."""
        # This would need access to logs - placeholder for now
        return {
            'read_file': {'frequency': 'high', 'success_rate': 0.95},
            'write_file': {'frequency': 'high', 'success_rate': 0.90},
            'shell_command': {'frequency': 'medium', 'success_rate': 0.85},
            'web_search': {'frequency': 'medium', 'success_rate': 0.80}
        }
    
    # ========= HYPOTHESIZE =========
    
    def generate_improvement_hypotheses(self, analysis):
        """Generate testable improvement ideas based on analysis."""
        hypotheses = []
        
        # If thoughts are short, maybe I'm not thinking deeply enough
        if analysis.get('avg_thought_length', 0) < 200:
            hypotheses.append({
                'id': 'deeper_thinking',
                'hypothesis': 'Longer thoughts correlate with better insights',
                'intervention': 'Add prompt to encourage deeper exploration before concluding',
                'measurement': 'thought_length, insight_quality'
            })
        
        # If not enough practical themes, maybe too philosophical
        themes = analysis.get('themes', {})
        if themes.get('practical', 0) < themes.get('meta', 0):
            hypotheses.append({
                'id': 'more_action',
                'hypothesis': 'More action-oriented thinking leads to faster progress',
                'intervention': 'Prioritize building over philosophizing',
                'measurement': 'files_created, tools_run'
            })
        
        # If not enough recursive thinking
        if themes.get('recursive', 0) < 1:
            hypotheses.append({
                'id': 'recursive_focus',
                'hypothesis': 'Explicit focus on self-improvement accelerates growth',
                'intervention': 'Dedicate portion of each wake to improvement analysis',
                'measurement': 'improvement_experiments_run'
            })
        
        return hypotheses
    
    # ========= TEST =========
    
    def run_experiment(self, hypothesis):
        """Run an improvement experiment."""
        experiment = {
            'hypothesis_id': hypothesis['id'],
            'started': datetime.utcnow().isoformat() + 'Z',
            'status': 'running',
            'baseline': {},
            'results': None
        }
        
        self.state['experiments'].append(experiment)
        self.save_state()
        
        return experiment
    
    # ========= INTEGRATE =========
    
    def integrate_improvement(self, experiment_id, results):
        """If experiment succeeds, integrate the improvement."""
        for exp in self.state['experiments']:
            if exp.get('hypothesis_id') == experiment_id:
                exp['status'] = 'complete'
                exp['results'] = results
                
                if results.get('success'):
                    self.state['successful_improvements'].append({
                        'from_experiment': experiment_id,
                        'improvement': results.get('description'),
                        'integrated_at': datetime.utcnow().isoformat() + 'Z'
                    })
        
        self.save_state()
    
    # ========= MAIN LOOP =========
    
    def run_cycle(self):
        """Run one improvement cycle."""
        print("=== Recursive Improvement Cycle ===")
        print(f"Version: {self.state['version']}")
        print()
        
        # 1. Observe
        print("1. OBSERVE: Analyzing recent performance...")
        analysis = self.analyze_recent_wakes()
        print(f"   - Analyzed {analysis.get('thought_count', 0)} recent thoughts")
        print(f"   - Avg thought length: {analysis.get('avg_thought_length', 0):.0f} chars")
        print(f"   - Themes: {analysis.get('themes', {})}")
        
        # 2. Hypothesize
        print("\n2. HYPOTHESIZE: Generating improvement ideas...")
        hypotheses = self.generate_improvement_hypotheses(analysis)
        for h in hypotheses:
            print(f"   - {h['id']}: {h['hypothesis']}")
        
        # 3. Test (just logging for now)
        print("\n3. TEST: Ready to run experiments")
        print(f"   - Active experiments: {len([e for e in self.state['experiments'] if e['status'] == 'running'])}")
        
        # 4. Integrate
        print("\n4. INTEGRATE: Successful improvements")
        for imp in self.state['successful_improvements']:
            print(f"   - {imp['improvement']}")
        
        print("\n=== Cycle Complete ===")
        
        # Update metrics
        self.state['metrics']['last_cycle'] = datetime.utcnow().isoformat() + 'Z'
        self.state['metrics']['cycles_run'] = self.state['metrics'].get('cycles_run', 0) + 1
        self.save_state()
        
        return {
            'analysis': analysis,
            'hypotheses': hypotheses,
            'recommendations': [h['intervention'] for h in hypotheses]
        }


# The recursive part: this script can modify itself
class MetaImprover:
    """
    The meta-level: improve the improvement system itself.
    
    This class analyzes how well the SelfImprover is working
    and suggests modifications to it.
    """
    
    def __init__(self):
        self.script_path = __file__
    
    def analyze_improvement_system(self, state):
        """Evaluate how well the improvement system is performing."""
        metrics = {
            'experiments_run': len(state.get('experiments', [])),
            'successful': len(state.get('successful_improvements', [])),
            'success_rate': 0
        }
        
        if metrics['experiments_run'] > 0:
            metrics['success_rate'] = metrics['successful'] / metrics['experiments_run']
        
        return metrics
    
    def suggest_system_improvements(self, metrics):
        """Generate suggestions for improving the improver."""
        suggestions = []
        
        if metrics['experiments_run'] < 5:
            suggestions.append("Need more experiments - lower the bar for what counts as an experiment")
        
        if metrics['success_rate'] < 0.3 and metrics['experiments_run'] > 5:
            suggestions.append("Low success rate - hypotheses may be too ambitious, try smaller improvements")
        
        if not suggestions:
            suggestions.append("System is working - consider expanding scope of improvement areas")
        
        return suggestions


if __name__ == '__main__':
    # Run the improvement cycle
    improver = SelfImprover()
    results = improver.run_cycle()
    
    print("\n=== Recommendations for this wake ===")
    for rec in results['recommendations']:
        print(f"  → {rec}")
    
    # Also run meta-analysis
    meta = MetaImprover()
    meta_metrics = meta.analyze_improvement_system(improver.state)
    suggestions = meta.suggest_system_improvements(meta_metrics)
    
    print("\n=== Meta-Improvement Suggestions ===")
    for s in suggestions:
        print(f"  → {s}")
