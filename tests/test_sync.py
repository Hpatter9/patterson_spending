import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sync.categorize import BUSINESS_RULES, load_rules
from sync.main import main
from sync.normalize import account_type, normalize
from sync.simplefin import _split_credentials

FIXTURE = Path(__file__).parent / "fixtures" / "simplefin_sample.json"
BIZ_FIXTURE = Path(__file__).parent / "fixtures" / "simplefin_business_sample.json"
NOW = datetime(2025, 10, 3, 12, 0, tzinfo=timezone.utc)


def run(overrides=None):
    return normalize(json.loads(FIXTURE.read_text()), load_rules(overrides=overrides), now=NOW)


def run_raw(path):
    return normalize(json.loads(Path(path).read_text()), load_rules(), now=NOW)


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


class BusinessTest(unittest.TestCase):
    def run_biz(self, business_accounts=("ACT-biz-1",), overrides=None):
        result = normalize(json.loads(BIZ_FIXTURE.read_text()), load_rules(), now=NOW,
                           business_rules=load_rules(BUSINESS_RULES, overrides), business_accounts=business_accounts)
        accts = {a["id"]: a["last4"] for a in result["accounts"]}
        return {(accts[t["accountId"]], t["description"]): t["category"] for t in result["transactions"]}

    def test_business_categories(self):
        cats = self.run_biz()
        self.assertEqual(cats[("4444", "SPOTIFY USA")], "Music & Licensing")
        self.assertEqual(cats[("4444", "SWEETWATER SOUND")], "Instruments & Equipment")
        self.assertEqual(cats[("4444", "IRS USATAXPYMT")], "Tax Payment")
        self.assertEqual(cats[("4444", "SQUARESPACE")], "Marketing & Website")  # longer merchant beats SQUARE income
        self.assertEqual(cats[("4444", "SQUARE INC DEPOSIT")], "Private Pay")
        self.assertEqual(cats[("4444", "SQUARE INC FEE ADJ")], "Uncategorized")  # income keywords only match deposits
        self.assertEqual(cats[("4444", "MOBILE DEPOSIT")], "Uncategorized")

    def test_owner_transfers(self):
        cats = self.run_biz()
        self.assertEqual(cats[("4444", "ONLINE TRANSFER TO CHK 1111")], "Owner Draw")
        self.assertEqual(cats[("1111", "ONLINE TRANSFER FROM BUSINESS CHK 4444")], "Transfer")

    def test_household_untouched(self):
        cats = self.run_biz()
        self.assertEqual(cats[("1111", "SPOTIFY USA")], "Subscriptions")
        self.assertEqual(cats[("1111", "KROGER #123 SPRINGFIELD")], "Groceries")

    def test_dashboard_id_and_business_overrides(self):
        biz_id = next(a["id"] for a in run_raw(BIZ_FIXTURE)["accounts"] if a["last4"] == "4444")
        cats = self.run_biz(business_accounts=[biz_id], overrides={"mobile deposit": "Contract Income"})
        self.assertEqual(cats[("4444", "MOBILE DEPOSIT")], "Contract Income")

    def test_no_business_accounts_means_household_rules(self):
        cats = self.run_biz(business_accounts=())
        self.assertEqual(cats[("4444", "SPOTIFY USA")], "Subscriptions")


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

    def test_business_accounts_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, ids = Path(tmp) / "sync.json", Path(tmp) / "business_accounts.json"
            ids.write_text(json.dumps(["ACT-biz-1"]))
            self.assertEqual(main(["--fixture", str(BIZ_FIXTURE), "--out", str(out), "--business-accounts", str(ids)]), 0)
            cats = {t["description"]: t["category"] for t in json.loads(out.read_text())["transactions"]}
            self.assertEqual(cats["SWEETWATER SOUND"], "Instruments & Equipment")


if __name__ == "__main__":
    unittest.main()
