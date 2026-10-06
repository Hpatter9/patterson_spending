"""Assign spending categories to transactions using merchant keyword rules."""
import json
from pathlib import Path

DEFAULT_RULES = Path(__file__).with_name("rules.json")
BUSINESS_RULES = Path(__file__).with_name("business_rules.json")

UNCATEGORIZED = "Uncategorized"
TRANSFER = "Transfer"
INCOME = "Income"
OWNER_DRAW = "Owner Draw"
OWNER_CONTRIBUTION = "Owner Contribution"
# Must match BIZ_INCOME, BIZ_EXPENSE and BIZ_CATEGORIES in dashboard/index.html.
BUSINESS_CATEGORIES = (
    "Contract Income", "Private Pay", "Groups & Workshops", "Training & Supervision", "Program Sales", "Other Income",
    "Instruments & Equipment", "Music & Licensing", "Therapy Supplies", "Continuing Education", "Certification & Licensing",
    "Memberships", "Liability Insurance", "Software & Apps", "Marketing & Website", "Rent & Space", "Contractors",
    "Phone & Internet", "Travel & Meals", "Bank & Payment Fees", "Office Supplies", "Other Expense",
    OWNER_DRAW, OWNER_CONTRIBUTION, "Tax Payment", TRANSFER, UNCATEGORIZED,
)


def load_rules(path=DEFAULT_RULES, overrides=None):
    """Load rules.json, then layer on overrides saved from the dashboard (merchant -> category)."""
    rules = json.loads(Path(path).read_text())
    merchants = {k.upper(): v for k, v in rules.get("merchants", {}).items()}
    merchants.update({k.upper(): v for k, v in (overrides or {}).items()})
    rules["merchants"] = merchants
    rules["transfer_keywords"] = [k.upper() for k in rules.get("transfer_keywords", [])]
    rules["income_keywords"] = [k.upper() for k in rules.get("income_keywords", [])]
    rules["owner_keywords"] = [k.upper() for k in rules.get("owner_keywords", [])]
    return rules


def categorize(payee, amount, rules):
    text = (payee or "").upper()
    # Longest keyword wins, so "AMAZON PRIME" beats "AMAZON".
    for keyword in sorted(rules["merchants"], key=len, reverse=True):
        if keyword in text:
            return rules["merchants"][keyword]
    # Business rules only: money moving to or from household accounts.
    if any(k in text for k in rules["owner_keywords"]):
        return OWNER_CONTRIBUTION if amount > 0 else OWNER_DRAW
    if any(k in text for k in rules["transfer_keywords"]):
        return TRANSFER
    if amount > 0 and any(k in text for k in rules["income_keywords"]):
        return rules.get("income_category", INCOME)
    return UNCATEGORIZED
