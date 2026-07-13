# CSR Automation Toolkit

**AI-Augmented Service Delivery Prototype**

Built by [Quentin Guillerey](https://linkedin.com/in/quentin-guillerey) — Customer Operations Manager, bilingual FR/EN

---

## The problem

I was running U.S. operations for a Fortune 500 enterprise account handling 3,000+ customer contacts per month. The team had no standardized response system, no audit trail, and no way to flag and route follow-up tasks automatically. Agents spent most of their time on manual triage and copy-paste work. No one was going to build the solution. So I started building one.

---

## What it does

| Component | What it does |
|---|---|
| **Tkinter GUI** | Desktop app for non-technical operators. No command line, no IT dependency. Includes a one-time setup screen (or "Skip — use offline mode") so each user can configure their own optional integrations. |
| **Keyword classifier with AI fallback** | Rule-based matching as the primary engine, with an optional OpenAI fallback for queries that don't match a known pattern. Matching is word-boundary based with inflection handling, so "sue" doesn't misfire inside "issue" while "delayed" still matches "delay". Currently covers 40 generic response entries as a proof of concept; designed to extend to a full, brand-agnostic query taxonomy. |
| **Editable response library** | All responses live in `responses.json`, not in code. The app seeds an editable copy to each user's config folder on first run; teams can add or change responses in a text editor and click "Reload Responses" in-app — no code changes, no rebuild. A corrupt or invalid file falls back to the bundled default and logs the problem. |
| **Local CSV audit log** | Primary logging method. Works immediately with zero setup: timestamp, query, response, follow-up flag, status, assignment, and resolution notes — closer to a lightweight ticket structure than a flat log. A contact column is reserved; capturing contact details in the GUI is on the roadmap. Cells are escaped against spreadsheet formula injection, and any logging or alert failure is written to a local `csr_errors.log` rather than failing silently. |
| **Slack alerting (optional)** | Every query triggers a notification if configured. High-priority items are flagged `[FOLLOW-UP NEEDED]` for manual escalation (Asana/Zapier routing planned, not yet wired in). |
| **Google Sheets logging (optional)** | Writes a condensed row (timestamp, query, response, follow-up flag) to a shared Sheet for team-wide visibility, if configured. Additive to the full CSV log, not a replacement. |

All network work (AI fallback, Slack, Sheets) runs off the UI thread, so the app stays responsive on slow connections.

---

## Stack

`Python` `OpenAI API (optional)` `Tkinter` `CSV` `Slack Webhooks (optional)` `Google Sheets API (optional)`

---

## Status

This is a working prototype, not a production-scale deployment. It demonstrates the architecture end-to-end — classification, local audit logging, and optional alerting/AI fallback all function — at a small scale (40 response entries, all generic/brand-agnostic). Scaling to a full operational query volume (see the companion sanitized CSR query library, ~1,300 entries across 18 categories) is the next phase of this project.

---

## Why I built it

This is what I do when I see a gap in an operation I am responsible for: diagnose the problem, scope a practical solution, and build a working proof of concept without waiting for budget approval or a specialist. The goal is minimum viable, extensible, and auditable from day one — proving the architecture before investing in scale.

---

## Roadmap

- [ ] Expand classifier coverage from 40 entries to a full, brand-agnostic query taxonomy
- [ ] Build a feedback loop so misclassified queries can be flagged and folded back into the rule set
- [x] Add per-user setup screen and local config (no `.env` file required)
- [x] Harden classifier matching (word-boundary + inflection matching, regression-tested)
- [x] Externalize the response library to an editable `responses.json` with in-app reload
- [x] Make failures visible: local error log plus in-app status instead of silent drops
- [ ] Capture customer contact details in the GUI so the audit log's contact column is populated
- [ ] Package as a standalone executable (no Python install required) for non-technical team rollout — see `PACKAGING.md`
- [ ] Wire up Asana/Zapier auto-routing for flagged follow-ups
- [ ] Measure real performance once deployed: time saved, escalation rate, audit coverage

---

## About me

Operations and customer success manager with 13+ years across regulated financial services, BPO, and diplomatic operations. Currently open to remote U.S. roles in ops, CS, and service delivery.

- Email: guillerey.finance@gmail.com
- LinkedIn: [linkedin.com/in/quentin-guillerey](https://linkedin.com/in/quentin-guillerey)
