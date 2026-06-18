#!/usr/bin/env python3
"""
CSR Automation Toolkit
AI-Augmented Service Delivery Infrastructure

Automates customer query classification, response generation, Slack alerting,
and Google Sheets audit logging for enterprise customer service operations.
"""

import re
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from datetime import datetime
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configuration from .env
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
IMAP_SERVER = "imap.gmail.com"
GSHEETS_CREDENTIALS = json.loads(os.getenv("GSHEETS_CREDENTIALS", "{}"))
GSHEETS_ID = os.getenv("GSHEETS_ID", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

USE_OPENAI = bool(OPENAI_API_KEY)

# Standard response templates with follow-up flags
STANDARD_RESPONSES = [
    (["help", "assist", "support"], "response_help", 
     "I'd be happy to assist you with that.", False),
    (["inconvenience", "sorry", "apologize"], "response_apology", 
     "I apologize for the inconvenience this issue may have caused.", False),
    (["unhappy", "complaint"], "response_satisfaction", 
     "I'm sorry to hear that, and I'll be glad to help resolve this.", True),
    (["delay", "late", "pending"], "response_delay", 
     "I apologize for the delay. Let me address this for you right away.", True),
    (["warranty", "claim", "refund"], "response_warranty", 
     "For warranty or refund requests, I can help you with next steps.", True),
]


def classify_with_ai(query):
    """
    Use OpenAI to classify a query if API key is available.
    Falls back to keyword matching if AI fails or is not configured.
    """
    if not USE_OPENAI:
        return None
    
    try:
        import openai
        client = openai.Client(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user", 
                "content": f"Classify this customer query by intent: {query}"
            }],
            temperature=0,
            max_tokens=50,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI classification error: {e}")
        return None


def get_response(query):
    """
    Match query to a standard response template.
    Tries AI classification first, then keyword matching.
    Returns (response_text, follow_up_flag).
    """
    query_lower = query.lower()
    
    # Try AI classification first
    if USE_OPENAI:
        ai_result = classify_with_ai(query_lower)
        if ai_result:
            for keywords, _, response_text, follow_up in STANDARD_RESPONSES:
                if any(kw in ai_result.lower() for kw in keywords):
                    return response_text, follow_up
    
    # Fall back to keyword matching
    for keywords, _, response_text, follow_up in STANDARD_RESPONSES:
        if any(keyword in query_lower for keyword in keywords):
            return response_text, follow_up
    
    # Default response
    return "Thank you for reaching out. I'll do my best to assist you.", False


def log_to_sheets(query, response, customer_email=None, follow_up=False):
    """
    Log interaction to Google Sheets for audit trail and performance tracking.
    """
    if not GSHEETS_ID or not GSHEETS_CREDENTIALS:
        print("Google Sheets not configured. Skipping log.")
        return
    
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            GSHEETS_CREDENTIALS, scope
        )
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GSHEETS_ID).sheet1
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        follow_up_text = "Yes" if follow_up else "No"
        
        sheet.append_row([
            timestamp,
            customer_email or "N/A",
            query[:100],
            response[:100],
            follow_up_text
        ])
        print(f"Logged to Sheets: {timestamp}")
    except Exception as e:
        print(f"Failed to log to Sheets: {e}")


def send_slack_alert(query, response, follow_up=False):
    """
    Send real-time alert to Slack with follow-up tagging if needed.
    """
    if not SLACK_WEBHOOK_URL:
        print("Slack webhook not configured. Skipping alert.")
        return
    
    follow_up_tag = " [FOLLOW-UP NEEDED]" if follow_up else ""
    
    payload = {
        "text": f"*New CSR Query{follow_up_tag}*\n"
                f"Query: {query[:100]}\n"
                f"Response: {response[:100]}",
        "username": "CSR Automation Bot",
        "icon_emoji": ":robot_face:"
    }
    
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        print(f"Slack alert sent{follow_up_tag}")
    except Exception as e:
        print(f"Failed to send Slack alert: {e}")


def send_email(to, subject, body):
    """
    Send email auto-reply via SMTP.
    """
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("Email not configured. Skipping send.")
        return
    
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, [to], msg.as_string())
        print(f"Email sent to {to}")
    except Exception as e:
        print(f"Failed to send email to {to}: {e}")


def check_emails():
    """
    Check inbox for new emails, classify, and auto-reply with logging.
    """
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("Email not configured. Skipping email check.")
        return
    
    try:
        with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
            mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            mail.select("INBOX")
            _, data = mail.search(None, "UNSEEN")
            email_ids = data[0].split()
            
            if not email_ids:
                print("No new emails.")
                return
            
            for email_id in email_ids:
                _, msg_data = mail.fetch(email_id, "(RFC822)")
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                query = email_message.get_payload()
                if isinstance(query, list):
                    query = str(query[0])
                
                response, follow_up = get_response(query)
                customer_email = email_message.get('From', 'unknown')
                
                send_email(customer_email, "Re: Your Query", response)
                log_to_sheets(query, response, customer_email, follow_up)
                send_slack_alert(query, response, follow_up)
                
    except Exception as e:
        print(f"Failed to check emails: {e}")


class CSRAutomationApp:
    """
    Desktop GUI for CSR agents to input queries and get auto-responses.
    """
    
    def __init__(self, root):
        self.root = root
        self.root.title("CSR Automation Toolkit")
        self.root.geometry("900x700")
        
        # Query input
        tk.Label(root, text="Customer Query:", font=("Helvetica", 10, "bold")).pack(pady=5)
        self.query_input = scrolledtext.ScrolledText(root, height=5, width=100)
        self.query_input.pack(pady=5, padx=10)
        
        # Response output
        tk.Label(root, text="Auto-Response:", font=("Helvetica", 10, "bold")).pack(pady=5)
        self.response_output = scrolledtext.ScrolledText(root, height=10, width=100)
        self.response_output.pack(pady=5, padx=10)
        
        # Follow-up indicator
        self.follow_up_label = tk.Label(root, text="", font=("Helvetica", 9))
        self.follow_up_label.pack(pady=5)
        
        # Buttons
        button_frame = tk.Frame(root)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Generate Response", 
                 command=self.generate_response, bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Check Emails", 
                 command=self.check_emails_thread, bg="#2196F3", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Exit", 
                 command=root.quit, bg="#f44336", fg="white").pack(side=tk.LEFT, padx=5)
        
        # Status indicator
        self.status_label = tk.Label(root, text="Ready", fg="green", font=("Helvetica", 9))
        self.status_label.pack(pady=5)
    
    def generate_response(self):
        """Handle manual query entry from GUI."""
        query = self.query_input.get("1.0", tk.END).strip()
        if not query:
            messagebox.showerror("Error", "Please enter a query.")
            return
        
        response, follow_up = get_response(query)
        self.response_output.delete("1.0", tk.END)
        self.response_output.insert("1.0", response)
        
        if follow_up:
            self.follow_up_label.config(text="[FOLLOW-UP NEEDED]", fg="red")
        else:
            self.follow_up_label.config(text="No follow-up required", fg="green")
        
        log_to_sheets(query, response, follow_up=follow_up)
        send_slack_alert(query, response, follow_up)
        self.status_label.config(text="Response generated and logged.", fg="blue")
    
    def check_emails_thread(self):
        """Check emails in background thread."""
        threading.Thread(target=check_emails, daemon=True).start()
        self.status_label.config(text="Checking emails...", fg="orange")


def main():
    """Main entry point."""
    root = tk.Tk()
    app = CSRAutomationApp(root)
    
    def check_emails_periodically():
        """Auto-check emails every 5 minutes."""
        check_emails()
        root.after(300000, check_emails_periodically)
    
    # Start periodic email check
    check_emails_periodically()
    
    root.mainloop()


if __name__ == "__main__":
    main()
