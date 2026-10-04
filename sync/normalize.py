"""Turn a raw SimpleFIN /accounts response into dashboard database rows.

Only institution, account name and last 4 digits are kept. Liabilities
(credit cards, loans) carry negative balances so net worth is a plain sum.
"""
import hashlib
import re
from datetime import datetime, timezone

from .categorize import categorize

LOAN_WORDS = ("LOAN", "MORTGAGE", "AUTO ", "STUDENT", "HELOC", "LINE OF CREDIT")
CREDIT_WORDS = ("CREDIT", "CARD", "VISA", "MASTERCARD", "AMEX", "DISCOVER", "REWARDS", "SAPPHIRE", "FREEDOM",
                "VENTURE", "BLUE CASH", "EVERYDAY", "SLATE", "HYATT", "FRONTIER", "WYNDHAM", "SIMPLICITY",
                "BANKAMERICARD", "PLATINUM", "EARNER", "PRIORITY")
SAVINGS_WORDS = ("SAVING", "MONEY MARKET", "CD ")
INVESTMENT_WORDS = ("IRA", "BROKERAGE", "ROTH", "401K", "403B", "ANNUITY", "INVESTMENT")
INVESTMENT_INSTITUTIONS = ("VANGUARD", "NORTHWESTERN MUTUAL", "FIDELITY", "SCHWAB", "BETTERMENT", "WEALTHFRONT")
CARD_ISSUERS = ("AMERICAN EXPRESS", "BARCLAYS", "CAPITAL ONE", "DISCOVER")  # rarely anything but cards here
LIABILITY_TYPES = ("credit", "loan")
HIDDEN = "hidden"


def doc_id(prefix, *parts):
    """Stable, database-safe id, so re-syncing the same item overwrites instead of duplicating."""
    return prefix + "_" + hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


CARDHOLDER_NAME = re.compile(r"^[A-Z]\. ?[A-Z' -]+$")  # Chase labels some cards "M. WOODS"


def account_type(name, override=None, institution="", descriptions=()):
    if override:
        return override
    text, inst = f"{name} ".upper(), (institution or "").upper()
    if any(w in inst for w in INVESTMENT_INSTITUTIONS) or any(f" {w} " in f" {text} " for w in INVESTMENT_WORDS):
        return "investment"
    if any(w in text for w in LOAN_WORDS):
        return "loan"
    if "CHECKING" in text:
        return "checking"
    if any(w in text for w in CREDIT_WORDS):
        return "credit"
    if any(w in text for w in SAVINGS_WORDS):
        return "savings"
    if any(w in inst for w in CARD_ISSUERS) and "360" not in text:
        return "credit"
    # Unlabeled accounts: a cardholder name, or interest charges, mean a credit card.
    bare = re.sub(r"[\s(.x-]*\d{4}\)?\s*$", "", (name or "").strip().upper(), flags=re.I)
    if CARDHOLDER_NAME.match(bare) or any("INTEREST CHARGE" in d.upper() for d in descriptions):
        return "credit"
    return "checking"


def last4(name):
    digits = re.findall(r"\d{4}", name or "")
    return digits[-1] if digits else ""


def _iso_date(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()


def normalize(raw, rules, now=None, business_rules=None, business_accounts=()):
    """business_accounts: dashboard (a_...) or SimpleFIN ids whose transactions use business_rules."""
    now = now or datetime.now(timezone.utc)
    business_accounts = set(business_accounts)
    type_overrides = rules.get("account_types", {})
    accounts, transactions = [], []

    for acct in raw.get("accounts", []):
        org = acct.get("org") or {}
        institution = org.get("name") or org.get("domain") or "Unknown"
        acct_id = doc_id("a", institution, acct["id"])
        # Overrides in rules.json may use the dashboard id (a_...) or SimpleFIN's own id.
        descriptions = [t.get("description") or "" for t in acct.get("transactions", [])]
        kind = account_type(acct.get("name", ""), type_overrides.get(acct_id) or type_overrides.get(acct["id"]),
                            institution, descriptions)
        if kind == HIDDEN:  # duplicates, $0 policies and other accounts not worth tracking
            continue
        acct_rules = rules
        if business_rules and (acct_id in business_accounts or acct["id"] in business_accounts):
            acct_rules = business_rules
        balance = float(acct.get("balance") or 0)
        # Banks report card/loan balances with either sign; store liabilities as negative.
        if kind in LIABILITY_TYPES:
            balance = -abs(balance)
        accounts.append({
            "id": acct_id,
            "name": re.sub(r"\s*\(?\.*\d{4}\)?\s*$", "", acct.get("name", "")).strip() or acct.get("name", ""),
            "institution": institution,
            "last4": last4(acct.get("name")),
            "type": kind,
            "balance": round(balance, 2),
            "available": float(acct["available-balance"]) if acct.get("available-balance") else None,
            "currency": acct.get("currency", "USD"),
            "balanceDate": _iso_date(acct["balance-date"]) if acct.get("balance-date") else None,
            "updatedAt": now.isoformat(timespec="seconds"),
        })

        for txn in acct.get("transactions", []):
            amount = float(txn["amount"])
            payee = (txn.get("payee") or txn.get("description") or "").strip()
            when = txn.get("transacted_at") or txn.get("posted")
            transactions.append({
                "id": doc_id("t", institution, acct["id"], txn["id"]),
                "accountId": acct_id,
                "date": _iso_date(when),
                "amount": round(amount, 2),
                "payee": payee,
                "description": (txn.get("description") or "").strip(),
                "category": categorize(f"{payee} {txn.get('description', '')}", amount, acct_rules),
                "pending": bool(txn.get("pending")),
            })

    snapshot = {
        "id": now.date().isoformat(),
        "date": now.date().isoformat(),
        "balances": {a["id"]: a["balance"] for a in accounts},
        "netWorth": round(sum(a["balance"] for a in accounts), 2),
    }
    return {
        "syncedAt": now.isoformat(timespec="seconds"),
        "errors": list(raw.get("errors", [])),
        "accounts": accounts,
        "transactions": sorted(transactions, key=lambda t: t["date"], reverse=True),
        "snapshot": snapshot,
    }
