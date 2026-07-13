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

- **CSV logging is the primary, always-on audit trail** — no setup
  required, works immediately. Stored at `%APPDATA%\CSRToolkit\csr_logs.csv`.
- **Responses live in `responses.json`, not in code.** The build bundles
  it as the default; on each user's first run it's copied to
  `%APPDATA%\CSRToolkit\responses.json` as their editable copy. Teammates
  (or you) can edit that file in any text editor and click "Reload
  Responses" in the app — no rebuild, no redistribution.
- **Errors are visible.** The packaged app has no console, so failures
  (Slack, Sheets, AI fallback, bad responses.json entries) are written to
  `%APPDATA%\CSRToolkit\csr_errors.log` and surfaced in the status bar.
- **Google Sheets, Slack, and OpenAI are all optional** — configure any/all
  of them via the in-app "Settings" screen, or skip entirely and the
  toolkit still works fully offline with keyword matching + CSV logging.
- No `.env` file needed. On first run (or via "Settings" any time after),
  each teammate enters their own credentials for whichever optional
  features they want. Saved locally to:
  ```
  %APPDATA%\CSRToolkit\config.json
  ```
  — never bundled in the .exe, never shared between teammates.

## One-time build setup

1. Install Python 3.10+ on the build machine (only needed for *building*,
   not for teammates running the final .exe):
   https://www.python.org/downloads/

2. Install dependencies — including the optional ones. PyInstaller can
   only bundle what's installed, so a build machine missing `openai` or
   `gspread` produces an .exe permanently missing those features:
   ```
   pip install -r requirements.txt
   pip install pyinstaller
   ```

## Build

From a folder containing all three of:
- `csr_automation_toolkit.py`
- `csr_automation_toolkit.spec`
- `responses.json`  ← required; the spec bundles it into the .exe

```
pyinstaller csr_automation_toolkit.spec
```

Output appears at:
```
dist/CSR_Automation_Toolkit.exe
```

This is a single file. No Python install, no pip, no dependencies needed
on a teammate's machine.

## Distributing to FPS teammates

1. Copy `CSR_Automation_Toolkit.exe` to each teammate's desktop (or a
   shared drive they can copy it from).
2. They double-click it. First launch shows the setup screen — everything
   on it is optional.
3. They can click "Skip — use offline mode" to start using it immediately
   with keyword matching and local CSV logging, no credentials needed at
   all. Or they can enter their own Slack/Sheets/OpenAI details for the
   extra features. Either way, "Save and Continue" / "Skip" gets them into
   the main app — and the choice sticks; the setup screen won't reappear.
4. Done — no further setup needed on subsequent launches. They can revisit
   "Settings" any time to add or change credentials, and edit
   `%APPDATA%\CSRToolkit\responses.json` any time to change responses.

## Before wide rollout, check with FPS IT

- Will antivirus/SmartScreen flag an unsigned .exe from an unknown
  publisher? (Likely yes, first run — Windows will show a "Windows
  protected your PC" warning that needs "More info" → "Run anyway."
  Code-signing avoids this but costs money and isn't necessary for an
  internal pilot tool. UPX compression is disabled in the spec to reduce
  false positives.)
- Do teammates have permission to run unsigned executables on their
  machines, or is that locked down by IT policy?
- Where should the canonical .exe live for updates — shared drive,
  internal site, manual redistribution each time you rebuild?

## Updating the toolkit later

**Response changes need no rebuild at all** — edit
`%APPDATA%\CSRToolkit\responses.json` on the teammate's machine (or
distribute an updated file to that location) and click "Reload Responses."

For code changes to `csr_automation_toolkit.py`, rerun:
```
pyinstaller csr_automation_toolkit.spec
```
and redistribute the new `.exe`. Teammates' saved credentials in
`%APPDATA%\CSRToolkit\config.json` and their edited `responses.json` are
untouched by updates — nothing needs re-entering.
