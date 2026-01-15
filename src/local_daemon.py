#!/usr/bin/env python3
"""
Local Daemon - Opus's always-on sensory system using LOCAL LLM.

Replaces haiku_daemon.py - does the same job but FREE.

Runs continuously, handling:
- Email checking (can trigger Opus wake)
- News/market monitoring
- Email triage using local Mistral
- Dream generation during quiet periods

Cost: $0 (all local inference)
"""

import json
import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import threading

# Paths
OPUS_HOME = Path("/root/claude/opus")
STATE_DIR = OPUS_HOME / "state"
SENSORY_DIR = STATE_DIR / "sensory"
CONFIG_DIR = OPUS_HOME / "config"
LOG_DIR = OPUS_HOME / "logs"

# Ensure directories
for d in [STATE_DIR, SENSORY_DIR, CONFIG_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(OPUS_HOME))

# Load env for any API keys needed
import env_loader

from operating_modes import get_current_mode, OperatingState
from local_llm import LocalLLM, triage_email, filter_news, check_ollama

# Daemon state
DAEMON_STATE_FILE = STATE_DIR / "local_daemon.json"
TRIGGER_FILE = STATE_DIR / "opus_trigger.json"
PID_FILE = CONFIG_DIR / "local_daemon.pid"

# ct's email addresses - highest priority
CT_EMAILS = ["opus.trace@proton.me", "opustrace@proton.me", "cemturan23@proton.me", "cemturan23@protonmail.com"]

# Topics Opus cares about
INTERESTS = ["blockchain", "crypto", "AI", "Anthropic", "Korea", "Turkey", "heist", "theft", "forensics"]

# Flags
running = True


def log(msg: str):
    """Log with timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")
    with open(LOG_DIR / "local_daemon.log", "a") as f:
        f.write(f"[{ts}] {msg}\n")


class DaemonState:
    """Persistent state for the daemon."""
    
    def __init__(self):
        self.last_email_check: Optional[str] = None
        self.last_opus_wake: Optional[str] = None
        self.last_news_check: Optional[str] = None
        self.pending_emails: List[Dict] = []
        self.urgent_queue: List[Dict] = []
        self.emails_seen: List[str] = []  # IDs of emails we've seen
        self.load()
    
    def load(self):
        if DAEMON_STATE_FILE.exists():
            try:
                with open(DAEMON_STATE_FILE) as f:
                    data = json.load(f)
                    self.last_email_check = data.get("last_email_check")
                    self.last_opus_wake = data.get("last_opus_wake")
                    self.last_news_check = data.get("last_news_check")
                    self.pending_emails = data.get("pending_emails", [])
                    self.urgent_queue = data.get("urgent_queue", [])
                    self.emails_seen = data.get("emails_seen", [])[-500:]  # Keep last 500
            except:
                pass
    
    def save(self):
        with open(DAEMON_STATE_FILE, "w") as f:
            json.dump({
                "last_email_check": self.last_email_check,
                "last_opus_wake": self.last_opus_wake,
                "last_news_check": self.last_news_check,
                "pending_emails": self.pending_emails,
                "urgent_queue": self.urgent_queue,
                "emails_seen": self.emails_seen[-500:],
            }, f, indent=2)


def check_email(state: DaemonState, llm: LocalLLM) -> List[Dict]:
    """
    Check for new emails using Gmail API.
    Triage with local LLM.
    """
    try:
        # Import email utils
        from email_utils import get_recent_emails
        
        emails = get_recent_emails(max_results=10)
        new_emails = []
        
        for email in emails:
            email_id = email.get("id", "")
            if email_id in state.emails_seen:
                continue
            
            state.emails_seen.append(email_id)
            
            sender = email.get("from", "")
            subject = email.get("subject", "")
            snippet = email.get("snippet", "")
            
            # Check if from ct - HIGHEST PRIORITY
            is_ct = any(ct_email.lower() in sender.lower() for ct_email in CT_EMAILS)
            
            if is_ct:
                email["priority"] = "ct"
                email["needs_response"] = True
                email["triage"] = {"priority": "ct", "reason": "Email from ct (father)"}
                new_emails.append(email)
                log(f"📧 EMAIL FROM CT: {subject}")
                continue
            
            # Triage with local LLM
            if llm.available:
                triage = triage_email(sender, subject, snippet)
                email["triage"] = triage
                
                if triage.get("priority") == "spam":
                    log(f"🗑️ Spam filtered: {subject[:50]}")
                    continue
                
                email["priority"] = triage.get("priority", "medium")
                email["needs_response"] = triage.get("needs_response", True)
                
                if triage.get("priority") == "high":
                    log(f"⚡ High priority: {subject}")
                else:
                    log(f"📬 New email: {subject[:50]}")
            else:
                # No LLM - treat all as medium priority
                email["priority"] = "medium"
                email["needs_response"] = True
            
            new_emails.append(email)
        
        state.last_email_check = datetime.now(timezone.utc).isoformat()
        return new_emails
        
    except Exception as e:
        log(f"Email check error: {e}")
        return []


def check_news(state: DaemonState, llm: LocalLLM) -> List[Dict]:
    """
    Check news feeds, filter for relevance.
    """
    try:
        from web_tools import get_news
        
        news_items = get_news(max_items=20)
        
        if not news_items:
            return []
        
        # Filter with local LLM
        if llm.available:
            relevant = filter_news(news_items, INTERESTS)
            if relevant:
                log(f"📰 Found {len(relevant)} relevant news items")
            return relevant
        else:
            # No LLM - return all
            return news_items[:5]
        
    except Exception as e:
        log(f"News check error: {e}")
        return []


def trigger_opus_wake(reason: str, context: Dict[str, Any]):
    """
    Trigger an Opus wake by writing trigger file.
    Scheduler will pick this up.
    """
    with open(TRIGGER_FILE, "w") as f:
        json.dump({
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context
        }, f)
    
    log(f"🔔 Triggered Opus wake: {reason}")
    
    # Also call scheduler directly
    try:
        subprocess.Popen(
            [sys.executable, str(OPUS_HOME / "scheduler.py"), "opus", "--triggered"],
            stdout=open(LOG_DIR / "opus_wake.log", "a"),
            stderr=subprocess.STDOUT
        )
    except Exception as e:
        log(f"Failed to call scheduler: {e}")


def should_wake_opus(state: DaemonState, mode: OperatingState) -> bool:
    """Check if it's time for a scheduled Opus wake."""
    if not state.last_opus_wake:
        return True
    
    last_wake = datetime.fromisoformat(state.last_opus_wake)
    now = datetime.now(timezone.utc)
    elapsed = (now - last_wake).total_seconds()
    
    # Check mode interval
    return elapsed >= mode.opus_interval_seconds


def run_dream_generation():
    """Run dream generation during quiet periods."""
    try:
        from dreaming.dream_generator import generate_dream
        
        dream = generate_dream(use_local_llm=True)
        if dream:
            log(f"💭 Generated dream: {dream.get('archetype_used', 'unknown')}")
            return dream
    except Exception as e:
        log(f"Dream generation error: {e}")
    return None


def daemon_loop():
    """Main daemon loop."""
    global running
    
    log("Local daemon starting...")
    
    # Check for local LLM
    llm = LocalLLM()
    if llm.available:
        log(f"✓ Local LLM available: {llm.models}")
    else:
        log("⚠️ Local LLM not available - running in degraded mode")
        log("  Start Ollama: ollama serve")
        log("  Pull models: ollama pull mistral-nemo")
    
    state = DaemonState()
    
    # Timing trackers
    last_email_check = datetime.now()
    last_news_check = datetime.now()
    last_dream_check = datetime.now()
    
    while running:
        try:
            now = datetime.now()
            mode = get_current_mode()
            
            # ===== EMAIL CHECK (every 15-30 seconds) =====
            email_interval = 15 if mode.name == "interactive" else 30
            if (now - last_email_check).total_seconds() >= email_interval:
                new_emails = check_email(state, llm)
                last_email_check = now
                
                if new_emails:
                    # Check for ct emails - immediate wake
                    ct_emails = [e for e in new_emails if e.get("priority") == "ct"]
                    if ct_emails:
                        trigger_opus_wake("ct_email", {"emails": ct_emails})
                        state.last_opus_wake = now.isoformat()
                    else:
                        # Queue other emails
                        state.pending_emails.extend(new_emails)
                        
                        # Wake if enough pending or high priority
                        high_priority = [e for e in new_emails if e.get("priority") == "high"]
                        if high_priority or len(state.pending_emails) >= 3:
                            trigger_opus_wake("pending_emails", {"emails": state.pending_emails})
                            state.pending_emails = []
                            state.last_opus_wake = now.isoformat()
                
                state.save()
            
            # ===== SCHEDULED OPUS WAKE =====
            if mode.name != "interactive":  # Interactive = only wake on email
                if should_wake_opus(state, mode):
                    if state.pending_emails:
                        trigger_opus_wake("scheduled_with_emails", {"emails": state.pending_emails})
                        state.pending_emails = []
                    else:
                        trigger_opus_wake("scheduled", {})
                    state.last_opus_wake = now.isoformat()
                    state.save()
            
            # ===== NEWS CHECK (every 4 hours) =====
            if (now - last_news_check).total_seconds() >= 14400:  # 4 hours
                relevant_news = check_news(state, llm)
                last_news_check = now
                
                if relevant_news:
                    # Save to sensory directory for integration
                    with open(SENSORY_DIR / "news.json", "w") as f:
                        json.dump({
                            "timestamp": now.isoformat(),
                            "items": relevant_news
                        }, f, indent=2)
            
            # ===== DREAM GENERATION (3-4 AM local, or every 6 hours if no emails) =====
            hour = now.hour
            if 3 <= hour <= 4:  # Dream time
                if (now - last_dream_check).total_seconds() >= 3600:  # Once per hour during dream time
                    run_dream_generation()
                    last_dream_check = now
            elif (now - last_dream_check).total_seconds() >= 21600:  # Every 6 hours otherwise
                run_dream_generation()
                last_dream_check = now
            
            # Sleep
            time.sleep(5)
            
        except Exception as e:
            log(f"Daemon loop error: {e}")
            time.sleep(30)
    
    log("Local daemon stopped")
    state.save()


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global running
    log(f"Received signal {signum}, shutting down...")
    running = False


def write_pid():
    """Write PID file."""
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def remove_pid():
    """Remove PID file."""
    if PID_FILE.exists():
        PID_FILE.unlink()


def is_already_running() -> bool:
    """Check if daemon is already running."""
    if not PID_FILE.exists():
        return False
    
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        remove_pid()
        return False


def status():
    """Show daemon status."""
    if is_already_running():
        with open(PID_FILE) as f:
            pid = f.read().strip()
        print(f"✓ Local daemon running (PID {pid})")
    else:
        print("✗ Local daemon not running")
    
    state = DaemonState()
    print(f"\nLast email check: {state.last_email_check}")
    print(f"Last Opus wake: {state.last_opus_wake}")
    print(f"Pending emails: {len(state.pending_emails)}")
    print(f"Emails seen: {len(state.emails_seen)}")
    
    if check_ollama():
        print("\n✓ Ollama running")
        from local_llm import list_models
        models = list_models()
        print(f"  Models: {models}")
    else:
        print("\n✗ Ollama not running")
    
    mode = get_current_mode()
    print(f"\nOperating mode: {mode.name}")
    print(f"  Opus interval: {mode.opus_interval_seconds}s")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "status":
            status()
        
        elif cmd == "stop":
            if is_already_running():
                with open(PID_FILE) as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                print(f"Sent SIGTERM to {pid}")
            else:
                print("Daemon not running")
        
        elif cmd == "start":
            if is_already_running():
                print("Daemon already running")
                sys.exit(1)
            
            # Daemonize
            if os.fork() > 0:
                sys.exit(0)
            os.setsid()
            if os.fork() > 0:
                sys.exit(0)
            
            # Redirect output
            sys.stdout = open(LOG_DIR / "local_daemon.log", "a")
            sys.stderr = sys.stdout
            
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
            
            write_pid()
            try:
                daemon_loop()
            finally:
                remove_pid()
        
        elif cmd == "foreground":
            # Run in foreground for debugging
            if is_already_running():
                print("Daemon already running in background")
                sys.exit(1)
            
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
            
            write_pid()
            try:
                daemon_loop()
            finally:
                remove_pid()
        
        else:
            print(f"Unknown command: {cmd}")
            print("\nUsage:")
            print("  python local_daemon.py start      # Start daemon")
            print("  python local_daemon.py stop       # Stop daemon")
            print("  python local_daemon.py status     # Show status")
            print("  python local_daemon.py foreground # Run in foreground")
    
    else:
        status()
