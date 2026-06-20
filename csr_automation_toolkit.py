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
skipped) per-user via the setup screen on first run.

RESPONSE LIBRARY: as of this revision, response content lives in an
external responses.json file next to the executable, not hardcoded in
this script. This is what makes the toolkit adaptable to any domain —
editing responses.json adds/changes/removes responses with no code
change and no rebuild. See load_responses() below. A small built-in
default set is kept as a fallback so the toolkit still works with zero
setup if responses.json is missing.
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
# so teammates who skip it don't need gspread/oauth2client installed.
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Per-user config storage
#
# Packaged builds (.exe) have no .env file alongside them, and each
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
# Response library — loaded from an external responses.json file
#
# This is the core "adapt to any domain" mechanism: editing responses.json
# (next to the .exe) adds, changes, or removes responses with no code
# change and no rebuild. The file is plain text — open it in Notepad,
# edit, save, relaunch the app.
#
# Matching is first-match-wins on lowercase substring containment, so
# entry ORDER in the file matters: more specific phrases must appear
# before broader phrases that contain them as a substring (e.g. "warranty
# denied" must be checked before the bare word "warranty", or the broader
# entry will always win first and the specific one becomes unreachable).
#
# A small built-in default set ships inside the .exe itself as a fallback,
# so the toolkit still works with zero setup even if responses.json is
# missing, deleted, or malformed — consistent with the rest of the app's
# "works immediately, nothing required" design.
# ---------------------------------------------------------------------------

# Minimal built-in fallback — only used if responses.json can't be loaded.
# Kept intentionally small; the real, growing library lives in the JSON file.
_DEFAULT_RESPONSES = [
    {
        "id": "default_greeting", "category": "greeting",
        "keywords": ["help", "assist", "support"],
        "response": "I'd be happy to assist you with that.",
        "follow_up": False,
    },
    {
        "id": "default_thanks", "category": "closing",
        "keywords": ["thank you", "thanks"],
        "response": "You're welcome. Is there anything else I can help you with?",
        "follow_up": False,
    },
]


def get_responses_path():
    """
    Location of the editable response library. Lives NEXT TO the
    executable (or the .py source, when run unpackaged), not in the
    per-user config folder — this file is meant to be opened, edited,
    and redistributed as part of adapting the toolkit to a new team or
    domain, not treated as personal local settings.
    """
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller-built .exe
        base = Path(sys.executable).parent
    else:
        # Running from source (python csr_automation_toolkit.py)
        base = Path(__file__).resolve().parent
    return base / "responses.json"


def load_responses():
    """
    Load the response library from responses.json. Returns a list of
    (keywords, id, response_text, follow_up) tuples in file order, which
    is also match-priority order (first match wins).

    Falls back to a small built-in default set — with a printed notice,
    not a crash or silent failure — if the file is missing or invalid,
    so the toolkit keeps working either way.
    """
    path = get_responses_path()
    raw_entries = None

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_entries = data.get("responses", [])
            if not raw_entries:
                print(f"responses.json at {path} has no entries — using built-in defaults.")
                raw_entries = None
        except (json.JSONDecodeError, OSError) as e:
            print(f"Could not read responses.json ({e}) — using built-in defaults.")
            raw_entries = None
    else:
        print(f"No responses.json found at {path} — using built-in defaults.")

    if raw_entries is None:
        raw_entries = _DEFAULT_RESPONSES

    parsed = []
    for entry in raw_entries:
        try:
            parsed.append((
                entry["keywords"],
                entry.get("id", ""),
                entry["response"],
                bool(entry.get("follow_up", False)),
            ))
        except KeyError as e:
            print(f"Skipping malformed response entry (missing {e}): {entry}")
    return parsed


# Loaded once at startup. Restart the app to pick up edits to responses.json
# (matches how the rest of the app already behaves — Settings changes also
# take effect via reload, not live file-watching).
STANDARD_RESPONSES = load_responses()


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
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": f"In a few words, classify the intent of this customer service query: {query}"
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
    Tries keyword matching first (fast, free, predictable). If nothing
    matches and OpenAI is configured, asks it to suggest an intent and
    re-checks that against the same keyword lists. Falls back to a
    generic acknowledgment if nothing matches either way.
    Returns (response_text, follow_up_flag).
    """
    query_lower = query.lower()

    for keywords, _, response_text, follow_up in STANDARD_RESPONSES:
        if any(keyword in query_lower for keyword in keywords):
            return response_text, follow_up

    if USE_OPENAI:
        ai_result = classify_with_ai(query_lower)
        if ai_result:
            ai_result_lower = ai_result.lower()
            for keywords, _, response_text, follow_up in STANDARD_RESPONSES:
                if any(kw in ai_result_lower for kw in keywords):
                    return response_text, follow_up

    return "Thank you for reaching out. I'll do my best to assist you.", False


def log_to_csv(query, response, customer_email=None, follow_up=False):
    """
    Primary audit log. Always available, no setup required.
    Stored at the per-user config location (see get_log_path), so it
    survives app updates and isn't lost if the .exe is moved/redistributed.
    """
    file_path = get_log_path()
    follow_up_text = "Yes" if follow_up else "No"
    new_row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        customer_email or "N/A",
        query,
        response,
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
    except OSError as e:
        print(f"Failed to write CSV log: {e}")


def log_to_sheets(query, response, customer_email=None, follow_up=False):
    """
    Optional: mirrors the interaction to Google Sheets for team-wide
    visibility, if configured. The CSV log above always runs regardless,
    so this is additive, not a replacement.
    """
    if not USE_SHEETS:
        return
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(GSHEETS_CREDENTIALS, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(GSHEETS_ID).sheet1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        follow_up_text = "Yes" if follow_up else "No"
        sheet.append_row([timestamp, customer_email or "N/A", query[:200], response[:200], follow_up_text])
    except Exception as e:
        print(f"Failed to log to Sheets: {e}")


def send_slack_alert(query, response, follow_up=False):
    """Optional real-time alert. No-op if not configured."""
    if not SLACK_WEBHOOK_URL:
        return
    follow_up_tag = " [FOLLOW-UP NEEDED]" if follow_up else ""
    payload = {
        "text": f"*New CSR Query{follow_up_tag}*\nQuery: {query[:200]}\nResponse: {response[:200]}",
        "username": "CSR Automation Bot",
        "icon_emoji": ":robot_face:",
    }
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to send Slack alert: {e}")


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
        tk.Button(button_frame, text="Generate Response",
                  command=self.generate_response, bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=5)
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

        response, follow_up = get_response(query)
        self.response_output.delete("1.0", tk.END)
        self.response_output.insert("1.0", response)

        if follow_up:
            self.follow_up_label.config(text="[FOLLOW-UP NEEDED]", fg="red")
        else:
            self.follow_up_label.config(text="No follow-up required", fg="green")

        log_to_csv(query, response, follow_up=follow_up)
        log_to_sheets(query, response, follow_up=follow_up)
        send_slack_alert(query, response, follow_up)
        self.status_label.config(text="Response generated and logged.", fg="blue")

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
    # No required fields anymore (CSV + keyword matching always work),
    # so the setup screen is offered once but never blocks usage.
    config = load_config()
    if config:
        launch_main_app(root)
    else:
        SetupScreen(root, on_complete=lambda: launch_main_app(root))
    root.mainloop()


if __name__ == "__main__":
    main()
