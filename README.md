# Patterson Spending

Household budget and spending tracker.

- **Dashboard:** [a private claude.ai page](https://claude.ai/artifact/8Aq4chNUNzxC1oL9jMxuBg) (source: `dashboard/index.html`) with tabs for this month vs budget, where money goes, net worth and debt, bills, **Business** (profit by service, invoices, mileage and quarterly tax estimates for the music therapy practice), and **Ask**: a Claude companion that answers questions about your finances and plans purchases using the dashboard's numbers. It runs on the viewer's own Claude account and asks permission on first use.
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

Business accounts are marked in the dashboard's **Business → Setup**. The routine passes their ids with `--business-accounts`, and their transactions are categorized with `sync/business_rules.json` (Schedule C-style categories) plus business rules saved from the dashboard (`rules` docs with `scope: "business"`). Business accounts are left out of household spending but still count toward net worth. Invoices, mileage and tax payments are entered on the dashboard. Clients go in by code or initials only, never names or health details.

Python 3.9+, standard library only.
