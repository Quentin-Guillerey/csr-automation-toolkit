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
| **Tkinter GUI** | Desktop app for non-technical operators. No command line, no IT dependency. |
| **Keyword classifier with AI fallback** | Rule-based keyword matching as the primary engine, with an OpenAI fallback for queries that don't match a known pattern. Currently covers 5 core response categories as a proof of concept; designed to extend to the full query taxonomy used by the team. |
| **Auto-reply engine** | IMAP email reader with SMTP auto-response tied to classifier output. |
| **Slack alerting** | Every query triggers a notification. High-priority items are flagged `[FOLLOW-UP NEEDED]` for manual escalation (Asana/Zapier routing planned, not yet wired in). |
| **Google Sheets audit log** | Full interaction history: timestamp, contact, query, response, follow-up flag. Built for compliance and performance tracking from day one. |

---

## Stack

`Python` `OpenAI API` `Tkinter` `IMAP/SMTP` `Slack Webhooks` `Google Sheets API`

---

## Status

This is a working prototype, not a production-scale deployment. It demonstrates the architecture end-to-end — classification, auto-reply, alerting, and audit logging all function — at a small scale (5 response categories). Scaling to the full operational query volume (the team's actual query library runs to ~1,300 distinct entries across 18 categories) is the next phase of this project.

---

## Why I built it

This is what I do when I see a gap in an operation I am responsible for: diagnose the problem, scope a practical solution, and build a working proof of concept without waiting for budget approval or a specialist. The goal is minimum viable, extensible, and auditable from day one — proving the architecture before investing in scale.

---

## Roadmap

- [ ] Expand classifier coverage from 5 categories to the full operational query taxonomy
- [ ] Build a feedback loop so misclassified queries can be flagged and folded back into the rule set
- [ ] Package as a standalone executable (no Python install required) for non-technical team rollout
- [ ] Wire up Asana/Zapier auto-routing for flagged follow-ups
- [ ] Measure real performance once deployed: time saved, escalation rate, audit coverage

---

## About me

Operations and customer success manager with 13+ years across regulated financial services, BPO, and diplomatic operations. Currently open to remote U.S. roles in ops, CS, and service delivery.

- Email: guillerey.finance@gmail.com
- LinkedIn: [linkedin.com/in/quentin-guillerey](https://linkedin.com/in/quentin-guillerey)
