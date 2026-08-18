# CSR Automation Toolkit

**AI-Augmented Service Delivery Prototype**

Built by [Quentin Guillerey](https://linkedin.com/in/quentin-guillerey), Customer Operations Manager, bilingual FR/EN

---

## The problem

Running U.S. operations for the world leader in robotic mowing at 3,000+ customer contacts per month, I watched agents spend most of their day on manual triage and copy-paste work. There was no standardized response system, no audit trail, and no automatic routing for follow-up tasks.

This repository is my own answer to that problem. It was built on personal time and personal hardware, ships with a generic brand-agnostic response library, contains no client data, and is not deployed on any account.

---

## What it does

| Component | What it does |
|---|---|
| **Tkinter GUI** | Desktop app for non-technical operators. No command line, no IT dependency. Includes a one-time setup screen (or "Skip, use offline mode") so each user can configure their own optional integrations. |
| **Keyword classifier with AI fallback** | Rule-based matching as the primary engine: whole-word, case-insensitive, suffix-tolerant (including doubled-consonant inflections, so `cancel` matches both `canceled` and `cancelled`), first-match-wins. Optional AI fallback for unmatched queries asks the model to select one known entry ID from the catalogue, so the result is a lookup rather than a second keyword guess. Anything outside the catalogue is rejected. Currently covers 40 generic response entries as a proof of concept. |
| **External response library** | All response content lives in `responses.json`, seeded to each user's config folder on first run. The library grows continuously: edit the JSON, click "Reload Responses," no rebuild, no restart, no redistribution. |
| **Validation loop** | Generate and Send are two separate steps. The suggested response is fully editable before the agent commits it, and nothing is logged or alerted until "Send & Log." |
| **Local CSV audit log** | Primary logging method, zero setup. Records the suggested response, the final (agent-approved) response, an auto-computed "Was Edited" flag, and both the matched entry ID and its category, plus timestamp, contact, follow-up flag, status, assignment, and resolution notes. This is the pilot's evidence base: it shows exactly which entries are weak, not just which broad category. |
| **Slack alerting (optional)** | The agent-approved final response triggers a notification if configured. High-priority items are flagged `[FOLLOW-UP NEEDED]` for manual escalation (Asana/Zapier routing planned, not yet wired in). |
| **Google Sheets audit log (optional)** | Mirrors interactions to a shared Sheet for team-wide visibility, if configured. Additive to the CSV log, not a replacement. |

---

## Audit integrity

The log is the product. These are guarantees, each covered by a test in `tests/`:

- **Formula injection is neutralized.** A query beginning `=`, `+`, `-`, or `@` is escaped before it is written, so an audit log opened in Excel or Sheets cannot execute it.
- **Schema mismatches are never mixed.** Before any write, the existing log's full header is compared against the current schema. On mismatch the old file is rotated out. **If rotation fails**, most commonly because the CSV is open in Excel, **the write is aborted and reported**, rather than appending new columns to an old-schema file.
- **Nothing fails silently.** The packaged build has no console, so every failure is written to `csr_errors.log` in the user's config folder and surfaced in the app's status bar. A dead Slack webhook or an expired Sheets credential is visible, not swallowed.
- **Network calls run off the UI thread.** Slack and Sheets are dispatched on a background thread so a slow or unreachable endpoint never freezes the window. The CSV write stays synchronous, because its result determines whether the interaction was recorded at all.

---

## Stack

`Python` `Tkinter` `CSV` `pytest` · optional: `OpenAI API` `Slack Webhooks` `Google Sheets API` · packaging: `PyInstaller`

---

## Tests

```
pip install -r requirements-dev.txt
pytest -q
```

The suite runs fully offline, with no network, no API keys, and no display. It enforces the audit-integrity guarantees above, the documented keyword-matching behaviour, and a **no-shadowed-keywords invariant** over the shipped library (no entry may silently swallow a later entry's trigger phrase, which is the failure mode that kills rule-based classifiers as they grow). Config and log paths are redirected to a temp directory, so running the tests never touches a real audit log.

---

## Status

Working prototype, validated on real hardware but **not deployed in production**. The full flow, covering classification, editable response validation, suggested-vs-final audit logging, and optional alerting and AI fallback, has been runtime-tested both from source and as a packaged standalone Windows executable (no Python install required, see `PACKAGING.md`). Current scale is 40 generic, brand-agnostic response entries.

No performance claims are made. Measurement comes after the pilot, from the audit log, not from estimates.

Next phase: pilot with 1 or 2 teammates, then scale the library toward a full operational query taxonomy (see the companion sanitized CSR query library, roughly 1,300 entries across 18 categories), driven by what the audit data shows rather than assumptions.

---

## Why I built it

When I see a structural gap in an operation, I would rather scope and prototype a solution than wait for budget approval or a specialist. The goal here was minimum viable, extensible, and auditable from day one: prove the architecture before investing in scale.

---

## Roadmap

- [x] Add per-user setup screen and local config (no `.env` file required)
- [x] Externalize the response library (`responses.json`) with in-app reload, so content grows without rebuilds
- [x] Add a validation loop: editable suggested responses, with suggested-vs-final and "Was Edited" captured in the audit log
- [x] Package as a standalone executable (no Python install required) for non-technical rollout, see `PACKAGING.md`
- [x] Harden the audit log: formula-injection escaping, schema-mismatch rotation with abort-on-failure, persistent error log, non-blocking integrations
- [x] Log the matched entry ID alongside its category, so pilot data identifies the specific weak entry
- [x] Offline test suite in CI covering the classifier and the audit-log guarantees
- [ ] Pilot with 1 or 2 teammates; review the audit log for misclassified queries and heavily edited responses
- [ ] Fold pilot findings back into the response library and keyword rules
- [ ] Expand classifier coverage toward a full, brand-agnostic query taxonomy
- [ ] Wire up Asana/Zapier auto-routing for flagged follow-ups
- [ ] Capture customer contact details in the GUI to populate the audit log's reserved contact column
- [ ] Measure real performance once deployed: time saved, escalation rate, audit coverage

---

## Related projects

- [AISCORE](https://github.com/Quentin-Guillerey/AISCORE): QA scoring engine for contact-center interactions. FastAPI and PostgreSQL, weighted rubric scoring, with every criterion classified as rule-based, model-based, or not automatable, and human override on compliance.
- Resolva: self-maintaining knowledge base that converts resolved support tickets into structured institutional knowledge. Claude API, Flask, SQLite, with SME review workflows and audit logs.

---

## About me

Operations and customer success manager with 14 years across regulated financial services, BPO, and diplomatic operations. Currently open to remote U.S. roles in ops, CS, and service delivery.

- Email: guillerey.finance@gmail.com
- LinkedIn: [linkedin.com/in/quentin-guillerey](https://linkedin.com/in/quentin-guillerey)
