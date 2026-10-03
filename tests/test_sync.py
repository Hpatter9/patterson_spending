import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sync.categorize import load_rules
from sync.main import main
from sync.normalize import account_type, normalize
from sync.simplefin import _split_credentials

FIXTURE = Path(__file__).parent / "fixtures" / "simplefin_sample.json"
NOW = datetime(2025, 10, 3, 12, 0, tzinfo=timezone.utc)


def run(overrides=None):
    return normalize(json.loads(FIXTURE.read_text()), load_rules(overrides=overrides), now=NOW)


class NormalizeTest(unittest.TestCase):
    def test_accounts(self):
        accts = {a["last4"]: a for a in run()["accounts"]}
        self.assertEqual(accts["1111"]["type"], "checking")
        self.assertEqual(accts["1111"]["name"], "Everyday Checking")
        self.assertEqual(accts["2222"]["type"], "credit")
        self.assertEqual(accts["2222"]["balance"], -1320.55)
        self.assertEqual(accts["3333"]["type"], "loan")
        self.assertEqual(accts["3333"]["balance"], -14200.00)  # positive loan balance stored as debt

    def test_net_worth_snapshot(self):
        snap = run()["snapshot"]
        self.assertEqual(snap["id"], "2025-10-03")
        self.assertEqual(snap["netWorth"], round(2450.18 - 1320.55 - 14200.00, 2))

    def test_categories(self):
        cats = {t["description"]: t["category"] for t in run()["transactions"]}
        self.assertEqual(cats["KROGER #123 SPRINGFIELD"], "Groceries")
        self.assertEqual(cats["ACME CORP PAYROLL"], "Income")
        self.assertEqual(cats["CREDIT CARD PAYMENT THANK YOU"], "Transfer")
        self.assertEqual(cats["UBER EATS ORDER"], "Dining")  # longest keyword beats "UBER"
        self.assertEqual(cats["UBER TRIP"], "Transportation")
        self.assertEqual(cats["MYSTERY SHOP LLC"], "Uncategorized")

    def test_dashboard_overrides_win(self):
        cats = {t["description"]: t["category"] for t in run({"mystery shop": "Hobbies"})["transactions"]}
        self.assertEqual(cats["MYSTERY SHOP LLC"], "Hobbies")

    def test_ids_are_stable_and_unique(self):
        first, second = run(), run()
        ids = [t["id"] for t in first["transactions"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, [t["id"] for t in second["transactions"]])

    def test_pending_flag(self):
        pending = [t for t in run()["transactions"] if t["pending"]]
        self.assertEqual([t["description"] for t in pending], ["NETFLIX.COM"])

    def test_account_type_override(self):
        self.assertEqual(account_type("Joint Account"), "checking")
        self.assertEqual(account_type("Joint Account", "savings"), "savings")


class ClientTest(unittest.TestCase):
    def test_credentials_split_from_url(self):
        base, auth = _split_credentials("https://user:p%40ss@bridge.example/simplefin/")
        self.assertEqual(base, "https://bridge.example/simplefin")
        self.assertEqual(auth, "Basic dXNlcjpwQHNz")  # base64("user:p@ss")

    def test_missing_credentials(self):
        with self.assertRaises(ValueError):
            _split_credentials("https://bridge.example/simplefin")


class MainTest(unittest.TestCase):
    def test_fixture_run_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sync.json"
            self.assertEqual(main(["--fixture", str(FIXTURE), "--out", str(out)]), 0)
            data = json.loads(out.read_text())
            self.assertEqual(len(data["accounts"]), 3)
            self.assertEqual(len(data["transactions"]), 7)


if __name__ == "__main__":
    unittest.main()
