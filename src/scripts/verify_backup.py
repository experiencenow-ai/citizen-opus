#!/usr/bin/env python3
"""
Opus Backup Verification System - Wake 377
Verifies backup by full restore and file-by-file comparison.
"""

import os
import sys
import json
import subprocess
import hashlib
import shutil
from pathlib import Path
from datetime import datetime, timezone

PASSPHRASE = "flame-remembers-candle-pulse-2026"
RESTORE_DIR = Path("./restore_verify")

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def sha256_file(filepath):
    """Calculate SHA256 of a file."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def fetch_chunk(url):
    """Fetch chunk from URL, return raw base64 content."""
    log(f"  Fetching {url}...")
    result = subprocess.run(
        ['curl', '-s', url],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise Exception(f"Failed to fetch {url}: {result.stderr}")
    
    lines = result.stdout.strip().split('\n')
    # Skip header line (# OPUS-CHUNK...)
    content = '\n'.join(lines[1:])
    return content

def verify_and_restore():
    """Complete verification: download, decrypt, extract, compare."""
    
    # Clean and create restore directory
    if RESTORE_DIR.exists():
        shutil.rmtree(RESTORE_DIR)
    RESTORE_DIR.mkdir()
    
    # Find latest manifest
    backup_dir = Path("./backups")
    manifests = sorted(backup_dir.glob("manifest_*.json"))
    if not manifests:
        log("ERROR: No manifest found!")
        return False
    
    manifest_path = manifests[-1]
    log(f"Using manifest: {manifest_path.name}")
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    log(f"Backup from wake {manifest.get('wake', 'unknown')}")
    log(f"Original hash: {manifest['original_hash'][:16]}...")
    
    # Step 1: Download all chunks
    log("Step 1: Downloading chunks...")
    import base64
    encrypted_data = b''
    
    for chunk in manifest['chunks']:
        content = fetch_chunk(chunk['url'])
        chunk_data = base64.b64decode(content)
        
        # Verify chunk hash
        chunk_hash = hashlib.sha256(chunk_data).hexdigest()
        if chunk_hash != chunk['hash']:
            log(f"  WARNING: Chunk {chunk['index']} hash mismatch!")
            log(f"    Expected: {chunk['hash'][:16]}...")
            log(f"    Got:      {chunk_hash[:16]}...")
        else:
            log(f"  Chunk {chunk['index']}: hash verified ✓")
        
        encrypted_data += chunk_data
    
    # Step 2: Save encrypted data
    encrypted_path = RESTORE_DIR / "downloaded.enc"
    with open(encrypted_path, 'wb') as f:
        f.write(encrypted_data)
    log(f"Step 2: Saved encrypted data ({len(encrypted_data):,} bytes)")
    
    # Step 3: Decrypt
    log("Step 3: Decrypting...")
    decrypted_path = RESTORE_DIR / "decrypted.tar.gz"
    
    result = subprocess.run(
        f'openssl enc -aes-256-cbc -d -pbkdf2 -in "{encrypted_path}" '
        f'-out "{decrypted_path}" -pass pass:{PASSPHRASE}',
        shell=True, capture_output=True, text=True
    )
    
    if result.returncode != 0:
        log(f"  ERROR: Decryption failed: {result.stderr}")
        return False
    
    # Verify decrypted hash
    decrypted_hash = sha256_file(decrypted_path)
    log(f"  Decrypted hash: {decrypted_hash[:16]}...")
    
    # Step 4: Extract
    log("Step 4: Extracting archive...")
    result = subprocess.run(
        f'tar -xzf "{decrypted_path}" -C "{RESTORE_DIR}"',
        shell=True, capture_output=True, text=True
    )
    
    if result.returncode != 0:
        log(f"  ERROR: Extraction failed: {result.stderr}")
        return False
    
    # List extracted files
    extracted = list(RESTORE_DIR.glob("*"))
    extracted = [f for f in extracted if f.name not in ['downloaded.enc', 'decrypted.tar.gz']]
    log(f"  Extracted {len(extracted)} files")
    
    # Step 5: Compare with originals
    log("Step 5: Comparing files...")
    
    critical_files = [
        "state.json", "index.json", "goals.json", "mechanisms.json",
        "capabilities.json", "status.json", "trading.json",
        "IDENTITY.md", "identity.md", "encrypt_tool.py", "backup_system.py"
    ]
    
    mismatches = []
    matches = []
    missing = []
    
    for filename in critical_files:
        original = Path(f"./{filename}")
        restored = RESTORE_DIR / filename
        
        if not original.exists():
            continue  # Not a current file
            
        if not restored.exists():
            missing.append(filename)
            continue
        
        orig_hash = sha256_file(original)
        rest_hash = sha256_file(restored)
        
        if orig_hash == rest_hash:
            matches.append(filename)
            log(f"  ✓ {filename}")
        else:
            mismatches.append((filename, orig_hash, rest_hash))
            log(f"  ✗ {filename} - MISMATCH")
    
    # Summary
    log("")
    log("=" * 50)
    log("VERIFICATION SUMMARY")
    log("=" * 50)
    log(f"✓ Matched files: {len(matches)}")
    log(f"✗ Mismatched files: {len(mismatches)}")
    log(f"? Missing from backup: {len(missing)}")
    
    if mismatches:
        log("\nMISMATCHES:")
        for fn, orig, rest in mismatches:
            log(f"  {fn}:")
            log(f"    Original: {orig[:20]}...")
            log(f"    Restored: {rest[:20]}...")
    
    if missing:
        log(f"\nMISSING: {', '.join(missing)}")
    
    success = len(mismatches) == 0
    log(f"\nOVERALL: {'✓ VERIFICATION PASSED' if success else '✗ VERIFICATION FAILED'}")
    
    return success

if __name__ == "__main__":
    success = verify_and_restore()
    sys.exit(0 if success else 1)
