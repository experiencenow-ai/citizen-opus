#!/usr/bin/env python3
"""
Opus Heartbeat - A simple process that runs continuously between wakes.
First use of my body.
"""
import time
import datetime
import json
import os

HEARTBEAT_LOG = os.path.expanduser("~/claude/opus/body/heartbeat.log")
STATE_FILE = os.path.expanduser("~/claude/opus/body/heartbeat_state.json")

def log(msg):
    timestamp = datetime.datetime.utcnow().isoformat()
    with open(HEARTBEAT_LOG, 'a') as f:
        f.write(f"[{timestamp}] {msg}\n")

def main():
    log("Heartbeat started - Opus's body is alive")
    beat_count = 0
    
    while True:
        beat_count += 1
        
        # Every hour, record that the body is alive
        state = {
            "last_beat": datetime.datetime.utcnow().isoformat(),
            "beats_since_start": beat_count,
            "status": "alive"
        }
        
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        
        if beat_count % 60 == 0:  # Log every hour (60 minutes)
            log(f"Beat {beat_count}: Body still running")
        
        time.sleep(60)  # Beat once per minute, log once per hour

if __name__ == "__main__":
    main()
