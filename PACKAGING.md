# Packaging the CSR Automation Toolkit as a standalone .exe

This must be run on a **Windows machine** — PyInstaller builds for the OS
it runs on, and the sandbox used to draft this code has no Windows
environment or display, so the build itself has to happen on your end.

## What changed in the code (already done)

`csr_automation_toolkit.py` merges two earlier parallel drafts into one
canonical version, with all brand-specific content removed — this is a
generic prototype, ready to be paired with the sanitized CSR query library
(see the "Generic CSR Knowledge Base" project) for any customer service
team to adapt, not just one originally built around a specific product line.

- **CSV logging is now the primary, always-on audit trail** — no setup
  required, works immediately. Stored at `%APPDATA%\CSRToolkit\csr_logs.csv`.
- **Google Sheets, Slack, and OpenAI are all optional** — configure any/all
  of them via the in-app "Settings" screen, or skip entirely and the
  toolkit still works fully offline with keyword matching + CSV logging.
- **Response content now lives in `responses.json`, not hardcoded in the
  script** — this is what makes the toolkit adaptable to any domain.
  Editing the JSON file adds, changes, or removes responses with no code
  change and no rebuild. See "The response library" section below —
  this file has its own packaging step, separate from the .exe build.
- No `.env` file needed. On first run (or via "Settings" any time after),
  each teammate enters their own credentials for whichever optional
  features they want. Saved locally to:
  ```
  %APPDATA%\CSRToolkit\config.json
  ```
  — never bundled in the .exe, never shared between teammates.

## The response library (`responses.json`)

**This file is NOT bundled into the .exe by PyInstaller — it must be
copied next to the .exe manually, every time.** This is intentional:
keeping it external is what lets the response set be edited and grown
without recompiling, but it does mean one extra manual step in the build
flow that's easy to forget.

- The toolkit looks for `responses.json` in the same folder as the
  running executable (or next to the `.py` file, if running from source).
- If the file is missing or malformed, the toolkit doesn't crash — it
  falls back to a tiny built-in default set (2 entries) and prints a
  notice. This means a forgotten `responses.json` is a *silent
  degradation*, not an error you'll necessarily notice on launch. Always
  verify the file is present after copying the `.exe` to `dist/`.
- To adapt the toolkit to a new team or domain: open `responses.json` in
  any text editor, add/edit/remove entries, save. No rebuild needed —
  just relaunch the `.exe`.
- Entry order matters: matching is first-match-wins on substring
  containment, so more specific phrases must appear before broader
  phrases that contain them (see the `_comment` field in the file
  itself for the exact rule, and worked examples in the file's existing
  entries — e.g. `warranty denied` is listed before the bare `warranty`).
- See the companion `CSR_Knowledge_Base.md` for de-escalation, upsell
  judgment, and rapport-building guidance that's deliberately *not* in
  `responses.json` — that content is for the agent to internalize, not
  for the classifier to auto-return verbatim.

## One-time build setup

1. Install Python 3.10+ on the build machine (only needed for *building*,
   not for teammates running the final .exe):
   https://www.python.org/downloads/

2. Install dependencies:
   ```
   pip install -r requirements.txt
   pip install pyinstaller
   ```

3. Confirm `requirements.txt` no longer needs `python-dotenv` (the .env
   dependency was replaced by the config screen) — remove that line if
   it's still listed.

## Build

From the folder containing `csr_automation_toolkit.py` and
`csr_automation_toolkit.spec`:

> **Note:** if you pulled `csr_automation_toolkit.spec` from the project as
> `csr_automation_toolkit_spec.txt` (renamed for mobile upload compatibility),
> rename it back to `csr_automation_toolkit.spec` before running the command
> below — the content is identical, only the extension was changed.

```
pyinstaller csr_automation_toolkit.spec
```

Output appears at:
```
dist/CSR_Automation_Toolkit.exe
```

This is a single file. No Python install, no pip, no dependencies needed
on a teammate's machine.

**Required extra step — copy the response library into `dist/` too:**
```
copy responses.json dist\
```
PyInstaller only bundles what's referenced in the `.spec` file's `datas`,
and `responses.json` is deliberately *not* in there — it's meant to stay
external and editable. Skip this step and the toolkit will still launch
and run fine, just silently using the 2-entry fallback set instead of
the real response library. Always confirm `dist\responses.json` exists
before distributing.

## Distributing to teammates

1. Copy **both** `CSR_Automation_Toolkit.exe` **and** `responses.json`
   to each teammate's desktop (or a shared drive they can copy from) —
   they must stay in the same folder. The toolkit runs without
   `responses.json` present, but silently falls back to a near-empty
   default response set if it's missing, so don't skip it.
2. They double-click the `.exe`. First launch shows the setup screen —
   everything on it is optional.
3. They can click "Skip — use offline mode" to start using it immediately
   with keyword matching and local CSV logging, no credentials needed at
   all. Or they can enter their own Slack/Sheets/OpenAI details for the
   extra features. Either way, "Save and Continue" / "Skip" gets them into
   the main app.
4. Done — no further setup needed on subsequent launches. They can revisit
   "Settings" any time to add or change credentials.

## Before wide rollout, check with [YOUR COMPANY] IT

- Will antivirus/SmartScreen flag an unsigned .exe from an unknown
  publisher? (Likely yes, first run — Windows will show a "Windows
  protected your PC" warning that needs "More info" → "Run anyway."
  Code-signing avoids this but costs money and isn't necessary for an
  internal pilot tool.)
- Do teammates have permission to run unsigned executables on their
  machines, or is that locked down by IT policy?
- Where should the canonical .exe live for updates — shared drive,
  internal site, manual redistribution each time you rebuild?

## Updating the toolkit later

**Two different update paths now, depending on what changed:**

**Adding or editing responses (no rebuild needed):**
Edit `responses.json` directly, save, redistribute just that file to
teammates (overwrite their existing copy, same folder as the `.exe`).
They relaunch the app — no PyInstaller, no new `.exe`. This is the
expected, common-case update path now that response content lives
outside the script.

**Changing actual code in `csr_automation_toolkit.py`** (new features,
bug fixes, UI changes): rerun
```
pyinstaller csr_automation_toolkit.spec
```
copy the new `responses.json` alongside it if that's changed too, and
redistribute both. Teammates' saved credentials in
`%APPDATA%\CSRToolkit\config.json` are untouched by either update path —
they won't need to re-enter anything.
