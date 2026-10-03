# Daily sync routine

Prompt for the scheduled Claude routine (fresh session each run, in this repo, with `SIMPLEFIN_ACCESS_URL` set). Replace `<DASHBOARD_URL>` with the dashboard's claude.ai link.

---

Sync the Patterson Spending dashboard at <DASHBOARD_URL>.

1. Read the dashboard's `rules` collection with ArtifactData `list`. Write it to `out/overrides.json` as `{"<merchant>": "<category>"}`.
2. Run `python -m sync.main --overrides out/overrides.json`. If it fails, set doc `meta/sync` to `{status: "error", message, at}` and send a push notification with the error. Stop there.
3. Open `out/sync.json`. For each transaction with category `Uncategorized`, pick the best category from: Groceries, Dining, Shopping, Gas, Transportation, Utilities, Subscriptions, Insurance, Health, Home, Kids, Travel, Entertainment, Gifts, Fees, Income, Transfer. Leave it `Uncategorized` if unclear.
4. Do not overwrite a transaction whose existing doc has `categoryLocked: true`. That flag means someone re-categorized it on the dashboard.
5. Write with ArtifactData `batch`, using each row's `id` as the doc id:
   - `accounts/<id>`: use `update` so `apr` and other fields entered on the page are kept.
   - `transactions/<id>`: use `update`.
   - `balances/<snapshot.id>`: use `set`.
   - `meta/sync`: `{status: "ok", at: syncedAt, accounts: n, transactions: n, errors: [...]}`.
6. Read `budgets` and `bills`. Send a push notification only if a bill is due within 3 days and not marked paid, or a category is over budget this month. Otherwise stay silent.
