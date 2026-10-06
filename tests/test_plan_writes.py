import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sync.categorize import load_rules
from sync.normalize import normalize
from sync.plan_writes import load_existing, main, plan

FIXTURE = Path(__file__).parent / "fixtures" / "simplefin_sample.json"
NOW = datetime(2025, 10, 3, 12, 0, tzinfo=timezone.utc)
EMPTY = {"accounts": {}, "transactions": {}, "balances": {}, "meta": {}}


def fresh_sync():
    return normalize(json.loads(FIXTURE.read_text()), load_rules(), now=NOW)


def stored(sync):
    """What the database holds right after `sync` was written."""
    db = copy.deepcopy(EMPTY)
    for a in sync["accounts"]:
        db["accounts"][a["id"]] = {k: v for k, v in a.items() if k != "id"}
    for t in sync["transactions"]:
        db["transactions"][t["id"]] = {k: v for k, v in t.items() if k != "id"}
    db["balances"][sync["snapshot"]["id"]] = {"netWorth": sync["snapshot"]["netWorth"]}
    db["meta"]["sync"] = {"status": "ok"}
    return db


def keys(writes):
    return {(w["op"], w["collection"], w["doc_id"]) for w in writes}


class PlanTest(unittest.TestCase):
    def test_first_sync_needs_no_versions(self):
        sync = fresh_sync()
        unpinned, pinned = plan(sync, copy.deepcopy(EMPTY))
        self.assertEqual(pinned, [])
        self.assertEqual(len(unpinned), 3 + 7 + 2)  # accounts, transactions, balance, meta

    def test_rerun_only_touches_balance_and_meta(self):
        sync = fresh_sync()
        unpinned, pinned = plan(sync, stored(sync))
        self.assertEqual(unpinned, [])
        self.assertEqual(keys(pinned), {("set", "balances", "2025-10-03"), ("set", "meta", "sync")})

    def test_changed_balance_and_posted_charge(self):
        sync = fresh_sync()
        db = stored(sync)
        acct = sync["accounts"][0]["id"]
        db["accounts"][acct]["balance"] = 1.0
        db["accounts"][acct]["apr"] = 9.9  # entered on the page; must survive
        pending = next(t for t in sync["transactions"] if t["pending"])
        pending["pending"] = False
        _, pinned = plan(sync, db)
        acct_write = next(w for w in pinned if w["collection"] == "accounts")
        self.assertEqual(acct_write["op"], "update")
        self.assertNotIn("apr", acct_write["data"])
        txn_write = next(w for w in pinned if w["doc_id"] == pending["id"])
        self.assertEqual(txn_write["data"], {"pending": False})

    def test_locked_category_is_kept(self):
        sync = fresh_sync()
        db = stored(sync)
        t = next(t for t in sync["transactions"] if t["category"] == "Uncategorized")
        db["transactions"][t["id"]].update(category="Uncategorized", categoryLocked=True)
        t["category"] = "Shopping"
        _, pinned = plan(sync, db)
        self.assertFalse(any(w["doc_id"] == t["id"] for w in pinned))
        db["transactions"][t["id"]]["categoryLocked"] = False
        _, pinned = plan(sync, db)
        self.assertEqual(next(w for w in pinned if w["doc_id"] == t["id"])["data"], {"category": "Shopping"})

    def test_marked_business_replaces_household_category(self):
        sync = fresh_sync()
        db = stored(sync)
        biz = sync["accounts"][1]["id"]  # the card: synced earlier with household categories
        txns = [t for t in sync["transactions"] if t["accountId"] == biz]
        for t in txns:
            t["category"] = "Travel & Meals"  # what the business rules give this run
        locked = txns[0]["id"]
        db["transactions"][locked].update(category="Dining", categoryLocked=True)
        _, pinned = plan(sync, db, business_accounts=[biz])
        changed = {w["doc_id"]: w["data"].get("category") for w in pinned if w["collection"] == "transactions"}
        self.assertNotIn(locked, changed)  # her own pick always wins
        for t in txns[1:]:
            self.assertEqual(changed[t["id"]], "Travel & Meals")
        _, pinned = plan(sync, db)  # not marked business: household categories stay
        self.assertFalse(any(w["collection"] == "transactions" and "category" in w["data"] for w in pinned))

    def test_business_category_is_not_replaced(self):
        sync = fresh_sync()
        db = stored(sync)
        biz = sync["accounts"][1]["id"]
        t = next(t for t in sync["transactions"] if t["accountId"] == biz)
        db["transactions"][t["id"]]["category"] = "Office Supplies"  # already a business category
        t["category"] = "Uncategorized"
        _, pinned = plan(sync, db, business_accounts=[biz])
        self.assertFalse(any(w["doc_id"] == t["id"] and "category" in w["data"] for w in pinned))

    def test_stale_pending_is_deleted(self):
        sync = fresh_sync()
        db = stored(sync)
        some = sync["transactions"][0]
        db["transactions"]["t_stale"] = dict(accountId=some["accountId"], date=some["date"], amount=-5, pending=True)
        db["transactions"]["t_old_posted"] = dict(accountId=some["accountId"], date=some["date"], amount=-5, pending=False)
        _, pinned = plan(sync, db)
        self.assertIn(("delete", "transactions", "t_stale"), keys(pinned))
        self.assertNotIn(("delete", "transactions", "t_old_posted"), keys(pinned))


class MainTest(unittest.TestCase):
    def test_two_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            sync = fresh_sync()
            (tmp / "sync.json").write_text(json.dumps(sync))
            for coll, docs in stored(sync).items():
                (tmp / "existing" / coll).mkdir(parents=True)
                for doc_id, data in docs.items():
                    (tmp / "existing" / coll / f"{doc_id}.json").write_text(json.dumps(data))
            self.assertEqual(len(load_existing(tmp / "existing")["transactions"]), 7)
            args = ["--sync", str(tmp / "sync.json"), "--existing", str(tmp / "existing"), "--out", str(tmp / "b")]
            self.assertEqual(main(args), 0)
            self.assertEqual(list((tmp / "b").glob("*.json")), [])
            (tmp / "v.json").write_text(json.dumps({"balances/2025-10-03": 3}))
            self.assertEqual(main(args + ["--versions", str(tmp / "v.json")]), 2)  # meta version missing
            (tmp / "v.json").write_text(json.dumps({"balances/2025-10-03": 3, "meta/sync": 8}))
            self.assertEqual(main(args + ["--versions", str(tmp / "v.json")]), 0)
            batch = json.loads((tmp / "b" / "pinned0.json").read_text())
            self.assertEqual({e["doc_id"]: e["if_version"] for e in batch}, {"2025-10-03": 3, "sync": 8})
            self.assertTrue(Path(batch[0]["file_path"]).exists())


if __name__ == "__main__":
    unittest.main()
