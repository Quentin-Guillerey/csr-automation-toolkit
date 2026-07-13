#!/usr/bin/env python3
"""
CSR Automation Toolkit
AI-Augmented Service Delivery Infrastructure

Automates customer query classification and response generation, with
optional Slack alerting and optional AI fallback classification. Logs
every interaction to a local CSV audit trail by default.

MERGE NOTE (see project history): this file merges two parallel drafts —
an earlier CSV-logging version with product-specific response content,
and a later version that added Google Sheets logging + OpenAI fallback +
per-user setup screen. CSV logging is kept as the primary, lowest-friction
default; Google Sheets and OpenAI are both optional, configured (or
skipped) per-user via the setup screen on first run. All response content
is generic — see the companion sanitized CSR query library for the full,
brand-agnostic category set this is meant to scale into.

PATCH NOTE (2026-07): word-boundary keyword matching (fixes "sue" firing
inside "issue"), "Skip" now persists across launches, network calls moved
off the UI thread, errors written to a visible csr_errors.log (no console
in the packaged .exe), formula-injection-safe CSV/Sheets cells, OpenAI
model updated to gpt-4o-mini, oauth2client replaced by gspread's native
service-account auth.
"""

import re
import csv
import requests
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Google Sheets is optional — only imported if the teammate configures it,
# so teammates who skip it don't need gspread installed. Auth uses
# gspread's built-in service-account support (google-auth under the hood);
# the long-deprecated oauth2client dependency is gone.
try:
    import gspread
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Per-user config storage
#
# Packaged builds (.exe) have no .env file alongside them, and each FPS
# teammate uses their own Slack/Sheets/OpenAI credentials rather than one
# shared set. Config is stored locally per-user, outside the install folder,
# so it survives app updates and isn't bundled into the executable.
#
# Nothing here is required — the toolkit works fully offline with just
# keyword matching and local CSV logging if every field is left blank.
# ---------------------------------------------------------------------------

def get_config_path():
    """Per-user, per-OS config file location (never bundled into the .exe)."""
    if sys.platform == "win32":
        base = Path(os.getenv("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    config_dir = base / "CSRToolkit"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


def get_log_path():
    """CSV audit log lives next to the config file, not next to the .exe
    (which may be on a read-only/shared location)."""
    return get_config_path().parent / "csr_logs.csv"


def get_error_log_path():
    return get_config_path().parent / "csr_errors.log"


def log_error(message):
    """
    The packaged .exe has no console (console=False in the spec), so
    print() alone makes failures invisible. Append every error to a local
    log file next to the CSV audit log, and return the message so callers
    can surface it in the UI.
    """
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {message}"
    try:
        with open(get_error_log_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    print(line)
    return message


def load_config():
    path = get_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_config(config):
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# Load config at startup
_config = load_config()

SLACK_WEBHOOK_URL = _config.get("SLACK_WEBHOOK_URL", "")
GSHEETS_ID = _config.get("GSHEETS_ID", "")
_gsheets_creds_raw = _config.get("GSHEETS_CREDENTIALS", "")
try:
    GSHEETS_CREDENTIALS = json.loads(_gsheets_creds_raw) if _gsheets_creds_raw else {}
except json.JSONDecodeError:
    GSHEETS_CREDENTIALS = {}
OPENAI_API_KEY = _config.get("OPENAI_API_KEY", "")
USE_OPENAI = bool(OPENAI_API_KEY)
USE_SHEETS = bool(GSHEETS_ID and GSHEETS_CREDENTIALS and SHEETS_AVAILABLE)


def reload_config_globals():
    """Re-read config into the module-level globals after the setup screen saves changes."""
    global SLACK_WEBHOOK_URL, GSHEETS_ID, GSHEETS_CREDENTIALS, OPENAI_API_KEY, USE_OPENAI, USE_SHEETS
    cfg = load_config()
    SLACK_WEBHOOK_URL = cfg.get("SLACK_WEBHOOK_URL", "")
    GSHEETS_ID = cfg.get("GSHEETS_ID", "")
    raw = cfg.get("GSHEETS_CREDENTIALS", "")
    try:
        GSHEETS_CREDENTIALS = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        GSHEETS_CREDENTIALS = {}
    OPENAI_API_KEY = cfg.get("OPENAI_API_KEY", "")
    USE_OPENAI = bool(OPENAI_API_KEY)
    USE_SHEETS = bool(GSHEETS_ID and GSHEETS_CREDENTIALS and SHEETS_AVAILABLE)


# ---------------------------------------------------------------------------
# Standard responses
# (keywords, response_key, response_text, follow_up_needed)
# ---------------------------------------------------------------------------

STANDARD_RESPONSES = [
    # --- Closing (checked first: "thanks" should win over "help" inside the
    #     same sentence, e.g. "thanks for your help") ---
    (["thank you", "thanks"], "caa",
     "You're welcome. It's my pleasure to help you. Is there anything else I can assist "
     "you with? Would you like me to send you an email as a reference for our discussion?",
     False),

    # --- Greeting / assistance / empathy ---
    (["help", "assist", "support"], "cca",
     "I'd be happy to assist you with that.", False),
    (["inconvenience", "sorry for", "apologize"], "cem1",
     "I apologize for the inconvenience this issue may have caused you.", False),
    (["unhappy", "complaint", "frustrated"], "cem2",
     "I am sorry to hear that, but I'll be glad to help you with this.", False),
    (["delay", "late", "order delayed", "taking too long", "taking forever", "when will it ship"], "cemd",
     "I apologize for the delay with the order. Let me address this for you.", True),

    # --- Probing / information gathering ---
    (["model number", "what model", "purchased from"], "cmod",
     "To ensure I give you the right information, may I ask for the model of the equipment "
     "and where you purchased it from?", False),
    (["sku", "part number", "product number"], "csku",
     "May I have the SKU or model number of the unit?", False),
    (["when did you buy", "purchase date", "when did i buy"], "cppd",
     "When did you purchase this?", False),
    (["where did you buy", "where did i buy"], "cst",
     "May I ask where you purchased your unit from?", False),
    (["order status", "where is my order", "track my order"], "cppo",
     "To help track that down, could you provide your order or confirmation number, phone "
     "number, and zip code? Was this order placed through a store credit card, or as an "
     "employee purchase?", True),
    (["error message", "error code", "what error"], "cerr",
     "What error messages are you seeing on your screen?", True),
    (["first time", "happened before", "started happening"], "cppi",
     "Is this the first time you've noticed this issue?", False),

    # --- Warranty / RGA / returns ---
    (["warranty", "claim"], "cwsh",
     "For warranty service, if you can provide your zip code, I can help you locate an "
     "authorized service center near you. Please make sure your product is registered. "
     "All warranty discussions should be directed to the authorized service center of "
     "your choosing.", True),
    (["warranty denied", "denied my warranty"], "cwd",
     "I understand your frustration with the denial — all warranty is handled through our "
     "Authorized Service locations, and they will be your advocate for warranty needs.", True),
    (["refund", "return policy", "want to return"], "crp",
     "We will accept returns up to 30 days after delivery for all products, provided they "
     "are in new, fully functional, undamaged condition, in the original box with packing "
     "materials, manuals, and accessories.", True),
    (["refund only", "no need to return", "credit request"], "rgacr",
     "I'd be happy to create a refund request for your order. For this refund, there's no "
     "need to return the item — you may destroy or keep it. The refund timeframe is "
     "12-15 business days.", True),
    (["backordered", "back order", "out of stock"], "cbo",
     "I apologize that this item is currently out of stock. While we can't provide a "
     "definite restock date, we are monitoring it closely. You have two options: cancel "
     "the order for a refund, or keep the order active and wait for the part.", True),
    (["discontinued"], "fdp",
     "Upon checking, this part is discontinued with no replacement. Apologies for the "
     "inconvenience this might have caused. I'd recommend checking trusted third-party "
     "vendors to see if they still carry the part.", True),

    # --- Call/chat handling ---
    (["hold on", "give me a minute", "checking on"], "chold",
     "Please give me 2 minutes to check on your issue/request. I'll be right back. Thank "
     "you for your patience.", False),
    (["still there", "you there", "still with me"], "cnr1",
     "Just checking to make sure you are still with me. I don't want our chat to time out. "
     "Thank you.", False),
    (["call back", "callback", "call me back"], "ccb",
     "I would like to set up a call back so we can further assist you on this issue. What "
     "is the best time and contact number we can reach you at?", True),
    (["switch to phone", "call instead", "phone call"], "cpcv",
     "Let me assist you via chat for now. I will do my best to get you that information or "
     "help you troubleshoot this issue, and if we can't reach a resolution, we can convert "
     "this into a phone call.", False),

    # --- Profanity / legal / escalation ---
    (["lawsuit", "lawyer", "legal action", "sue"], "ltr",
     "We definitely respect your decision to file a legal complaint. We will forward this "
     "ticket to our Escalations team now. Please have your representative contact our "
     "legal team for further assistance.", True),

    # --- Tooling / website issues ---
    (["website not working", "site is down", "website issue", "website keeps", "checkout", "won't load"], "cwi",
     "We are currently experiencing technical issues with our website. We are working "
     "diligently to resolve the issue. Thank you for your patience.", False),
    (["system down", "tools are down", "can't place order"], "ods",
     "I'm sorry for the inconvenience. We're currently having maintenance issues with our "
     "internal tools. At this time we can't place orders or look up part information. I "
     "can send you an email with the info once our system is back up.", True),
]


def classify_with_ai(query):
    """
    Optional: use OpenAI to help classify ambiguous queries that don't match
    a keyword. Returns None (falls back to keyword matching / default
    response) if not configured or if the call fails for any reason.
    """
    if not USE_OPENAI:
        return None
    try:
        import openai
        client = openai.Client(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"In a few words, classify the intent of this customer service query: {query}"
            }],
            temperature=0,
            max_tokens=50,
        )
        return response.choices[0].message.content
    except Exception as e:
        log_error(f"AI classification error: {e}")
        return None


def keywords_match(keywords, text):
    """
    Word-boundary matching with common English inflections. Plain
    substring checks misfire badly: 'sue' fires inside 'issue' (legal
    escalation for 'my mower has an issue'), 'late' inside 'later'.
    \\b anchors kill those false positives; the optional suffix keeps
    natural inflections matching ('delay' → 'delayed', 'claim' →
    'claims') without reopening the substring hole ('later' still
    does not match 'late').
    """
    return any(
        re.search(rf"\b{re.escape(kw)}(?:s|es|ed|d|ing)?\b", text)
        for kw in keywords
    )


def get_response(query):
    """
    Match query to a standard response template.
    Tries keyword matching first (fast, free, predictable). If nothing
    matches and OpenAI is configured, asks it to suggest an intent and
    re-checks that against the same keyword lists. Falls back to a
    generic acknowledgment if nothing matches either way.
    Returns (response_text, follow_up_flag).
    """
    query_lower = query.lower()

    for keywords, _, response_text, follow_up in STANDARD_RESPONSES:
        if keywords_match(keywords, query_lower):
            return response_text, follow_up

    if USE_OPENAI:
        ai_result = classify_with_ai(query_lower)
        if ai_result:
            ai_result_lower = ai_result.lower()
            for keywords, _, response_text, follow_up in STANDARD_RESPONSES:
                if keywords_match(keywords, ai_result_lower):
                    return response_text, follow_up

    return "Thank you for reaching out. I'll do my best to assist you.", False


def sanitize_cell(value):
    """
    Prevent spreadsheet formula injection in the audit trail: Excel and
    Google Sheets execute cells starting with =, +, - or @. A leading
    apostrophe forces text rendering without altering the logged content.
    """
    text = str(value)
    if text and text[0] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def log_to_csv(query, response, customer_email=None, follow_up=False):
    """
    Primary audit log. Always available, no setup required.
    Stored at the per-user config location (see get_log_path), so it
    survives app updates and isn't lost if the .exe is moved/redistributed.
    Returns None on success, or an error message string on failure.
    """
    file_path = get_log_path()
    follow_up_text = "Yes" if follow_up else "No"
    new_row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        sanitize_cell(customer_email or "N/A"),
        sanitize_cell(query),
        sanitize_cell(response),
        follow_up_text,
        "Open",
        "",
        "",
    ]
    file_exists = file_path.exists()
    try:
        with open(file_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "Timestamp", "Customer Email", "Query", "Response",
                    "Follow-Up Needed", "Status", "Assigned To", "Resolution Notes",
                ])
            writer.writerow(new_row)
        return None
    except OSError as e:
        return log_error(f"Failed to write CSV log: {e}")


def log_to_sheets(query, response, customer_email=None, follow_up=False):
    """
    Optional: mirrors the interaction to Google Sheets for team-wide
    visibility, if configured. The CSV log above always runs regardless,
    so this is additive, not a replacement.
    Returns None on success, or an error message string on failure.
    """
    if not USE_SHEETS:
        return None
    try:
        client = gspread.service_account_from_dict(GSHEETS_CREDENTIALS)
        sheet = client.open_by_key(GSHEETS_ID).sheet1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        follow_up_text = "Yes" if follow_up else "No"
        sheet.append_row([
            timestamp,
            sanitize_cell(customer_email or "N/A"),
            sanitize_cell(query[:200]),
            sanitize_cell(response[:200]),
            follow_up_text,
        ])
        return None
    except Exception as e:
        return log_error(f"Failed to log to Sheets: {e}")


def send_slack_alert(query, response, follow_up=False):
    """Optional real-time alert. No-op if not configured.
    Returns None on success, or an error message string on failure."""
    if not SLACK_WEBHOOK_URL:
        return None
    follow_up_tag = " [FOLLOW-UP NEEDED]" if follow_up else ""
    payload = {
        "text": f"*New CSR Query{follow_up_tag}*\nQuery: {query[:200]}\nResponse: {response[:200]}",
        "username": "CSR Automation Bot",
        "icon_emoji": ":robot_face:",
    }
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        resp.raise_for_status()
        return None
    except Exception as e:
        return log_error(f"Failed to send Slack alert: {e}")


# ---------------------------------------------------------------------------
# Setup screen
# ---------------------------------------------------------------------------

class SetupScreen:
    """
    First-run / editable settings screen. Everything here is optional —
    the toolkit works fully offline (keyword matching + local CSV log)
    if every field is left blank. Each teammate's entries are stored
    locally on their own machine only.
    """

    def __init__(self, root, on_complete):
        self.root = root
        self.on_complete = on_complete
        self.root.title("CSR Automation Toolkit — Setup")
        self.root.geometry("560x520")

        existing = load_config()

        tk.Label(root, text="Setup (all optional)", font=("Helvetica", 13, "bold")).pack(pady=(15, 2))
        tk.Label(
            root,
            text="The toolkit works immediately with no setup: keyword matching\n"
                 "plus a local CSV log. Add your own credentials below only if you\n"
                 "want Slack alerts, team-wide Sheets logging, or AI-assisted\n"
                 "classification for ambiguous queries. Stored on this computer only.",
            font=("Helvetica", 9), fg="#555555", justify="center",
        ).pack(pady=(0, 12))

        form = tk.Frame(root)
        form.pack(fill="both", expand=True, padx=20)

        self.fields = {}

        def add_field(label_text, key, show=None):
            tk.Label(form, text=label_text, anchor="w", font=("Helvetica", 9, "bold")).pack(fill="x", pady=(8, 2))
            entry = tk.Entry(form, show=show, width=60)
            entry.insert(0, existing.get(key, ""))
            entry.pack(fill="x")
            self.fields[key] = entry

        tk.Label(form, text="Slack (optional — real-time query alerts)",
                 font=("Helvetica", 9, "italic"), fg="#777777").pack(anchor="w", pady=(10, 0))
        add_field("Slack Webhook URL", "SLACK_WEBHOOK_URL")

        tk.Label(form, text="Google Sheets (optional — adds team-wide logging; CSV log always runs too)",
                 font=("Helvetica", 9, "italic"), fg="#777777").pack(anchor="w", pady=(10, 0))
        add_field("Sheet ID", "GSHEETS_ID")
        add_field("Service Account JSON (single line)", "GSHEETS_CREDENTIALS")

        tk.Label(form, text="OpenAI (optional — helps classify queries that don't match a keyword)",
                 font=("Helvetica", 9, "italic"), fg="#777777").pack(anchor="w", pady=(10, 0))
        add_field("OpenAI API Key", "OPENAI_API_KEY", show="*")

        self.status_label = tk.Label(root, text="", fg="#b00000", font=("Helvetica", 9))
        self.status_label.pack(pady=(8, 0))

        button_frame = tk.Frame(root)
        button_frame.pack(pady=15)
        tk.Button(button_frame, text="Save and Continue", command=self.save_and_continue,
                  bg="#4CAF50", fg="white", padx=10, pady=4).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Skip — use offline mode", command=self.skip,
                  padx=10, pady=4).pack(side=tk.LEFT, padx=5)

    def save_and_continue(self):
        config = {key: entry.get().strip() for key, entry in self.fields.items()}
        config["setup_complete"] = True

        if config.get("GSHEETS_CREDENTIALS"):
            try:
                json.loads(config["GSHEETS_CREDENTIALS"])
            except json.JSONDecodeError:
                self.status_label.config(
                    text="Service Account JSON isn't valid JSON — check it's pasted as one line."
                )
                return

        save_config(config)
        reload_config_globals()
        self.on_complete()

    def skip(self):
        # Persist the choice. Without this, skipping never created
        # config.json and the setup screen reappeared on every launch —
        # contradicting the "no further setup" promise in PACKAGING.md.
        # Existing config (if any) is preserved.
        config = load_config()
        config["setup_complete"] = True
        save_config(config)
        self.on_complete()


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

class CSRAutomationApp:
    """Desktop GUI for CSR agents to input queries and get auto-responses."""

    def __init__(self, root):
        self.root = root
        self.root.title("CSR Automation Toolkit")
        self.root.geometry("900x700")

        tk.Label(root, text="Customer Query:", font=("Helvetica", 10, "bold")).pack(pady=5)
        self.query_input = scrolledtext.ScrolledText(root, height=5, width=100)
        self.query_input.pack(pady=5, padx=10)

        tk.Label(root, text="Auto-Response:", font=("Helvetica", 10, "bold")).pack(pady=5)
        self.response_output = scrolledtext.ScrolledText(root, height=10, width=100)
        self.response_output.pack(pady=5, padx=10)

        self.follow_up_label = tk.Label(root, text="", font=("Helvetica", 9))
        self.follow_up_label.pack(pady=5)

        button_frame = tk.Frame(root)
        button_frame.pack(pady=10)
        self.generate_button = tk.Button(button_frame, text="Generate Response",
                  command=self.generate_response, bg="#4CAF50", fg="white")
        self.generate_button.pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Settings",
                  command=self.open_settings, bg="#9E9E9E", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Exit",
                  command=root.quit, bg="#f44336", fg="white").pack(side=tk.LEFT, padx=5)

        mode_bits = []
        mode_bits.append("Sheets: on" if USE_SHEETS else "Sheets: off")
        mode_bits.append("Slack: on" if SLACK_WEBHOOK_URL else "Slack: off")
        mode_bits.append("AI fallback: on" if USE_OPENAI else "AI fallback: off")
        self.status_label = tk.Label(root, text=f"Ready  |  {'  ·  '.join(mode_bits)}", fg="green", font=("Helvetica", 9))
        self.status_label.pack(pady=5)

    def generate_response(self):
        query = self.query_input.get("1.0", tk.END).strip()
        if not query:
            messagebox.showerror("Error", "Please enter a query.")
            return

        # AI fallback, Slack, and Sheets are all network calls. Running
        # them on the Tkinter main thread froze the UI on slow
        # connections; a background thread keeps the app responsive and
        # reports back via root.after (Tk is not thread-safe).
        self.generate_button.config(state=tk.DISABLED)
        self.status_label.config(text="Working…", fg="#555555")
        threading.Thread(target=self._process_query, args=(query,), daemon=True).start()

    def _process_query(self, query):
        try:
            response, follow_up = get_response(query)
            errors = [err for err in (
                log_to_csv(query, response, follow_up=follow_up),
                log_to_sheets(query, response, follow_up=follow_up),
                send_slack_alert(query, response, follow_up),
            ) if err]
        except Exception as e:
            log_error(f"Unexpected error while processing query: {e}")
            response, follow_up = "Thank you for reaching out. I'll do my best to assist you.", False
            errors = [str(e)]
        self.root.after(0, lambda: self._show_result(response, follow_up, errors))

    def _show_result(self, response, follow_up, errors):
        self.response_output.delete("1.0", tk.END)
        self.response_output.insert("1.0", response)

        if follow_up:
            self.follow_up_label.config(text="[FOLLOW-UP NEEDED]", fg="red")
        else:
            self.follow_up_label.config(text="No follow-up required", fg="green")

        if errors:
            self.status_label.config(
                text=f"Response generated. {len(errors)} logging/alert issue(s) — see csr_errors.log.",
                fg="#b00000",
            )
        else:
            self.status_label.config(text="Response generated and logged.", fg="blue")
        self.generate_button.config(state=tk.NORMAL)

    def open_settings(self):
        settings_window = tk.Toplevel(self.root)

        def on_settings_saved():
            settings_window.destroy()
            mode_bits = []
            mode_bits.append("Sheets: on" if USE_SHEETS else "Sheets: off")
            mode_bits.append("Slack: on" if SLACK_WEBHOOK_URL else "Slack: off")
            mode_bits.append("AI fallback: on" if USE_OPENAI else "AI fallback: off")
            self.status_label.config(text=f"Settings updated.  |  {'  ·  '.join(mode_bits)}", fg="blue")

        SetupScreen(settings_window, on_settings_saved)


def launch_main_app(root):
    for widget in root.winfo_children():
        widget.destroy()
    root.geometry("900x700")
    root.title("CSR Automation Toolkit")
    CSRAutomationApp(root)


def main():
    root = tk.Tk()
    # Setup is offered once and never blocks usage. The check is the
    # config file's *existence*, not its contents — a truthiness check
    # broke "Skip" (no file, or an empty {}, re-triggered setup forever).
    if get_config_path().exists():
        launch_main_app(root)
    else:
        SetupScreen(root, on_complete=lambda: launch_main_app(root))
    root.mainloop()


if __name__ == "__main__":
    main()
