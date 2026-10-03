"""Assign spending categories to transactions using merchant keyword rules."""
import json
from pathlib import Path

DEFAULT_RULES = Path(__file__).with_name("rules.json")

UNCATEGORIZED = "Uncategorized"
TRANSFER = "Transfer"
INCOME = "Income"


def load_rules(path=DEFAULT_RULES, overrides=None):
    """Load rules.json, then layer on overrides saved from the dashboard (merchant -> category)."""
    rules = json.loads(Path(path).read_text())
    merchants = {k.upper(): v for k, v in rules.get("merchants", {}).items()}
    merchants.update({k.upper(): v for k, v in (overrides or {}).items()})
    rules["merchants"] = merchants
    rules["transfer_keywords"] = [k.upper() for k in rules.get("transfer_keywords", [])]
    rules["income_keywords"] = [k.upper() for k in rules.get("income_keywords", [])]
    return rules


def categorize(payee, amount, rules):
    text = (payee or "").upper()
    # Longest keyword wins, so "AMAZON PRIME" beats "AMAZON".
    for keyword in sorted(rules["merchants"], key=len, reverse=True):
        if keyword in text:
            return rules["merchants"][keyword]
    if any(k in text for k in rules["transfer_keywords"]):
        return TRANSFER
    if amount > 0 and any(k in text for k in rules["income_keywords"]):
        return INCOME
    return UNCATEGORIZED
