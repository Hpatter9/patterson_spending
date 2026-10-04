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

    def test_account_type_detection(self):
        cases = {
            ("Venture X", "Capital One"): "credit",
            ("World of Hyatt", "Chase Bank"): "credit",
            ("Blue Cash Everyday®", "American Express"): "credit",
            ("Everyday Checking", "Example Bank"): "checking",
            ("Live Life Funds", "Bank of America"): "checking",
            ("Roth IRA Brokerage Account", "Vanguard"): "investment",
            ("65 LIFE", "NorthWestern Mutual"): "investment",
            ("Joint Savings", "Bellco Credit Union"): "savings",
            ("Auto Loan 3333", "Example Auto Finance"): "loan",
            ("M. WOODS", "Chase Bank"): "credit",
            ("H. PATTERSON", "Chase Bank"): "credit",
            ("M. WOODS (...7731)", "Chase Bank"): "credit",
            ("M. WOODS 7731", "Chase Bank"): "credit",
        }
        for (name, inst), want in cases.items():
            self.assertEqual(account_type(name, institution=inst), want, name)

    def test_interest_charges_mean_credit(self):
        self.assertEqual(account_type("monaay", institution="Bank of America", descriptions=["Interest Charge"]), "credit")
        self.assertEqual(account_type("monaay", institution="Bank of America", descriptions=["Interest Income"]), "checking")

    def test_hidden_accounts_are_dropped(self):
        raw = json.loads(FIXTURE.read_text())
        loan_id = next(a for a in run()["accounts"] if a["type"] == "loan")["id"]
        rules = load_rules()
        rules["account_types"] = {loan_id: "hidden", "ACT-card-1": "hidden"}  # dashboard id and SimpleFIN id
        result = normalize(raw, rules, now=NOW)
        self.assertEqual([a["type"] for a in result["accounts"]], ["checking"])
        self.assertEqual(len(result["transactions"]), 4)

    def test_account_type_override(self):
        self.assertEqual(account_type("Joint Account"), "checking")
        self.assertEqual(account_type("Joint Account", "savings"), "savings")


class ClientTest(unittest.TestCase):
    def test_credentials_split_from_url(self):
        base, auth = _split_credentials("https://user:p%40ss@bridge.example/simplefin/")
        self.assertEqual(base, "https://bridge.example/simplefin")
        self.assertEqual(auth, "Basic dXNlcjpwQHNz")  # base64("user:p@ss")

    def test_requests_send_user_agent(self):
        from unittest import mock
        from sync import simplefin
        seen = []
        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return b"https://u:p@bridge.example/simplefin"
        def fake_urlopen(req, timeout):
            seen.append(req.get_header("User-agent"))
            return Resp()
        with mock.patch.object(simplefin.urllib.request, "urlopen", fake_urlopen), \
             mock.patch.object(simplefin.json, "load", lambda r: {}):
            simplefin.claim_setup_token("aHR0cHM6Ly9icmlkZ2UuZXhhbXBsZS9jbGFpbS94")
            simplefin.fetch_accounts("https://u:p@bridge.example/simplefin")
        self.assertEqual(seen, [simplefin.USER_AGENT] * 2)

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
