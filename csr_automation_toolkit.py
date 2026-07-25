#!/usr/bin/env python3
"""
CSR Automation Toolkit
AI-Augmented Service Delivery Infrastructure

Automates customer query classification and response generation, with
optional Slack alerting and optional AI fallback classification. Logs
every interaction to a local CSV audit trail by default.

VALIDATION LOOP (this version): Generate and Send are two separate steps.
"Generate Response" classifies the query and fills the response box, which
stays fully editable. Nothing is logged or sent until the agent clicks
"Send & Log", at which point the CSV records BOTH the suggested response
and the final (possibly edited) response, plus an auto-computed
"Was Edited" flag. Slack/Sheets, if configured, receive the final text.

Response content lives in responses.json next to this script (or next to
the .exe in a packaged build). "Reload Responses" re-reads it without a
restart, so the library can grow continuously without rebuilds.
"""

import csv
import re
import requests
import tkinter as tk
from tkinter import scrolledtext, messagebox
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Google Sheets is optional — only imported if the teammate configures it.
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Per-user config storage (unchanged from previous version)
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
    """CSV audit log lives next to the config file, not next to the .exe."""
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
    """Re-read config into globals after the setup screen saves changes."""
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
# Response library — external responses.json
#
# Lives next to this script (or next to the packaged .exe). Expected format,
# a list of entries:
#   [
#     {
#       "keywords": ["order status", "where is my order"],
#       "key": "cppo",
#       "response": "To help track that down, ...",
#       "follow_up": true
#     },
#     ...
#   ]
# Entries are matched top-to-bottom, first match wins — same semantics as
# the previous inline list. If your responses.json uses different field
# names, adjust _normalize_entry() below (it already tolerates a few
# common variants).
# ---------------------------------------------------------------------------

def get_app_dir():
    """Directory the script or the packaged .exe is running from."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_responses_path():
    """The live, editable copy lives in the per-user config folder. On first
    run it's seeded from the responses.json shipped next to the script/.exe,
    so teammates can edit their copy freely and 'Reload Responses' picks it
    up without touching the distributed files."""
    user_copy = get_config_path().parent / "responses.json"
    if not user_copy.exists():
        seed = get_app_dir() / "responses.json"
        if seed.exists():
            try:
                user_copy.write_bytes(seed.read_bytes())
            except OSError as e:
                print(f"Could not seed responses.json to config folder: {e}")
                return seed  # fall back to reading the shipped copy directly
    return user_copy


_SUFFIXES = "(?:es|ed|ing|s|d)?"


def _compile_keyword(kw):
    """Whole-word match, case-insensitive, tolerating common suffixes on the
    final word: 'delay' matches 'delayed', but 'sue' does NOT match inside
    'issue' (word boundary) and 'order' does not match 'borders'."""
    words = kw.strip().lower().split()
    if not words:
        return None
    parts = [re.escape(w) for w in words]
    parts[-1] = parts[-1] + _SUFFIXES
    pattern = r"\b" + r"\s+".join(parts) + r"\b"
    return re.compile(pattern, re.IGNORECASE)


def _normalize_entry(entry):
    keywords = entry.get("keywords") or entry.get("triggers") or []
    key = entry.get("category") or entry.get("key") or entry.get("id") or ""
    response = entry.get("response") or entry.get("response_text") or entry.get("text") or ""
    follow_up = bool(entry.get("follow_up", entry.get("follow_up_needed", False)))
    if not keywords or not response:
        return None
    patterns = [p for p in (_compile_keyword(k) for k in keywords) if p]
    if not patterns:
        return None
    return (patterns, key, response, follow_up)


def load_responses():
    """Returns (entries, error_message). entries is a list of
    (compiled_patterns, category, response, follow_up) tuples, in file
    order — first match wins, so specific phrases belong above broad ones."""
    path = get_responses_path()
    if not path.exists():
        return [], f"responses.json not found at {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return [], f"Could not read responses.json: {e}"
    if isinstance(raw, dict):
        raw = raw.get("responses", [])
    if not isinstance(raw, list):
        return [], "responses.json must be a list, or an object with a 'responses' list"
    entries = []
    for item in raw:
        if isinstance(item, dict):
            norm = _normalize_entry(item)
            if norm:
                entries.append(norm)
    if not entries:
        return [], "responses.json loaded but contained no valid entries"
    return entries, None


RESPONSES, _responses_error = load_responses()

DEFAULT_RESPONSE = "Thank you for reaching out. I'll do my best to assist you."
DEFAULT_KEY = "default"


def classify_with_ai(query):
    """Optional OpenAI-assisted classification. Returns None if not
    configured or on any failure."""
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
    """Match query to a response entry.
    Returns (response_text, follow_up_flag, category_key)."""
    query_lower = query.lower()

    for patterns, key, response_text, follow_up in RESPONSES:
        if any(p.search(query_lower) for p in patterns):
            return response_text, follow_up, key

    if USE_OPENAI:
        ai_result = classify_with_ai(query_lower)
        if ai_result:
            ai_result_lower = ai_result.lower()
            for patterns, key, response_text, follow_up in RESPONSES:
                if any(p.search(ai_result_lower) for p in patterns):
                    return response_text, follow_up, key

    return DEFAULT_RESPONSE, False, DEFAULT_KEY


# ---------------------------------------------------------------------------
# Audit logging — now records suggested vs final
# ---------------------------------------------------------------------------

CSV_HEADER = [
    "Timestamp", "Customer Email", "Query", "Category",
    "Suggested Response", "Final Response", "Was Edited",
    "Follow-Up Needed", "Status", "Assigned To", "Resolution Notes",
]


def _rotate_legacy_log(file_path):
    """If an existing log uses the old column layout, rename it so old and
    new rows never share one file with mismatched columns (audit integrity)."""
    try:
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            first_line = f.readline()
        if "Was Edited" not in first_line:
            legacy = file_path.parent / "csr_logs_legacy.csv"
            # Don't overwrite an existing legacy file; add a timestamp if needed.
            if legacy.exists():
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                legacy = file_path.parent / f"csr_logs_legacy_{stamp}.csv"
            file_path.rename(legacy)
    except OSError as e:
        print(f"Could not rotate legacy log: {e}")


def log_to_csv(query, suggested, final, category, customer_email=None, follow_up=False):
    """Primary audit log. Records both the suggested and the final
    (agent-approved) response, plus whether the agent edited it."""
    file_path = get_log_path()
    was_edited = "Yes" if suggested.strip() != final.strip() else "No"
    follow_up_text = "Yes" if follow_up else "No"
    new_row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        customer_email or "N/A",
        query,
        category,
        suggested,
        final,
        was_edited,
        follow_up_text,
        "Open",
        "",
        "",
    ]
    if file_path.exists():
        _rotate_legacy_log(file_path)
    file_exists = file_path.exists()
    try:
        with open(file_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(CSV_HEADER)
            writer.writerow(new_row)
        return True
    except OSError as e:
        print(f"Failed to write CSV log: {e}")
        return False


def log_to_sheets(query, final, category, customer_email=None, follow_up=False):
    """Optional team-wide mirror. Logs the FINAL response only — the full
    suggested-vs-final detail lives in the local CSV."""
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
        sheet.append_row([timestamp, customer_email or "N/A", query[:200],
                          final[:200], follow_up_text, category])
    except Exception as e:
        print(f"Failed to log to Sheets: {e}")


def send_slack_alert(query, final, follow_up=False):
    """Optional real-time alert with the FINAL response. No-op if not configured."""
    if not SLACK_WEBHOOK_URL:
        return
    follow_up_tag = " [FOLLOW-UP NEEDED]" if follow_up else ""
    payload = {
        "text": f"*New CSR Query{follow_up_tag}*\nQuery: {query[:200]}\nResponse: {final[:200]}",
        "username": "CSR Automation Bot",
        "icon_emoji": ":robot_face:",
    }
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to send Slack alert: {e}")


# ---------------------------------------------------------------------------
# Setup screen (unchanged)
# ---------------------------------------------------------------------------

class SetupScreen:
    """First-run / editable settings screen. Everything here is optional."""

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
# Main app — with validation loop
# ---------------------------------------------------------------------------

class CSRAutomationApp:
    """Desktop GUI. Two-step flow: Generate (classify + suggest, editable)
    then Send & Log (agent-approved final gets logged and alerted)."""

    def __init__(self, root):
        self.root = root
        self.root.title("CSR Automation Toolkit")
        self.root.geometry("900x700")

        # Pending interaction: set by Generate, consumed by Send & Log.
        self.pending = None

        tk.Label(root, text="Customer Query:", font=("Helvetica", 10, "bold")).pack(pady=5)
        self.query_input = scrolledtext.ScrolledText(root, height=5, width=100)
        self.query_input.pack(pady=5, padx=10)

        tk.Label(root, text="Suggested Response (edit before sending):",
                 font=("Helvetica", 10, "bold")).pack(pady=5)
        self.response_output = scrolledtext.ScrolledText(root, height=10, width=100)
        self.response_output.pack(pady=5, padx=10)

        self.follow_up_label = tk.Label(root, text="", font=("Helvetica", 9))
        self.follow_up_label.pack(pady=5)

        button_frame = tk.Frame(root)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Generate Response",
                  command=self.generate_response, bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=5)
        self.send_button = tk.Button(button_frame, text="Send & Log",
                                     command=self.send_and_log, bg="#2196F3", fg="white",
                                     state=tk.DISABLED)
        self.send_button.pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Reload Responses",
                  command=self.reload_responses, bg="#9E9E9E", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Settings",
                  command=self.open_settings, bg="#9E9E9E", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Exit",
                  command=root.quit, bg="#f44336", fg="white").pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(root, text="", fg="green", font=("Helvetica", 9))
        self.status_label.pack(pady=5)
        self._set_ready_status()

        if _responses_error:
            messagebox.showwarning(
                "Response library",
                f"{_responses_error}\n\nThe toolkit will run, but every query "
                "will get the generic fallback until responses.json is fixed "
                "and reloaded."
            )

    def _mode_bits(self):
        bits = [f"{len(RESPONSES)} responses"]
        bits.append("Sheets: on" if USE_SHEETS else "Sheets: off")
        bits.append("Slack: on" if SLACK_WEBHOOK_URL else "Slack: off")
        bits.append("AI fallback: on" if USE_OPENAI else "AI fallback: off")
        return "  ·  ".join(bits)

    def _set_ready_status(self, prefix="Ready"):
        self.status_label.config(text=f"{prefix}  |  {self._mode_bits()}", fg="green")

    def generate_response(self):
        query = self.query_input.get("1.0", tk.END).strip()
        if not query:
            messagebox.showerror("Error", "Please enter a query.")
            return

        response, follow_up, category = get_response(query)
        self.response_output.delete("1.0", tk.END)
        self.response_output.insert("1.0", response)

        if follow_up:
            self.follow_up_label.config(text="[FOLLOW-UP NEEDED]", fg="red")
        else:
            self.follow_up_label.config(text="No follow-up required", fg="green")

        self.pending = {
            "query": query,
            "suggested": response,
            "follow_up": follow_up,
            "category": category,
        }
        self.send_button.config(state=tk.NORMAL)
        self.status_label.config(
            text="Suggested response ready — review or edit, then Send & Log. Nothing logged yet.",
            fg="#b36b00",
        )

    def send_and_log(self):
        if not self.pending:
            messagebox.showerror("Error", "Generate a response first.")
            return

        final = self.response_output.get("1.0", tk.END).strip()
        if not final:
            messagebox.showerror("Error", "Response is empty — edit it or regenerate before sending.")
            return

        p = self.pending
        ok = log_to_csv(p["query"], p["suggested"], final, p["category"],
                        follow_up=p["follow_up"])
        log_to_sheets(p["query"], final, p["category"], follow_up=p["follow_up"])
        send_slack_alert(p["query"], final, p["follow_up"])

        edited = "edited" if p["suggested"].strip() != final else "unedited"
        self.pending = None
        self.send_button.config(state=tk.DISABLED)
        if ok:
            self.status_label.config(text=f"Sent and logged ({edited}).", fg="blue")
        else:
            self.status_label.config(
                text="Sent, but CSV write FAILED — check console / file permissions.", fg="red")

    def reload_responses(self):
        global RESPONSES, _responses_error
        entries, err = load_responses()
        if err:
            messagebox.showerror("Reload failed", f"{err}\n\nKeeping the "
                                 f"previously loaded {len(RESPONSES)} responses.")
            return
        RESPONSES = entries
        _responses_error = None
        self._set_ready_status(prefix="Responses reloaded")

    def open_settings(self):
        settings_window = tk.Toplevel(self.root)

        def on_settings_saved():
            settings_window.destroy()
            self._set_ready_status(prefix="Settings updated")

        SetupScreen(settings_window, on_settings_saved)


def launch_main_app(root):
    for widget in root.winfo_children():
        widget.destroy()
    root.geometry("900x700")
    root.title("CSR Automation Toolkit")
    CSRAutomationApp(root)


def main():
    root = tk.Tk()
    config = load_config()
    if config:
        launch_main_app(root)
    else:
        SetupScreen(root, on_complete=lambda: launch_main_app(root))
    root.mainloop()


if __name__ == "__main__":
    main()
