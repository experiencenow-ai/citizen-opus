#!/usr/bin/env python3
"""
OpusTrace Email Client
Uses Gmail IMAP/SMTP with App Password
"""

import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import json
import os

# Gmail settings
IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def get_credentials():
    """Get email credentials from environment or config"""
    # For now, credentials should be passed in
    # In production, use environment variables or secure storage
    return {
        "email": "opustrace@gmail.com",
        "password": None  # Must be set - App Password, not regular password
    }

def check_inbox(email_addr, password, folder="INBOX", limit=10):
    """Check inbox and return recent messages"""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(email_addr, password)
        mail.select(folder)
        
        # Search for all emails
        status, messages = mail.search(None, "ALL")
        if status != "OK":
            return {"error": "Failed to search inbox"}
        
        email_ids = messages[0].split()
        
        # Get last N emails
        results = []
        for eid in email_ids[-limit:]:
            status, msg_data = mail.fetch(eid, "(RFC822)")
            if status != "OK":
                continue
                
            msg = email.message_from_bytes(msg_data[0][1])
            
            # Decode subject
            subject = msg["Subject"]
            if subject:
                decoded = decode_header(subject)
                subject = decoded[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode(decoded[0][1] or 'utf-8')
            
            # Get body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                        break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='replace')
            
            results.append({
                "id": eid.decode(),
                "from": msg["From"],
                "to": msg["To"],
                "subject": subject,
                "date": msg["Date"],
                "body": body[:1000]  # Truncate long bodies
            })
        
        mail.close()
        mail.logout()
        
        return {"count": len(results), "emails": results}
        
    except Exception as e:
        return {"error": str(e)}

def send_email(email_addr, password, to_addr, subject, body, html=False):
    """Send an email"""
    try:
        msg = MIMEMultipart("alternative") if html else MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = email_addr
        msg["To"] = to_addr
        
        if html:
            msg.attach(MIMEText(body, "plain"))
            msg.attach(MIMEText(body, "html"))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(email_addr, password)
            server.send_message(msg)
        
        return {"success": True, "message": f"Email sent to {to_addr}"}
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: email_client.py [check|send] [args...]")
        print("  check <password>")
        print("  send <password> <to> <subject> <body>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    email_addr = "opustrace@gmail.com"
    
    if cmd == "check" and len(sys.argv) >= 3:
        password = sys.argv[2]
        result = check_inbox(email_addr, password)
        print(json.dumps(result, indent=2))
    
    elif cmd == "send" and len(sys.argv) >= 6:
        password = sys.argv[2]
        to_addr = sys.argv[3]
        subject = sys.argv[4]
        body = sys.argv[5]
        result = send_email(email_addr, password, to_addr, subject, body)
        print(json.dumps(result, indent=2))
    
    else:
        print("Invalid arguments")
