# CSR Knowledge Base — Agent Reference Guide

**Companion to the CSR Automation Toolkit.** This document is for the human agent to read and internalize — unlike `responses.json`, nothing here is auto-matched or returned verbatim to a customer. It covers the judgment-call side of customer support: when to de-escalate, when to mention an upsell, and how to sound human while doing it.

This is domain-agnostic by design. Swap in your company's specific policies, products, and regulatory constraints where noted — the underlying behaviors transfer across SaaS, fintech, pharma, B2B, or any other vertical.

---

## 1. De-escalation

De-escalation isn't a script — it's a sequence of moves. The goal is to lower the emotional temperature *before* you try to solve the actual problem. Solving the problem first, while the customer is still activated, usually fails even if your solution is correct.

### The core sequence

1. **Acknowledge before you solve.** The first thing out of your mouth (or onto the screen) should recognize what the person is feeling, not jump straight to the fix. A customer who feels heard will let you work; a customer who feels processed will keep escalating no matter what you offer.
2. **Slow down, don't speed up.** The instinct under pressure is to talk faster and get to resolution quicker. Do the opposite — a calmer, more deliberate pace is itself de-escalating. Matching someone's urgency or frustration in your own tone adds fuel.
3. **Get specific, not defensive.** Ask for the concrete detail (order number, date, what exactly happened) rather than explaining policy or defending the company. Explaining policy too early reads as deflection, even when it's accurate.
4. **Give them a next step, even a small one.** "I'm going to do X right now" is more de-escalating than "I understand your frustration." Action signals you're taking it seriously; sympathy alone can read as a placeholder for action.
5. **Know when to bring in a second person.** If the customer is asking for a supervisor, asking by the second time isn't a failure on your part — looping someone in early, gracefully, is often what actually resolves things. See "When to escalate internally" below.

### What not to do

- Don't say "calm down" or any variant — it never calms anyone down.
- Don't argue the facts in the moment if the customer is highly activated. Get the facts right later, in writing if needed; in the moment, the priority is bringing the temperature down.
- Don't take it personally or mirror frustration back. The customer is angry at the situation, not at you specifically, even when it's aimed at you.
- Don't over-apologize past the point of usefulness — one genuine acknowledgment lands better than five reflexive "I'm so sorrys," which start to sound hollow.

### When to escalate internally

Escalate to a supervisor or specialized team when:
- The customer has explicitly asked for one, more than once.
- The situation involves a legal threat, regulatory complaint, or safety issue.
- You don't have the authority to offer the resolution the situation actually calls for (e.g., an exception to policy).
- You notice yourself getting frustrated — escalating is also a tool for protecting your own ability to stay level with the next customer.

Escalating well means setting the next person up to succeed: a quick, accurate summary so the customer never has to repeat themselves from scratch.

### Domain-specific notes (customize per industry)

- **Regulated industries (fintech, pharma, healthcare):** some complaints carry compliance obligations (e.g., mandatory reporting timelines, specific required disclosures). Know your industry's triggers for "this isn't just a CX issue anymore" before you're in the conversation, not during it.
- **B2B / high-contract-value accounts:** the account's commercial relationship (renewal timing, contract size, relationship owner) often changes who should be looped in and how fast — loop in account management proactively rather than waiting to be asked.

---

## 2. Policies and procedures — general best practices

Policies in `responses.json` give the agent the *exact wording* for common situations. This section is about *how* to deliver that wording so it doesn't read as robotic or adversarial.

- **State the policy as a fact, not a verdict against the customer.** "Our return window is 30 days" lands differently than "You're outside the return window." Same information, very different tone.
- **Pair policy with the next available option.** A policy statement alone (especially a "no") feels like a dead end. Always follow it with what *can* be done, even if it's smaller than what was asked.
- **Don't promise what you can't confirm.** If you're not certain a timeline or exception will hold, say what you're checking on rather than committing to an outcome you might have to walk back.
- **Write down what you tell the customer.** Whatever channel you're in, the resolution notes / audit trail should reflect what was actually promised — this protects both the customer and the next agent who picks up the thread.

---

## 3. Upsell and cross-sell — judgment, not a script

Upsell timing matters more than upsell content. The same offer, mentioned at the wrong moment, reads as tone-deaf; mentioned at the right moment, it reads as helpful.

### Good moments to mention something extra

- **Right after a resolution lands well** — the customer is in a positive state, primed to hear "since you're here" without it feeling like a pivot away from their actual problem.
- **When the customer's own words signal a real need** — "I keep running into [limit]," "I wish it could also do [thing]" — these are the customer upselling themselves; you're just following their lead, not introducing something unprompted.
- **At natural plan/contract boundaries** — renewal conversations, usage-limit conversations — where bringing up options is expected, not intrusive.

### Bad moments

- **Mid-frustration or mid-complaint.** Never. An upsell offered while someone is still upset reads as the company trying to extract more money instead of solving the problem — it can undo whatever de-escalation work you've already done.
- **As a substitute for actually solving the issue.** If the "upsell" is really a workaround for something broken, be honest about that distinction rather than dressing up a patch as a premium feature.
- **Repeatedly, after a decline.** One mention, framed as genuinely optional, is enough. Pushing after "no thanks" erodes trust fast.

### How to frame it

Keep it low-pressure and tied to what the customer actually said, not a generic pitch:
- Reference their specific situation ("given what you're using this for…") rather than a scripted feature list.
- Make declining easy and explicit ("no pressure either way") — this paradoxically makes people more receptive, not less.
- Don't oversell. A short, honest mention that respects a "no" builds more long-term trust (and more eventual upgrades) than a hard pitch.

---

## 4. Rapport-building language

These are phrases an agent layers into their own words — not canned outputs, not things a customer's message should ever auto-trigger. Used naturally and not too often, they make an interaction feel personal instead of transactional.

### Reassurance / ownership

- "You're in good hands."
- "Let me take care of that for you personally."
- "I'm going to stay on this until it's resolved."
- "Consider this handled."

### Collaborative framing

- "How does that sound?"
- "Does that work for you?"
- "Let's figure this out together."
- "What would be most helpful for you right now?"

### Validating without over-apologizing

- "That makes total sense given what you've described."
- "I'd want the same thing in your position."
- "Fair point — let me look into that."

### Closing warmly

- "Anything else on your mind before we wrap up?"
- "I'll be right here if anything else comes up."
- "Thanks for your patience while we sorted that out."

**Usage note:** these work because they're said sparingly and sound like the agent means them. Stacking several in one response, or using the same one every time, has the opposite effect — it starts to sound like a script, which is exactly what this section is trying to avoid producing.

---

## 5. Adapting this document to a new domain

When repointing the toolkit at a new company or industry:

1. Keep Sections 1, 3, and 4 largely as-is — de-escalation psychology, upsell timing, and rapport language are close to universal.
2. Rewrite Section 2's specifics (and the corresponding `responses.json` policy entries) to match the new domain's actual policies, refund windows, compliance language, etc.
3. Add a domain-specific subsection under "De-escalation → Domain-specific notes" for whatever regulatory or industry-specific triggers apply (e.g., HIPAA in healthcare, FINRA-adjacent disclosures in fintech, GDPR/data-subject requests in any EU-facing SaaS).

---

*Last updated: this is a living document — update it as the response library in `responses.json` grows, so the two stay in sync.*
