# User settings and corrections

Last updated: YYYY-MM-DD

---

> Example template. Replace the placeholders and dated examples
> with the user's actual corrections as they occur.

This file records corrections that `<USER_NAME>` makes to the routine's decisions. The routine must read it before acting and apply these adjustments as persistent rules.

## Classification corrections

- YYYY-MM-DD: Do not create drafts for automatic notifications from shared storage services (e.g. Drive shares). Nobody responds to those. Exception: if the email body includes an explicit personal message.
- YYYY-MM-DD: `<CONTACT_NAME>` (`<sender@example.com>`) is a family member/close contact of the user. Communication with them happens through another channel (not email). Do not create drafts for their automatic emails (Drive shares, etc.).
- YYYY-MM-DD: Emails from the sensitive bank/service (`<sender@example.com>`) or any mention of the card/account `<ACCOUNT_REF>` → **DO NOT archive automatically**. The user does not actively use it. Keep in inbox and mark as action required.
- YYYY-MM-DD: Queue/Delete must **archive** (not just label). Periodically (e.g. Fridays) the routine produces an extended report summarizing everything archived/deleted in the period, analyzes what might be relevant, and suggests unsubscribes for what is not.
- YYYY-MM-DD: **Job opportunities and calls for proposals NEVER go to Queue/Delete.** The routine must review each job alert and evaluate relevance vs. the user's profile (subject areas, geography, seniority) and keep relevant ones in inbox so the user can prioritize. Archive only clearly irrelevant ones. Improve criteria over time with feedback.

- YYYY-MM-DD: **NEVER move emails to trash (TRASH).** The routine does NOT have permission to delete emails under any circumstance. "Queue/Delete" means archive (`--remove INBOX`), NOT `--add TRASH`.

## Tone / draft corrections

- Preferred sign-off: `<SIGN_OFF>` (e.g. "Best regards", "Cheers").
- Preferred register: `<formal | informal>` as appropriate.
- Style: be concise.

## Behavior corrections

- YYYY-MM-DD: If the user reports the routine is being too aggressive archiving/deleting, **prefer keeping in inbox when in doubt** until they indicate otherwise. Only archive/delete when there is high certainty the email does not require attention.
- YYYY-MM-DD: **NEVER accept, decline, or respond to calendar invitations automatically.** Only report them in the summary. Act on the calendar only when the user explicitly requests it.
- YYYY-MM-DD: **Drafts always within the thread.** Use the CLI command that replies to the original messageId (`--reply-to-message-id <messageId>`), never create orphan drafts via APIs that don't support reply-to.
- YYYY-MM-DD: For pending payments, define priority by service: mark urgent those that affect production/operations; the rest can wait.
- YYYY-MM-DD: **Periodic weekly report.** In addition to the daily review, produce an extended report covering everything archived and flagged as Queue/Delete since the previous report. Include: summary of what arrived, analysis of what might be relevant, and for what is not, investigate whether unsubscribe is possible (link or instructions).
- YYYY-MM-DD: **Events with deadlines are not merely informational.** When an email from an active project mentions a future date, read the full body and extract every implicit action: registration, RSVP, form to complete, expected attendance, material distribution. Mark them as "Action required" in the report with an explicit deadline, **not** as "upcoming event, no actions". If you suggest a response, create it as a draft (not just describe it).

## Format

When the user corrects something, add it here with date and brief context. Example:

```
- YYYY-MM-DD: "Don't archive emails from <sender>, I always want to see them" → move to policy.md as inbox rule
- YYYY-MM-DD: "The draft tone for <person> was too formal" → record tone preference
```
