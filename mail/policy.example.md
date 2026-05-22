# Mail classification policy

Last updated: YYYY-MM-DD

---

> Example template. Replace the `<...>` placeholders and example rows
> with the user's actual senders, domains, and rules.

## Queue/Delete (for final user review)

### By sender (always delete)

| Sender | Address | Exceptions |
|---|---|---|
| Job alerts | `<sender@example.com>` | **DO NOT delete.** Review each alert, evaluate relevance vs. `<USER_NAME>`'s profile (professional interests, subject areas, geography) and keep relevant ones in inbox. Archive only clearly irrelevant ones. |
| Daily agenda notifications | `<sender@example.com>` | Only "Daily Agenda" or "no events scheduled" |
| Service X promos | `<sender@example.com>` | — |
| Mass surveys | `<sender@example.com>` | — |
| Retailer promos | `<sender@example.com>` | Except billing/payment emails |
| Promotional newsletter | `<sender@example.com>` | — |
| Design platform promos | `<sender@example.com>` | — |
| Airline promos | `<sender@example.com>` | — |
| Travel agency promos | `<sender@example.com>` | — |
| Insurance promos | `<sender@example.com>` | NOT insurance/debit/claims emails |
| Bank promos | `<sender@example.com>` | — |
| Job board alerts | `<sender@example.com>` | — |
| Content newsletter | `<sender@example.com>` | — |
| Fintech promos | `<sender@example.com>` | — |
| SaaS promos | `<sender@example.com>` | NOT failed payment emails |
| Gaming promos | — | — |
| Online course promos | `<sender@example.com>` | — |
| Software promos | `<sender@example.com>` | — |
| Social platform announcements | `<sender@example.com>` | — |

<!-- TODO: fill in with the user's actual senders -->

### By content (delete)

- Generic commercial promotions (offers, discounts, marketing)
- Spam or irrelevant emails
- Re-engagement emails ("we miss you", "come back")

### Safeguard

BEFORE labeling as delete, verify there is nothing relevant hidden: an interesting event, a concrete professional opportunity, a pending payment. If there is, DO NOT label and mention it in the summary.

---

## Archive (remove from inbox)

### By sender (always archive)

| Sender | Address | Notes |
|---|---|---|
| Ride service receipts | `<sender@example.com>` | Keep, not in inbox |
| Account security alerts | `<sender@example.com>` | — |
| Automatic payment receipts | `<sender@example.com>` | — |
| Tech newsletter A | `<sender@example.com>` | — |
| Tech newsletter B | `<sender@example.com>` | — |
| Membership platform | `<sender@example.com>` | Already summarized |
| Product changelogs | `<sender@example.com>` | — |
| Dev tools newsletters | `<sender@example.com>` | — |
| Expense sharing platform | `<sender@example.com>` | — |
| Learning app | `<sender@example.com>` | — |
| Video game store | `<sender@example.com>` | — |
| Substack/Quora newsletter | `<sender@example.com>` | — |
| Airline loyalty program | `<sender@example.com>` | — |
| Bank post-transaction surveys | `<sender@example.com>` | If >1 day old |
| Bank spending notifications | `<sender@example.com>` | Already seen |
| Bank statements | `<sender@example.com>` | — |
| Cloud billing receipts | `<sender@example.com>` | — |
| Community/NGO newsletter | `<sender@example.com>` | Already summarized |
| SaaS product updates | `<sender@example.com>` | Terms/product |
| Social app notifications | `<sender@example.com>` | — |
| Wallet/parking notifications | `<sender@example.com>` | — |

<!-- TODO: fill in with the user's actual senders -->

### By content (archive)

- Tech newsletters and updates already read/summarized
- Informational group emails where no response is needed
- Conversation threads where the topic is already resolved
- Invitations to past events

---

## Keep in inbox (never archive automatically)

### Priority senders

| Domain | Context |
|---|---|
| `<org-domain-1.org>` | `<PROJECT_NAME>` — brief description |
| `<org-domain-2.org>` | `<PROJECT_NAME>` — brief description |
| `<org-domain-3.org>` | `<CONTACT_NAME>` — active business contact |

<!-- List domains of projects/people that should NEVER be archived -->

### Security alerts

| Sender | Address | Reason |
|---|---|---|
| Sensitive bank/service | `<sender@example.com>` | The user does not actively use this product. Any activity is a red flag. Keep + action required. |

### By content (keep)

- Emails where the user is in To: or Cc: directly on active work topics
- Emails with label IMPORTANT + CATEGORY_PERSONAL
- Emails that require a response (with draft created)
- Event invitations the user must decide whether to attend
- Anything with an upcoming deadline or urgency

### Billing/payment issues (always keep + mark action required)

- Rejected payments from any service
- Hosting/SaaS suspensions
- Failed subscription payments
- App store billing
- Insurance/health plan overdue payments
- Any email about failed payment, overdue balance, or service suspension

**Repetitive payment emails:** if there are multiple emails about the same issue, keep only the most recent in inbox, archive the rest. Mention it as "recurring unresolved issue".

---

## Evolution notes

<!-- Optional log: record when senders or rules are added/removed -->

- YYYY-MM-DD: File created from `secretary-core` template.
