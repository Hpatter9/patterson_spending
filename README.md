# Patterson Spending

Household budget and spending tracker.

- **Dashboard:** a private claude.ai page with tabs for this month vs budget, where money goes, net worth and debt, and bills.
- **Sync:** `sync/` pulls balances and transactions from [SimpleFIN Bridge](https://beta-bridge.simplefin.org) (read-only) and writes `out/sync.json`.
- **Daily routine:** a scheduled Claude session runs the sync and loads the results into the dashboard's database. See [ROUTINE.md](ROUTINE.md).

**No financial data is ever committed.** `out/`, CSVs and `.env` files are gitignored. The SimpleFIN access URL lives only in the Claude environment secret `SIMPLEFIN_ACCESS_URL`.

## Setup

1. Create an account at beta-bridge.simplefin.org, link each bank, card and loan, then create a **setup token**.
2. Exchange the token once for an access URL:
   `python -m sync.main --claim <setup-token>`
3. Add the printed URL as the secret `SIMPLEFIN_ACCESS_URL` in the Claude cloud environment settings.
4. Test it: `python -m sync.main` (prints account and transaction counts).

## Development

```
python -m unittest                                          # tests, fake data only
python -m sync.main --fixture tests/fixtures/simplefin_sample.json
```

Merchant → category rules live in `sync/rules.json`. Re-categorizing a transaction on the dashboard saves a rule to the dashboard's `rules` collection, and the next sync applies it via `--overrides`. To fix a misdetected account type, add `"<simplefin account id>": "checking|savings|credit|loan"` under `account_types`.

Python 3.9+, standard library only.
