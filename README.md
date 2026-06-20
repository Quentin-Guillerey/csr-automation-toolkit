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
| **Keyword classifier with AI fallback** | Rule-based keyword matching as the primary engine, with an optional OpenAI fallback for queries that don't match a known pattern. Currently covers 25 generic response categories as a proof of concept; designed to extend to a full, brand-agnostic query taxonomy. |
| **Local CSV audit log** | Primary logging method. Works immediately with zero setup: timestamp, contact, query, response, follow-up flag, status, assignment, and resolution notes — closer to a lightweight ticket structure than a flat log. |
| **Slack alerting (optional)** | Every query triggers a notification if configured. High-priority items are flagged `[FOLLOW-UP NEEDED]` for manual escalation (Asana/Zapier routing planned, not yet wired in). |
| **Google Sheets audit log (optional)** | Mirrors the CSV log to a shared Sheet for team-wide visibility, if configured. Additive to the CSV log, not a replacement. |

---

## Stack

`Python` `OpenAI API (optional)` `Tkinter` `CSV` `Slack Webhooks (optional)` `Google Sheets API (optional)`

---

## Status

This is a working prototype, not a production-scale deployment. It demonstrates the architecture end-to-end — classification, local audit logging, and optional alerting/AI fallback all function — at a small scale (25 response categories, all generic/brand-agnostic). Scaling to a full operational query volume (see the companion sanitized CSR query library, ~1,300 entries across 18 categories) is the next phase of this project.

---

## Why I built it

This is what I do when I see a gap in an operation I am responsible for: diagnose the problem, scope a practical solution, and build a working proof of concept without waiting for budget approval or a specialist. The goal is minimum viable, extensible, and auditable from day one — proving the architecture before investing in scale.

---

## Roadmap

- [ ] Expand classifier coverage from 25 categories to a full, brand-agnostic query taxonomy
- [ ] Build a feedback loop so misclassified queries can be flagged and folded back into the rule set
- [x] Add per-user setup screen and local config (no `.env` file required)
- [ ] Package as a standalone executable (no Python install required) for non-technical team rollout — see `PACKAGING.md`
- [ ] Wire up Asana/Zapier auto-routing for flagged follow-ups
- [ ] Measure real performance once deployed: time saved, escalation rate, audit coverage

---

## About me

Operations and customer success manager with 13+ years across regulated financial services, BPO, and diplomatic operations. Currently open to remote U.S. roles in ops, CS, and service delivery.

- Email: guillerey.finance@gmail.com
- LinkedIn: [linkedin.com/in/quentin-guillerey](https://linkedin.com/in/quentin-guillerey)
