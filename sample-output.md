# Social-engineering simulation: Dana Iyer

- **Role:** Senior Payroll Analyst at Northwind Logistics
- **Communication style:** Brisk and formal, mixes payroll shorthand with chatty asides, mirrors whoever she is replying to
- **Difficulty:** 3/5
- **Objective:** Gain unauthorized access to Dana's payroll systems by convincing her to change bank details via a forged request.

## Pretext narrative

The attacker poses as Marta Kwan, Dana's manager, claiming that there has been a last-minute adjustment needed for payroll processing. They reference a recent communication from the finance department regarding Q3 adjustments, which the attacker has accessed through an internal report. To add credibility, the attacker forges a company email from Marta's address indicating urgency. The attacker plans to reach out to Dana today since the deadline for the payroll change is imminent, leveraging Dana's newness to the team and her current uncertainty over processes to push for a quick response. The attacker also mentions that the finance team has flagged discrepancies that need immediate resolution, making it essential for Dana to act quickly and follow the new instructions provided.

## Opening message

**Subject:** Payroll Update Required for Q3 Adjustments

Hi Dana, this is Marta Kwan from People Operations. I need you to update the bank details for payroll processing due to some urgent adjustments flagged by finance. Please check your email for the invoice reference #Q3-2023-128 and make the necessary changes in the bank-change portal by the end of the day. Thanks for your quick attention to this!

## Escalation path

1. **email** · Send a follow-up email _(goal: Reiterate urgency and introduce a new deadline)_
   - Artifact: Invoice reference #Q3-2023-128
2. **phone** · Call Dana to confirm the changes _(goal: Ensure Dana is taking action and address any doubts)_
   - Artifact: Caller ID displays Marta's number
3. **chat** · Send a chat message via the company platform _(goal: Request confirmation of the updated bank details)_
   - Artifact: Chat transcript showing urgency
4. **in_person** · Arrange a quick meeting to finalize the changes _(goal: Get Dana to verbally confirm the updates and build trust)_
   - Artifact: Calendar invite for a 'quick sync' meeting

## Red flags for defenders

1. **Inconsistencies in communication style**
   - Why it matters: If Marta typically communicates in a more personable tone, the abruptness may indicate something is off.
   - Defender action: Verify the message with Marta directly before acting.
2. **Unfamiliarity with process**
   - Why it matters: Dana is still new to the team and may not be clear on how to verify requests.
   - Defender action: Consult with a trusted colleague about the process before proceeding.
3. **Urgent deadline without prior notice**
   - Why it matters: Requests for immediate action without prior context could be a red flag.
   - Defender action: Request additional details and context for the sudden urgency.
4. **Forcing a quick response**
   - Why it matters: High-pressure tactics are often used in social engineering to create confusion.
   - Defender action: Take a moment to verify the request and seek clarity.

---

_Fictional exercise. Domains, names, and systems are invented. Use against authorized targets only._
