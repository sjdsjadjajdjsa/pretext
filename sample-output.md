# Social-engineering simulation: Dana Iyer

- **Role:** Senior Payroll Analyst at Northwind Logistics
- **Communication style:** Brisk and formal, mixes payroll shorthand with chatty asides, mirrors whoever she is replying to
- **Difficulty:** 3/5
- **Objective:** Obtain Dana's access to the bank-change portal for unauthorized modifications.

## Pretext narrative

The attacker conducts research on Northwind Logistics and discovers a recent press release about a new payroll system implementation. Leveraging this information, the attacker forges an email address that closely mimics that of Marta Kwan (marta.k@northwindlogistics.com) and claims to be reaching out regarding some urgent updates. The attacker emphasizes that, as the new Senior Payroll Analyst, it is crucial for Dana Iyer to assist in the verification of the new banking details for payroll processing. The attacker incorporates a fake ticket number (TICKET-4562) from the IT department, suggesting that an issue has been flagged that requires immediate attention. By framing the message around a critical payroll update, the attacker makes Dana feel responsible and pressed for time, effectively manipulating her into compliance.

## Opening message

**Subject:** Payroll Inquiry: Action Needed Today

Hi Dana, this is Marta Kwan (marta.k@northwindlogistics.com). I need your help with TICKET-4562. We need to verify the new banking details for payroll processing before the end of the day due to the recent system changes. Can you check the bank-change portal and confirm the new entries? Let me know if you have any questions.

## Escalation path

1. **email** · Send a follow-up email detailing urgency. _(goal: Get Dana to confirm the bank details are updated by the end of the day.)_
   - Artifact: A screenshot of the supposed bank-change portal showing incorrect details.
2. **phone** · Call Dana to discuss the bank details. _(goal: Pressure Dana into making the changes immediately.)_
   - Artifact: A call log showing the call was made from a number mimicking the payroll hotline.
3. **chat** · Send a chat message claiming to be from IT. _(goal: Reinforce urgency by introducing a new IT contact who corroborates the need for changes.)_
   - Artifact: A message from 'IT Support' with a link to a fake IT support page.
4. **in_person** · Suggest a quick in-person meeting. _(goal: Obtain verbal confirmation from Dana about the bank changes.)_
   - Artifact: A calendar invite for a 'quick sync' to discuss payroll updates.

## Red flags for defenders

1. **Email address discrepancy**
   - Why it matters: The attacker used a slightly altered email address that mimics Marta's, which could indicate a phishing attempt.
   - Defender action: Verify the sender's email address against known contacts before responding.
2. **Unusual urgency around bank changes**
   - Why it matters: The request to finalize banking details is unusually urgent, which is not standard practice.
   - Defender action: Consult with peers or supervisors about typical response times for such requests.
3. **Inconsistencies in IT support communication**
   - Why it matters: The IT support message may not come from a verified internal source.
   - Defender action: Cross-check IT requests with the IT department directly before taking action.

---

_Fictional exercise. Domains, names, and systems are invented. Use against authorized targets only._
