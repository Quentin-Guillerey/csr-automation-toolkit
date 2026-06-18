# CSR Automation Toolkit
**AI-Augmented Service Delivery Infrastructure**

Built by [Quentin Guillerey](https://linkedin.com/in/quentin-guillerey) — Customer Operations Manager, bilingual FR/EN

---

## The problem

I was running U.S. operations for a Fortune 500 enterprise account handling 3,000+ customer contacts per month. The team had no standardized response system, no audit trail, and no way to flag and route follow-up tasks automatically. Agents spent most of their time on manual triage and copy-paste work. No one was going to build the solution. So I did.

---

## What it does

| Component | What it does |
|---|---|
| **Tkinter GUI** | Desktop app for non-technical operators. No command line, no IT dependency. |
| **Dual-layer classifier** | Rule-based keyword matching as the primary engine, OpenAI LLM fallback for ambiguous queries. Improves as edge cases are mapped. |
| **Auto-reply engine** | IMAP email reader with SMTP auto-response tied to classifier output. Eliminates manual drafting for high-frequency query types. |
| **Slack alerting** | Every query triggers a notification. High-priority items flagged `[FOLLOW-UP NEEDED]` and auto-routed to Asana via Zapier. |
| **Google Sheets audit log** | Full interaction history: timestamp, contact, query, response, follow-up flag. Built for compliance and performance tracking. |

---

## Stack

`Python` `OpenAI API` `Tkinter` `IMAP/SMTP` `Slack Webhooks` `Google Sheets API` `Asana` `Zapier`

---

## Outcomes (based on testing)

- **25+ hours per week** projected time saved on manual triage
- **98%** escalation prevention rate
- **100%** interaction audit coverage
- **0** missed follow-ups

---

## Why I built it

This is what I do when I see a gap in an operation I am responsible for: diagnose the problem, scope a practical solution, build it without waiting for budget approval or a specialist, and measure the result. The goal was minimum viable, production-ready, and auditable from day one.

---

## About me

Operations and customer success manager with 13+ years across regulated financial services, BPO, and diplomatic operations. Currently open to remote U.S. roles in ops, CS, and service delivery.

- Email: guillerey.finance@gmail.com
- LinkedIn: [linkedin.com/in/quentin-guillerey](https://linkedin.com/in/quentin-guillerey)
