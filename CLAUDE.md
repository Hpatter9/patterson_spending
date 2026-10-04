# Patterson Spending

Household and business budget tracker for the Patterson family. Several Claude sessions work on this repo, so this file keeps them in sync.

## Before you change anything
1. Work on branch **`ccr-dbafe857-rn6jty`**. It's the source of truth, and the daily sync runs from it. Run `git pull origin ccr-dbafe857-rn6jty` first. If your session is on another branch, merge it into this one and push here.
2. The dashboard is one live page: https://claude.ai/artifact/8Aq4chNUNzxC1oL9jMxuBg. Its source is `dashboard/index.html`.
   - Before editing, read the live version (Artifact `read`) and diff it against the file. Someone else may have published since the last commit. Merge their changes into the file and never publish over them.
   - Publish from `dashboard/index.html`, then commit and push in the same turn, so the repo always matches what's live.
3. Run `python3 -m unittest` before every push.
4. Update **Current state** below in the same commit when you add or change a feature, collection or routine step.

## Never
- Commit financial data, account numbers or the SimpleFIN key. Real data goes only in `out/`, which is gitignored, and gets deleted after use.
- Print balances, transactions or the SimpleFIN key in chat.
- Archive the session **"Patterson Spending sync runner"** (`session_01ChAZqxCkdwSczEvntTNUfV`). The daily routine runs in it.
- Store client names or health details for the business. Use client codes or initials only.

## Current state
**Bank sync.** The routine "Patterson Spending daily sync" (`trig_01V6M5B6nfb3KVZThyC58i7n`) runs at 5:49am America/Denver in the sync runner session. It follows `ROUTINE.md`, so change the steps there, not in the trigger.
- `sync/` pulls from SimpleFIN (`SIMPLEFIN_ACCESS_URL` is set in the environment settings) and categorizes with `sync/rules.json` for household accounts and `sync/business_rules.json` for business accounts.
- `sync/plan_writes.py` turns `out/sync.json` into database batches. The database refuses changes to an existing row unless the write names the row's version, so new rows are sent as-is and changed rows go in a second pass with their versions.

**Dashboard database collections:**
- `accounts`: synced accounts. Ids starting `m_` were added by hand, and the sync never touches them. Business accounts carry `business: true`.
- `transactions`, `balances/{date}`, `meta/sync`: written by the sync.
- `budgets`, `bills`, `rules`: edited on the page. A `rules` doc with `scope: "business"` is a business merchant rule.
- `invoices`, `mileage`, `taxPayments`, `meta/business`: Business tab.

**Account types:** checking, savings, credit, loan, investment, and hidden (duplicates or $0 policies, set in `rules.json` → `account_types`).

**Two sides, picked from the title dropdown** (`SPACES` in `dashboard/index.html`; the choice is remembered per browser):
- **Patterson Spending** (personal): This Month, Where It Goes, Net Worth & Debt, Bills, Ask.
- **Get In Tune** (her music therapy practice, getintunemusictherapy.com): Overview, Invoices, Mileage, Taxes, Setup, Ask. It has its own color tokens under `body[data-space="biz"]`. These are provisional purple until her site's brand colors are applied; the site is blocked by this environment's network settings.
- Each side keeps its own Ask conversation and suggestions.
- Budget rows, category bars and merchants open a detail panel.
- Ask is a Claude companion. It runs on the viewer's own account through the page's ability to call Claude. It can propose changes, which save only when the viewer taps Apply.
