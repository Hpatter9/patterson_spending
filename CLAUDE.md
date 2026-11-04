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
**Bank sync.** The routine "Patterson Spending daily sync" (`trig_01V6M5B6nfb3KVZThyC58i7n`) runs at 5:49am America/Denver in the sync runner session. It follows `ROUTINE.md`, so change the steps there, not in the trigger. If every account at one bank has a `balanceDate` 2+ days old, the bank connection in SimpleFIN has stalled (Chase does this). The dashboard shows a warning (`staleBanks()`), and the morning sync sends a notification.

**Ask answer queue.** Viewers whose account can't run live Ask (her free account) get a send-a-question box. The routine "Patterson Spending: answer Ask questions" (`trig_01KMWWxzE85d8cXu7dxwXJzw`) runs three times a day (7:52am, 12:52pm and 6:52pm Mountain) in the same runner session, on the owner's account, and follows `ASK_QUEUE.md`. It used to run hourly, but that used up the account's weekly limit and stopped the morning sync (Oct 25–28), so keep it to a few runs a day.
- `sync/` pulls from SimpleFIN (`SIMPLEFIN_ACCESS_URL` is set in the environment settings) and categorizes with `sync/rules.json` for household accounts and `sync/business_rules.json` for business accounts.
- When an account is marked business after its transactions synced, `plan_writes --business-accounts` swaps their household categories for business ones on the next sync (categories she picked by hand, `categoryLocked`, never change). `BUSINESS_CATEGORIES` in `sync/categorize.py` must match the dashboard's lists; a test checks this.
- `sync/plan_writes.py` turns `out/sync.json` into database batches. The database refuses changes to an existing row unless the write names the row's version, so new rows are sent as-is and changed rows go in a second pass with their versions.

**Dashboard database collections:**
- `accounts`: synced accounts. Ids starting `m_` were added by hand, and the sync never touches them. Business accounts carry `business: true`.
- `transactions`, `balances/{date}`, `meta/sync`: written by the sync.
- `budgets`, `bills`, `rules`: edited on the page. A `rules` doc with `scope: "business"` is a business merchant rule. Picking a business category also moves her other not-yet-picked charges from the same merchant.
- `invoices`, `mileage`, `taxPayments`, `meta/business`: Business tab.
- `questions`: the Ask answer queue (see `ASK_QUEUE.md`).
- `rewards`: card perks and points, edited on the Rewards tab.
  - `card_<accountId>`: `product`, `annivMonth`, `used{<perk>_<period>}` (a dollar amount, or a date for every-4-years perks), `perks{<perk>: {amount, off}}`, `custom{<key>: {name, amount, per}}`.
  - `prog_<program>`: `balance`, `asOf`, `cpp`.

**Account types:** checking, savings, credit, loan, investment, and hidden (duplicates or $0 policies, set in `rules.json` → `account_types`).

**Account names:** `rules.json` → `account_names` overrides the names the bank sends, by dashboard id. Example: Chase sends the Ink cards as "H. PATTERSON". The Chase Ink cards are Hunter's and belong on the personal side, not Get In Tune.

**Two sides, picked from the title dropdown** (`SPACES` in `dashboard/index.html`; the choice is remembered per browser):
- **Patterson Spending** (personal): This Month, Where It Goes, Net Worth & Debt, Bills, Rewards, Grow, Fun Facts, Ask.
- **Fun Facts** (`viewFun`) is worked out in the browser from synced transactions, so it stores nothing and works on her free account. It has three parts:
  - a fact-of-the-day card with an "Another one" button
  - monthly badges (`funBadges`)
  - last month "wrapped", plus a grid of facts (`funFacts`), such as coffee runs, meals out, most-visited place, no-spend days, round-ups, gas miles and spending pace
  - Coffee and Amazon are matched by the `COFFEE` and `AMAZON` regexes.
- **Get In Tune** (her music therapy practice, getintunemusictherapy.com): Overview, Invoices, Mileage, Taxes, Setup, Fun Facts, Ask. It has its own brand tokens under `body[data-space="biz"]`, taken from her site: indigo #352c73/#4a439e, violet #a12db5, Oswald headings and Assistant text. Her services are the default service lines in `BIZ_DEFAULTS`. Her logo (from static.wixstatic.com, trimmed to 314×112) is embedded in the header as a WebP data URI (`#bizLogo`), on a light background in dark mode.
- Each side keeps its own Ask conversation and suggestions.
- Budget rows, category bars and merchants open a detail panel. It shows an exact charges − refunds = total breakdown and a pending note (`catMath`), and budget rows carry a short pending/refunds line.
- **The personal side counts household accounts only** (`homeAccts()`). Net worth, its history (`netWorthSeries()`, built from each snapshot's per-account `balances`) and Ask's net worth all leave out `business: true` accounts. Net Worth & Debt notes how many it left out.
- **Card due days and APRs.** SimpleFIN doesn't send them, so they're `dueDay` and `apr` on each account, typed in on Net Worth & Debt.
  - `cardTerms()` estimates them from history: the due day from the day payments usually post, and the APR from the latest interest charge ÷ the average balance in the 31 days of snapshots before it × 365/30.
  - "Fill in estimates" (`cardFills()`) writes only fields that are still empty.
  - Bills shows a Credit cards panel (`cardBillsPanel()`) with each card's next due date and today's balance, and marks it paid when a payment posted in the 4 weeks before.
- **Rewards** (`viewRewards`) covers every credit card.
  - `REWARD_CARDS` is the catalog of card products: program, earn rates and perks. A perk has an amount and resets monthly, every 6 months, each calendar year, each card year or every 4 years. Amounts are as of October 2026, so update the catalog when issuers change them.
  - `CARD_GUESS` picks each card's product from its name. Cards the bank sends only as a cardholder name ("M. WOODS") get picked on the page. Chase business cards, including the Sapphire Reserve for Business (`csrb`), arrive this way.
  - The tab has three views (`S.rwView`):
    - **Credits:** a "use before it resets" list, then one collapsible block per card.
    - **Points:** balances by program.
    - **Cards:** setup items first, then every card with Edit.
  - **Card year start** (`rwAnniv()`): a month set on the page wins, and the year starts on the 1st of it. Otherwise the start is estimated as 30 days before the card's last ANNUAL MEMBERSHIP FEE. Chase charges the fee on the first statement *after* the anniversary, so the Sapphire Reserve ·1983's Aug 1 fee means its card year began in early July. Its three July travel credits (exactly $300) belong to the current card year. Estimated resets say "around".
  - **Travel credits applied automatically** (`autoTravel` on the Sapphire Reserve and Reserve for Business): if travel charges (`TRAVELISH`: Travel category, rideshare, parking, tolls, transit) of $25 or more, at least 5 days old, posted after the last credit and got no credit, the $300 is treated as used up (`travelUsedUp()`). The page explains why.
  - Resets are shown as dates ("Resets Aug 1, 2027"). The synced history only goes back about 3 months (`histStart()`), so cards with longer periods say that credits used before then must be marked by hand.
  - **Edit card** (under Cards) sets the card's product, renewal month and name.
  - **Card names.** The name is saved as `nickname` on the account doc. The sync never writes that field, and the page shows it everywhere in place of the bank's name (`bankName` keeps the original).
  - The Southwest Priority card's $75 travel credit ended in 2025, so it's not in the catalog.
  - A perk counts as used from whichever is more: matching statement credits on that card (the perk's `match` regex, positive amounts) or what was logged by hand.
  - Points balances aren't in SimpleFIN, so they're typed in. "Earned since" estimates points from purchases since then × the earn rates.
  - Ask sees the balances and the perks about to reset (`rewardsSnapshot()`).
- **Grow** (`viewGrow`) has two views (`S.growView`).
  - **Suggestions** (`suggestions()`): rule-based tips from the household's own numbers, ranked "Do first" / "Worth doing" / "Good to know". They cover:
    - card balances charging interest (highest APR first) and recent interest paid
    - emergency cushion in months of spending, and idle checking
    - monthly surplus or gap over the last 3 full months
    - a category on pace to run high, and budgets already over
    - subscriptions
    - card credits about to reset
    - card utilization, high-rate loans, and investment accounts that stopped updating

    Each tip can open Ask with a question filled in (`data-sg-ask`). They're general guidance, not financial advice, and the page says so.
  - **Investments** (`viewInvest`):
    - household `investment` accounts summed per daily snapshot (`invSeries()`), shown as a value line chart
    - a day-to-day change bar chart (`changeBars()`)
    - latest-day, past-week and since-start changes
    - a per-account table that flags accounts not updated for 4+ days

    Changes include contributions and withdrawals, and days without a sync are skipped.
- **Get In Tune also has Fun Facts** (`viewBizFun`): invoices, mileage, profit and badges. It names clients by their code only.
- Ask is a Claude companion. It runs on the viewer's own account through the page's ability to call Claude. It can propose changes, which save only when the viewer taps Apply.
