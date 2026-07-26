# CSR Automation Toolkit

**AI-Augmented Service Delivery Prototype**

Built by [Quentin Guillerey](https://linkedin.com/in/quentin-guillerey) — Customer Operations Manager, bilingual FR/EN

---

## The problem

I was running U.S. operations for the World Leader in Robotic Mowing handling 3,000+ customer contacts per month. The team had no standardized response system, no audit trail, and no way to flag and route follow-up tasks automatically. Agents spent most of their time on manual triage and copy-paste work. No one was going to build the solution. So I started building one.

---

## What it does

| Component | What it does |
|---|---|
| **Tkinter GUI** | Desktop app for non-technical operators. No command line, no IT dependency. Includes a one-time setup screen (or "Skip — use offline mode") so each user can configure their own optional integrations. |
| **Keyword classifier with AI fallback** | Rule-based matching as the primary engine — whole-word, case-insensitive, suffix-tolerant, first-match-wins — with an optional OpenAI fallback for queries that don't match a known pattern. Currently covers 40 generic response entries as a proof of concept; designed to extend to a full, brand-agnostic query taxonomy. |
| **External response library** | All response content lives in `responses.json`, seeded to each user's config folder on first run. The library grows continuously — edit the JSON, click "Reload Responses," no rebuild, no restart, no redistribution. |
| **Validation loop** | Generate and Send are two separate steps. The suggested response is fully editable before the agent commits it; nothing is logged or alerted until "Send & Log." |
| **Local CSV audit log** | Primary logging method, zero setup. Records the suggested response, the final (agent-approved) response, an auto-computed "Was Edited" flag, and the matched category — plus timestamp, contact, follow-up flag, status, assignment, and resolution notes. This is the pilot's evidence base: it shows exactly where the classifier and the response copy are weak. |
| **Slack alerting (optional)** | The agent-approved final response triggers a notification if configured. High-priority items are flagged `[FOLLOW-UP NEEDED]` for manual escalation (Asana/Zapier routing planned, not yet wired in). |
| **Google Sheets audit log (optional)** | Mirrors interactions to a shared Sheet for team-wide visibility, if configured. Additive to the CSV log, not a replacement. |

---

## Stack

`Python` `OpenAI API (optional)` `Tkinter` `CSV` `Slack Webhooks (optional)` `Google Sheets API (optional)` `PyInstaller`

---

## Status

This is a working prototype, validated on real hardware but not yet deployed at production scale. The full flow — classification, editable response validation, suggested-vs-final audit logging, and optional alerting/AI fallback — has been runtime-tested both from source and as a packaged standalone Windows executable (no Python install required; see `PACKAGING.md`). Current scale is 40 generic, brand-agnostic response entries. Next phase: pilot with 1–2 teammates, then scale the library toward a full operational query taxonomy (see the companion sanitized CSR query library, ~1,300 entries across 18 categories), driven by what the audit data shows rather than assumptions.

---

## Why I built it

This is what I do when I see a gap in an operation I am responsible for: diagnose the problem, scope a practical solution, and build a working proof of concept without waiting for budget approval or a specialist. The goal is minimum viable, extensible, and auditable from day one — proving the architecture before investing in scale.

---

## Roadmap

- [x] Add per-user setup screen and local config (no `.env` file required)
- [x] Externalize the response library (`responses.json`) with in-app reload — content grows without rebuilds
- [x] Add a validation loop: editable suggested responses, with suggested-vs-final and "Was Edited" captured in the audit log
- [x] Package as a standalone executable (no Python install required) for non-technical team rollout — see `PACKAGING.md`
- [ ] Pilot with 1–2 teammates; review the audit log for misclassified queries and heavily edited responses
- [ ] Fold pilot findings back into the response library and keyword rules
- [ ] Expand classifier coverage toward a full, brand-agnostic query taxonomy
- [ ] Wire up Asana/Zapier auto-routing for flagged follow-ups
- [ ] Measure real performance once deployed: time saved, escalation rate, audit coverage

---

## About me

Operations and customer success manager with 13+ years across regulated financial services, BPO, and diplomatic operations. Currently open to remote U.S. roles in ops, CS, and service delivery.

- Email: guillerey.finance@gmail.com
- LinkedIn: [linkedin.com/in/quentin-guillerey](https://linkedin.com/in/quentin-guillerey)
