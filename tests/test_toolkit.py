"""
Offline test suite for the CSR Automation Toolkit.

Runs with no network, no API keys, no Slack, no Sheets, and no display.
Imports the module with a temporary config directory so a developer's real
audit log and config are never touched.

    pip install pytest
    pytest -q
"""

import csv
import importlib
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _stub_tkinter():
    """The toolkit imports tkinter at module scope. CI runners and headless
    build agents often have no Tk, so install a minimal stub before import.
    No test instantiates a widget; this only satisfies the import."""
    try:
        import tkinter  # noqa: F401
        return
    except ImportError:
        pass

    tk = types.ModuleType("tkinter")
    for name in ("Label", "Entry", "Frame", "Button", "Tk", "Toplevel"):
        setattr(tk, name, type(name, (), {"__init__": lambda self, *a, **k: None}))
    tk.END = "end"
    tk.LEFT = "left"
    tk.DISABLED = "disabled"
    tk.NORMAL = "normal"

    scrolled = types.ModuleType("tkinter.scrolledtext")
    scrolled.ScrolledText = type("ScrolledText", (), {"__init__": lambda self, *a, **k: None})
    box = types.ModuleType("tkinter.messagebox")
    box.showerror = box.showwarning = box.showinfo = lambda *a, **k: None

    tk.scrolledtext = scrolled
    tk.messagebox = box
    sys.modules["tkinter"] = tk
    sys.modules["tkinter.scrolledtext"] = scrolled
    sys.modules["tkinter.messagebox"] = box


@pytest.fixture()
def toolkit(tmp_path, monkeypatch):
    """Import the toolkit with config/log paths redirected into tmp_path, so
    a developer's real audit log and config are never touched."""
    _stub_tkinter()
    if sys.platform == "win32":
        monkeypatch.setenv("APPDATA", str(tmp_path))
    else:
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    sys.modules.pop("csr_automation_toolkit", None)
    mod = importlib.import_module("csr_automation_toolkit")
    importlib.reload(mod)
    return mod


# ---------------------------------------------------------------------------
# Keyword compiler: the documented behaviour must be the real behaviour
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("keyword,text,expected", [
    # Word boundaries: the claim the README makes explicitly
    ("sue", "this is an issue", False),
    ("order", "crossing borders", False),
    ("is", "this", False),
    ("cat", "concatenate", False),
    # Basic suffix tolerance
    ("delay", "the shipment is delayed", True),
    ("refund", "refunding now", True),
    ("box", "several boxes", True),
    # Doubled-consonant inflections (US and British/Canadian spelling)
    ("cancel", "my order was canceled", True),
    ("cancel", "my order was cancelled", True),
    ("ship", "it shipped yesterday", True),
    ("ship", "when is it shipping", True),
    ("plan", "planning an upgrade", True),
    # Multi-word phrases tolerate arbitrary whitespace
    ("order status", "what is my order status", True),
    ("order status", "order   status please", True),
    ("order status", "order\nstatus", True),
    # Exact phrase still required, not bag-of-words
    ("order status", "status of the order", False),
])
def test_keyword_matching(toolkit, keyword, text, expected):
    pattern = toolkit._compile_keyword(keyword)
    assert bool(pattern.search(text.lower())) is expected


def test_empty_keyword_is_ignored(toolkit):
    assert toolkit._compile_keyword("   ") is None


# ---------------------------------------------------------------------------
# First-match-wins ordering invariant
# ---------------------------------------------------------------------------

def test_no_shadowed_keywords_in_shipped_library(toolkit):
    """Every keyword must be reachable: no earlier entry may swallow a later
    entry's trigger phrase. This is the failure mode that silently kills
    rule-based classifiers as the library grows."""
    responses = json.loads((ROOT / "responses.json").read_text(encoding="utf-8"))
    items = responses["responses"] if isinstance(responses, dict) else responses
    entries = [toolkit._normalize_entry(it) for it in items]
    entries = [e for e in entries if e]

    shadowed = []
    for j, entry in enumerate(entries):
        raw_keywords = items[j].get("keywords", [])
        for kw in raw_keywords:
            for i, earlier in enumerate(entries):
                if i >= j:
                    break
                if any(p.search(kw.lower()) for p in earlier.patterns):
                    shadowed.append((kw, entry.entry_id, earlier.entry_id))
                    break
    assert not shadowed, f"unreachable keywords: {shadowed}"


def test_shipped_library_loads_and_ids_are_unique(toolkit):
    entries, err = toolkit.load_responses()
    assert err is None
    assert len(entries) > 0
    ids = [e.entry_id for e in entries]
    assert len(ids) == len(set(ids)), "duplicate entry ids"


def test_first_match_wins(toolkit):
    e1 = toolkit._normalize_entry({
        "id": "specific", "category": "a",
        "keywords": ["order status"], "response": "SPECIFIC"})
    e2 = toolkit._normalize_entry({
        "id": "broad", "category": "b",
        "keywords": ["order"], "response": "BROAD"})
    toolkit.RESPONSES = [e1, e2]
    text, _, entry_id, _ = toolkit.get_response("what is my order status")
    assert entry_id == "specific"
    assert text == "SPECIFIC"


def test_unmatched_query_returns_generic_default(toolkit):
    toolkit.RESPONSES = []
    text, follow_up, entry_id, category = toolkit.get_response("zzzz nonsense")
    assert entry_id == toolkit.DEFAULT_ID
    assert category == toolkit.DEFAULT_CATEGORY
    assert follow_up is False
    assert text == toolkit.DEFAULT_RESPONSE


# ---------------------------------------------------------------------------
# CSV formula injection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload", [
    "=cmd|' /C calc'!A0",
    "+1+1",
    "-2+3",
    "@SUM(1:9)",
    "\t=1+1",
])
def test_formula_injection_is_neutralized(toolkit, payload):
    assert toolkit._sanitize(payload).startswith("'")


@pytest.mark.parametrize("benign", [
    "where is my order",
    "",
    "order #12345",
    "3 items missing",
])
def test_benign_values_are_untouched(toolkit, benign):
    assert toolkit._sanitize(benign) == benign


def test_written_csv_cell_is_not_a_live_formula(toolkit):
    ok, msg = toolkit.log_to_csv(
        query="=cmd|' /C calc'!A0",
        suggested="s", final="s",
        entry_id="cppo", category="policy")
    assert ok, msg
    rows = list(csv.reader(toolkit.get_log_path().open(encoding="utf-8", newline="")))
    assert rows[0] == toolkit.CSV_HEADER
    query_col = rows[0].index("Query")
    assert rows[1][query_col].startswith("'")


# ---------------------------------------------------------------------------
# Audit log integrity
# ---------------------------------------------------------------------------

def test_edit_flag_and_ids_are_recorded(toolkit):
    toolkit.log_to_csv("q", "suggested text", "final text", "cppo", "policy")
    toolkit.log_to_csv("q2", "same", "same", "cerr", "general")
    rows = list(csv.DictReader(toolkit.get_log_path().open(encoding="utf-8", newline="")))
    assert rows[0]["Was Edited"] == "Yes"
    assert rows[1]["Was Edited"] == "No"
    assert rows[0]["Entry ID"] == "cppo"
    assert rows[0]["Category"] == "policy"
    assert rows[1]["Entry ID"] == "cerr"


def test_mismatched_header_is_rotated_not_appended(toolkit):
    """An old-schema log must be moved aside, never appended to."""
    log = toolkit.get_log_path()
    with log.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Timestamp", "Query", "Response"])  # old schema
        w.writerow(["2026-01-01 00:00:00", "old query", "old response"])

    ok, msg = toolkit.log_to_csv("new", "s", "s", "cppo", "policy")
    assert ok, msg

    legacy = log.parent / "csr_logs_legacy.csv"
    assert legacy.exists(), "old-schema file was not rotated out"
    rows = list(csv.reader(log.open(encoding="utf-8", newline="")))
    assert rows[0] == toolkit.CSV_HEADER
    assert len(rows) == 2, "new log should contain only the header and one new row"


def test_matching_header_is_not_rotated(toolkit):
    toolkit.log_to_csv("first", "s", "s", "cppo", "policy")
    toolkit.log_to_csv("second", "s", "s", "cppo", "policy")
    assert not (toolkit.get_log_path().parent / "csr_logs_legacy.csv").exists()
    rows = list(csv.reader(toolkit.get_log_path().open(encoding="utf-8", newline="")))
    assert len(rows) == 3  # header + 2


def test_write_is_aborted_when_rotation_fails(toolkit, monkeypatch):
    """If the old log cannot be moved (locked by Excel on Windows), the write
    must fail loudly rather than append the new schema to the old file."""
    log = toolkit.get_log_path()
    with log.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(["Timestamp", "Query", "Response"])
    before = log.read_text(encoding="utf-8")

    def boom(self, target):
        raise OSError("file is locked")

    monkeypatch.setattr(Path, "rename", boom)
    ok, msg = toolkit.log_to_csv("new", "s", "s", "cppo", "policy")

    assert ok is False
    assert msg
    assert log.read_text(encoding="utf-8") == before, "old log was modified after a failed rotation"


# ---------------------------------------------------------------------------
# Optional integrations must be true no-ops when unconfigured
# ---------------------------------------------------------------------------

def test_slack_is_a_noop_without_a_webhook(toolkit):
    toolkit.SLACK_WEBHOOK_URL = ""
    assert toolkit.send_slack_alert("q", "r", False) == (True, "")


def test_sheets_is_a_noop_when_disabled(toolkit):
    toolkit.USE_SHEETS = False
    assert toolkit.log_to_sheets("q", "r", "cppo", "policy") == (True, "")


def test_ai_fallback_is_a_noop_without_a_key(toolkit):
    toolkit.USE_OPENAI = False
    assert toolkit.classify_with_ai("anything") is None


def test_ai_fallback_rejects_an_id_outside_the_catalogue(toolkit, monkeypatch):
    """The model must not be able to invent a category."""
    entry = toolkit._normalize_entry({
        "id": "cppo", "category": "policy",
        "keywords": ["order status"], "response": "R"})
    toolkit.RESPONSES = [entry]
    toolkit.USE_OPENAI = True
    toolkit.OPENAI_API_KEY = "test-key"

    class _Msg:
        content = "totally_made_up_id"

    class _Choice:
        message = _Msg()

    class _Completion:
        choices = [_Choice()]

    class _FakeClient:
        def __init__(self, **kw):
            self.chat = self

        @property
        def completions(self):
            return self

        def create(self, **kw):
            return _Completion()

    fake_openai = type("openai", (), {"OpenAI": _FakeClient})
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    assert toolkit.classify_with_ai("something unmatched") is None


# ---------------------------------------------------------------------------
# Response library robustness
# ---------------------------------------------------------------------------

def test_missing_library_reports_an_error_not_a_crash(toolkit, monkeypatch):
    monkeypatch.setattr(toolkit, "get_responses_path",
                        lambda: Path("/nonexistent/responses.json"))
    entries, err = toolkit.load_responses()
    assert entries == []
    assert "not found" in err


def test_malformed_library_reports_an_error_not_a_crash(toolkit, monkeypatch, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setattr(toolkit, "get_responses_path", lambda: bad)
    entries, err = toolkit.load_responses()
    assert entries == []
    assert "Could not read" in err


def test_entries_missing_required_fields_are_skipped(toolkit):
    assert toolkit._normalize_entry({"id": "x", "keywords": []}) is None
    assert toolkit._normalize_entry({"id": "x", "keywords": ["hi"]}) is None
    assert toolkit._normalize_entry({"id": "x", "response": "hi"}) is None


def test_id_falls_back_to_category_when_absent(toolkit):
    entry = toolkit._normalize_entry({
        "category": "policy", "keywords": ["hello"], "response": "R"})
    assert entry.entry_id == "policy"
    assert entry.category == "policy"
