# Daily sync routine

Prompt for the scheduled Claude routine: a fresh session each run in this repo, at 5:49am Mountain, with the environment variable `SIMPLEFIN_ACCESS_URL` set.

Dashboard: https://claude.ai/artifact/8Aq4chNUNzxC1oL9jMxuBg (source in `dashboard/index.html`).

---

Sync the Patterson Spending dashboard at https://claude.ai/artifact/8Aq4chNUNzxC1oL9jMxuBg. Never print the SimpleFIN access URL, balances or transactions in chat.

1. If `SIMPLEFIN_ACCESS_URL` is not set, write doc `meta/sync` as `{status: "error", message: "SIMPLEFIN_ACCESS_URL is missing from the environment settings", at: <now>}`. Send a push notification saying so, then stop.
2. Read the dashboard's `rules` collection with ArtifactData `list`. Write rules without `scope` to `out/overrides.json` and rules with `scope: "business"` to `out/business_overrides.json`, both as `{"<merchant>": "<category>"}`. Then read the `accounts` collection and write the ids of accounts with `business: true` to `out/business_accounts.json` as a JSON list (an empty list if there are none).
3. Run `python -m sync.main --overrides out/overrides.json --business-accounts out/business_accounts.json --business-overrides out/business_overrides.json`. If it fails, write `meta/sync` as `{status: "error", message, at}`, send a push notification with the error, and stop.
4. In `out/sync.json`, give each `Uncategorized` transaction its best category from: Groceries, Dining, Shopping, Gas, Transportation, Utilities, Subscriptions, Insurance, Health, Home, Kids, Travel, Entertainment, Games, Gifts, Fees, Income, Transfer. For transactions on business accounts (ids in `out/business_accounts.json`), use this list instead: Contract Income, Private Pay, Groups & Workshops, Training & Supervision, Program Sales, Other Income, Instruments & Equipment, Music & Licensing, Therapy Supplies, Continuing Education, Certification & Licensing, Memberships, Liability Insurance, Software & Apps, Marketing & Website, Rent & Space, Contractors, Phone & Internet, Travel & Meals, Bank & Payment Fees, Office Supplies, Other Expense, Owner Draw, Owner Contribution, Tax Payment, Transfer. On business accounts, a clearly personal purchase (groceries, rent, personal shopping, family trips) is `Owner Draw`, and meals while traveling are `Travel & Meals`. Leave it `Uncategorized` if it's unclear.
5. Export the current database with ArtifactData `list` and `out_dir: out/existing`, paging with `cursor` until done:
   - `accounts`
   - `transactions` (query `where date >= <earliest date in out/sync.json>`, limit 1000)
   - `balances` (query `where date == <today>`)
   - `meta`
   Note each listed doc's `version`.
6. Run `python -m sync.plan_writes --existing out/existing --business-accounts out/business_accounts.json`. Apply every `out/batches/new*.json` file with ArtifactData `batch`, passing the file's entries as `writes`.
7. For each id in `out/pinned.json`, write `{"<collection>/<doc_id>": <version from step 5>}` into `out/versions.json`. Then run `python -m sync.plan_writes --existing out/existing --business-accounts out/business_accounts.json --versions out/versions.json` and apply `out/batches/pinned*.json` the same way. If a batch is refused because a version changed, re-read that doc and redo steps 5–7 once.
8. Read `budgets`, `bills`, `invoices`, `taxPayments` and `meta/business`. Send a push notification only in these cases:
   - a bill is due within 3 days and its `paidMonth` isn't the current month
   - a household credit card (`type: "credit"`, not `business`) with a `dueDay` is due within 3 days, it owes money, and no payment (a positive amount described like PAYMENT, AUTOPAY or THANK YOU) has posted on it in the 28 days before that due date
   - a category is over budget this month
   - a business invoice with no `paidDate` is 30 or more days past its `due` date (or `issued` + 30 days when `due` is empty). Use the client code, never more.
   - a quarterly estimated tax payment is due within 7 days (Apr 15, Jun 15, Sep 15, Jan 15) and no `taxPayments` doc or business `Tax Payment` transaction for that quarter exists this year
   - `out/sync.json` lists SimpleFIN errors, such as a bank that needs to be reconnected
   - a bank has stopped updating: every account from one institution in `out/sync.json` has a `balanceDate` 2 or more days old. Name the bank and say to reconnect it in SimpleFIN Bridge. Send this at most once per bank per day.

   Otherwise stay silent.
