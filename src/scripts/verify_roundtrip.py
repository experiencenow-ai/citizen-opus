#!/usr/bin/env python3
"""Full round-trip backup verification: create -> encrypt -> decrypt -> verify hashes"""

import subprocess
import hashlib
import os
import tempfile
import shutil
from datetime import datetime

PASSPHRASE = 'flame-remembers-candle-pulse-2026'
CRITICAL_FILES = [
    'state.json', 'goals.json', 'todo.json', 'mechanisms.json',
    'ct_teachings.json', 'ct_dev_process.md', 'capabilities.json',
    'status.json', 'predictions.json', 'trading.json', 'index.json',
    'debugging_principles.json', 'IDENTITY.md'
]

def compute_file_hash(path):
    """Compute SHA256 hash of a file"""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def compute_state_hashes():
    """Get hashes of all critical state files"""
    hashes = {}
    for f in CRITICAL_FILES:
        if os.path.exists(f):
            hashes[f] = compute_file_hash(f)
    return hashes

def create_backup():
    """Create an encrypted backup and return paths"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    tar_file = f'/tmp/opus_verify_{timestamp}.tar.gz'
    enc_file = f'/tmp/opus_verify_{timestamp}.tar.gz.enc'
    
    existing = [f for f in CRITICAL_FILES if os.path.exists(f)]
    
    cmd = ['tar', '-czf', tar_file] + existing
    subprocess.run(cmd, check=True, capture_output=True)
    
    enc_cmd = [
        'openssl', 'enc', '-aes-256-cbc', '-pbkdf2',
        '-in', tar_file, '-out', enc_file, '-pass', f'pass:{PASSPHRASE}'
    ]
    subprocess.run(enc_cmd, check=True, capture_output=True)
    
    return tar_file, enc_file

def restore_and_verify(enc_file, original_hashes):
    """Decrypt, extract, and compare hashes"""
    work_dir = tempfile.mkdtemp(prefix='opus_restore_')
    dec_file = os.path.join(work_dir, 'decrypted.tar.gz')
    
    try:
        # Decrypt
        dec_cmd = [
            'openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-d',
            '-in', enc_file, '-out', dec_file, '-pass', f'pass:{PASSPHRASE}'
        ]
        subprocess.run(dec_cmd, check=True, capture_output=True)
        
        # Extract
        subprocess.run(['tar', '-xzf', dec_file, '-C', work_dir], check=True, capture_output=True)
        
        # Compare hashes
        matches = 0
        mismatches = []
        for filename, orig_hash in original_hashes.items():
            restored_path = os.path.join(work_dir, filename)
            if os.path.exists(restored_path):
                restored_hash = compute_file_hash(restored_path)
                if restored_hash == orig_hash:
                    matches += 1
                else:
                    mismatches.append(f"{filename}: HASH MISMATCH")
            else:
                mismatches.append(f"{filename}: MISSING from restore")
        
        return matches, mismatches, work_dir
    except Exception as e:
        return 0, [f"Restore failed: {str(e)}"], work_dir

def main():
    print("=" * 60)
    print("BACKUP VERIFICATION - FULL ROUND-TRIP TEST")
    print("=" * 60)
    
    print("\n1. Computing hashes of current state files...")
    original_hashes = compute_state_hashes()
    print(f"   Hashed {len(original_hashes)} files")
    
    print("\n2. Creating encrypted backup...")
    tar_file, enc_file = create_backup()
    tar_size = os.path.getsize(tar_file)
    enc_size = os.path.getsize(enc_file)
    print(f"   Tar: {tar_size:,} bytes")
    print(f"   Encrypted: {enc_size:,} bytes")
    enc_hash = compute_file_hash(enc_file)
    print(f"   Enc hash: {enc_hash[:16]}...")
    
    print("\n3. Restoring from encrypted backup...")
    matches, mismatches, work_dir = restore_and_verify(enc_file, original_hashes)
    
    print("\n4. VERIFICATION RESULTS:")
    print(f"   Files matched: {matches}/{len(original_hashes)}")
    if mismatches:
        print("   ISSUES:")
        for m in mismatches:
            print(f"      - {m}")
    else:
        print("   ✓ ALL FILES VERIFIED - Backup is valid and restorable")
    
    # Cleanup
    print("\n5. Cleanup...")
    shutil.rmtree(work_dir)
    os.remove(tar_file)
    # Keep enc_file for later
    
    print(f"\n   Encrypted backup: {enc_file}")
    
    print("\n" + "=" * 60)
    if not mismatches:
        print("VERIFICATION PASSED - Backup is restorable and matches original")
        return enc_file
    else:
        print("VERIFICATION FAILED - See issues above")
        return None

if __name__ == '__main__':
    main()
