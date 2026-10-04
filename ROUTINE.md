# Daily sync routine

Prompt for the scheduled Claude routine: a fresh session each run in this repo, at 5:49am Mountain, with the environment variable `SIMPLEFIN_ACCESS_URL` set.

Dashboard: https://claude.ai/artifact/8Aq4chNUNzxC1oL9jMxuBg (source in `dashboard/index.html`).

---

Sync the Patterson Spending dashboard at https://claude.ai/artifact/8Aq4chNUNzxC1oL9jMxuBg. Never print the SimpleFIN access URL, balances or transactions in chat.

1. If `SIMPLEFIN_ACCESS_URL` is not set, write doc `meta/sync` as `{status: "error", message: "SIMPLEFIN_ACCESS_URL is missing from the environment settings", at: <now>}`. Send a push notification saying so, then stop.
2. Read the dashboard's `rules` collection with ArtifactData `list`. Write it to `out/overrides.json` as `{"<merchant>": "<category>"}`.
3. Run `python -m sync.main --overrides out/overrides.json`. If it fails, write `meta/sync` as `{status: "error", message, at}`, send a push notification with the error, and stop.
4. In `out/sync.json`, give each `Uncategorized` transaction its best category from: Groceries, Dining, Shopping, Gas, Transportation, Utilities, Subscriptions, Insurance, Health, Home, Kids, Travel, Entertainment, Games, Gifts, Fees, Income, Transfer. Leave it `Uncategorized` if it's unclear.
5. Export the current database with ArtifactData `list` and `out_dir: out/existing`, paging with `cursor` until done:
   - `accounts`
   - `transactions` (query `where date >= <earliest date in out/sync.json>`, limit 1000)
   - `balances` (query `where date == <today>`)
   - `meta`
   Note each listed doc's `version`.
6. Run `python -m sync.plan_writes --existing out/existing`. Apply every `out/batches/new*.json` file with ArtifactData `batch`, passing the file's entries as `writes`.
7. For each id in `out/pinned.json`, write `{"<collection>/<doc_id>": <version from step 5>}` into `out/versions.json`. Then run `python -m sync.plan_writes --existing out/existing --versions out/versions.json` and apply `out/batches/pinned*.json` the same way. If a batch is refused because a version changed, re-read that doc and redo steps 5–7 once.
8. Read `budgets` and `bills`. Send a push notification only in these cases:
   - a bill is due within 3 days and its `paidMonth` isn't the current month
   - a category is over budget this month
   - `out/sync.json` lists SimpleFIN errors, such as a bank that needs to be reconnected

   Otherwise stay silent.
