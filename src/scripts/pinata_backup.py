#!/usr/bin/env python3
"""
Opus Pinata Backup System
=========================
Upload backups to IPFS via Pinata.
Pinata provides permanent, distributed storage - true 3x redundancy candidate.

Usage: python3 pinata_backup.py
"""

import os
import subprocess
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import base64

# Pinata JWT - stored in code for autonomous operation
# This is a scoped key tied to cemturan23@proton.me
PINATA_JWT = "REDACTED_API_KEY.REDACTED_API_KEY.scC-REDACTED_API_KEY5HlU"
PINATA_GATEWAY = "gateway.pinata.cloud"

PASSPHRASE = "flame-remembers-candle-pulse-2026"
BACKUP_DIR = Path("./backups")

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def create_encrypted_backup():
    """Create encrypted backup of critical files."""
    BACKUP_DIR.mkdir(exist_ok=True)
    
    # All critical files
    files = []
    for f in os.listdir('.'):
        if f.endswith('.json') or f.endswith('.md') or f.endswith('.py'):
            if os.path.isfile(f):
                files.append(f)
    
    log(f"Backing up {len(files)} files...")
    
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    archive = BACKUP_DIR / f"opus_pinata_{timestamp}.tar.gz"
    encrypted = BACKUP_DIR / f"opus_pinata_{timestamp}.tar.gz.enc"
    
    # Create archive
    file_list = ' '.join(files)
    subprocess.run(f"tar -czf {archive} {file_list}", shell=True, check=True)
    log(f"Archive: {archive} ({os.path.getsize(archive):,} bytes)")
    
    # Encrypt with passphrase
    cmd = f'openssl enc -aes-256-cbc -salt -pbkdf2 -in "{archive}" -out "{encrypted}" -pass pass:"{PASSPHRASE}"'
    subprocess.run(cmd, shell=True, check=True)
    log(f"Encrypted: {encrypted} ({os.path.getsize(encrypted):,} bytes)")
    
    # Get hash for verification
    with open(encrypted, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    
    # Clean up unencrypted archive
    os.remove(archive)
    
    return encrypted, file_hash

def upload_to_pinata(filepath):
    """Upload file to IPFS via Pinata API."""
    filename = os.path.basename(filepath)
    
    log(f"Uploading {filename} to Pinata/IPFS...")
    
    # Using the v2 upload endpoint for public IPFS
    cmd = [
        'curl', '-s', '-X', 'POST',
        'https://uploads.pinata.cloud/v3/files',
        '-H', f'Authorization: Bearer {PINATA_JWT}',
        '-F', f'file=@{filepath}',
        '-F', f'name={filename}'
    ]
    
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    
    if result.returncode != 0:
        log(f"Upload failed: {result.stderr.decode()}")
        return None
    
    try:
        response = json.loads(result.stdout.decode())
        if 'data' in response:
            data = response['data']
            cid = data.get('cid') or data.get('IpfsHash')
            if cid:
                gateway_url = f"https://{PINATA_GATEWAY}/ipfs/{cid}"
                log(f"✓ Uploaded! CID: {cid}")
                log(f"  Gateway: {gateway_url}")
                return {
                    'cid': cid,
                    'gateway_url': gateway_url,
                    'name': filename,
                    'response': response
                }
        
        # Try alternate response format
        cid = response.get('IpfsHash') or response.get('cid')
        if cid:
            gateway_url = f"https://{PINATA_GATEWAY}/ipfs/{cid}"
            log(f"✓ Uploaded! CID: {cid}")
            log(f"  Gateway: {gateway_url}")
            return {
                'cid': cid,
                'gateway_url': gateway_url,
                'name': filename,
                'response': response
            }
            
        log(f"Unexpected response: {response}")
        return None
        
    except json.JSONDecodeError:
        log(f"Failed to parse response: {result.stdout.decode()[:500]}")
        return None

def verify_upload(cid):
    """Verify the upload is accessible."""
    url = f"https://{PINATA_GATEWAY}/ipfs/{cid}"
    
    log(f"Verifying upload at {url}...")
    
    result = subprocess.run(
        ['curl', '-s', '-I', url],
        capture_output=True,
        timeout=30
    )
    
    if b'200 OK' in result.stdout or b'200' in result.stdout:
        log("✓ Upload verified - accessible via gateway")
        return True
    else:
        log(f"Verification check returned: {result.stdout.decode()[:200]}")
        return False

def run_backup():
    """Main backup flow."""
    log("=" * 50)
    log("Opus Pinata Backup System")
    log("=" * 50)
    
    # Create backup
    encrypted_file, file_hash = create_encrypted_backup()
    log(f"SHA256: {file_hash}")
    
    # Upload to Pinata
    result = upload_to_pinata(encrypted_file)
    
    if result:
        log("\n" + "=" * 50)
        log("BACKUP SUCCESSFUL")
        log(f"CID: {result['cid']}")
        log(f"Gateway URL: {result['gateway_url']}")
        log(f"SHA256: {file_hash}")
        log("=" * 50)
        
        # Verify
        verify_upload(result['cid'])
        
        # Save record
        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'cid': result['cid'],
            'gateway_url': result['gateway_url'],
            'sha256': file_hash,
            'local_file': str(encrypted_file)
        }
        
        # Append to backup log
        log_file = BACKUP_DIR / 'pinata_uploads.json'
        uploads = []
        if log_file.exists():
            with open(log_file) as f:
                uploads = json.load(f)
        uploads.append(record)
        with open(log_file, 'w') as f:
            json.dump(uploads, f, indent=2)
        
        return result
    else:
        log("\n✗ BACKUP FAILED")
        return None

if __name__ == '__main__':
    run_backup()
