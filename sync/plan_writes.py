"""Turn out/sync.json into ArtifactData batch files that are safe to re-run.

The dashboard database refuses a write to an existing document unless it names
the version it was read at. New documents need no version, so this splits writes:

  * new transactions          -> `set`, no version needed
  * changed existing docs     -> pinned: `update` / `delete` / `set` with if_version
                                 (accounts, posted pending charges, today's balance, meta/sync)

Pass 1 (no --versions): writes the unpinned batches and lists the docs that need a
version in pinned.json, next to the --out folder. Read those versions (ArtifactData list/get), save them as
{"collection/doc_id": version} and run pass 2 with --versions to get the pinned batch.

Usage:
  python -m sync.plan_writes --existing out/existing [--versions out/versions.json]

`--existing` is an ArtifactData `out_dir` export: <dir>/<collection>/<doc_id>.json.
"""
import argparse
import json
import sys
from pathlib import Path

from .categorize import UNCATEGORIZED

BATCH_SIZE = 50
TXN_SYNCED = ("accountId", "date", "amount", "payee", "description", "pending")
ACCOUNT_SYNCED = ("name", "institution", "last4", "type", "balance", "available", "currency", "balanceDate", "updatedAt")


def load_existing(root):
    existing = {}
    for coll in ("accounts", "transactions", "balances", "meta"):
        d = Path(root) / coll
        existing[coll] = {p.stem: json.loads(p.read_text()) for p in sorted(d.glob("*.json"))} if d.is_dir() else {}
    return existing


def plan(sync, existing):
    """Return (unpinned, pinned) lists of write dicts without file paths or versions."""
    unpinned, pinned = [], []

    for acct in sync["accounts"]:
        data = {k: acct.get(k) for k in ACCOUNT_SYNCED}
        old = existing["accounts"].get(acct["id"])
        if old is None:
            unpinned.append(dict(op="set", collection="accounts", doc_id=acct["id"], data=data))
        elif any(old.get(k) != v for k, v in data.items()):
            pinned.append(dict(op="update", collection="accounts", doc_id=acct["id"], data=data))

    fresh_ids = set()
    for txn in sync["transactions"]:
        fresh_ids.add(txn["id"])
        old = existing["transactions"].get(txn["id"])
        if old is None:
            data = {k: v for k, v in txn.items() if k != "id"}
            unpinned.append(dict(op="set", collection="transactions", doc_id=txn["id"], data=data))
            continue
        data = {k: txn.get(k) for k in TXN_SYNCED if old.get(k) != txn.get(k)}
        # A category chosen on the dashboard always wins; otherwise only fill in blanks.
        if not old.get("categoryLocked") and old.get("category") == UNCATEGORIZED and txn["category"] != UNCATEGORIZED:
            data["category"] = txn["category"]
        if data:
            pinned.append(dict(op="update", collection="transactions", doc_id=txn["id"], data=data))

    # Pending charges come back as posted ones with new ids, so drop the stale pending copies.
    window_start = min((t["date"] for t in sync["transactions"]), default=None)
    synced_accounts = {a["id"] for a in sync["accounts"]}
    for doc_id, old in existing["transactions"].items():
        if (old.get("pending") and doc_id not in fresh_ids and old.get("accountId") in synced_accounts
                and window_start and old.get("date", "") >= window_start):
            pinned.append(dict(op="delete", collection="transactions", doc_id=doc_id))

    snap = sync["snapshot"]
    snap_write = dict(op="set", collection="balances", doc_id=snap["id"], data={k: v for k, v in snap.items() if k != "id"})
    (pinned if snap["id"] in existing["balances"] else unpinned).append(snap_write)

    meta = dict(status="ok" if sync["accounts"] else "error", at=sync["syncedAt"], accounts=len(sync["accounts"]),
                transactions=len(sync["transactions"]), errors=sync["errors"])
    meta_write = dict(op="set", collection="meta", doc_id="sync", data=meta)
    if sync["errors"]:
        meta["message"] = "; ".join(map(str, sync["errors"]))[:500]
    (pinned if "sync" in existing["meta"] else unpinned).append(meta_write)
    return unpinned, pinned


def write_batches(writes, out_dir, prefix):
    """Write each doc body to its own file and group entries into batch files of 50."""
    out_dir = Path(out_dir)
    paths = []
    for n in range(0, len(writes), BATCH_SIZE):
        entries = []
        for w in writes[n:n + BATCH_SIZE]:
            entry = {k: v for k, v in w.items() if k != "data"}
            if "data" in w:
                doc = out_dir / "docs" / w["collection"] / f"{w['doc_id']}.json"
                doc.parent.mkdir(parents=True, exist_ok=True)
                doc.write_text(json.dumps(w["data"]))
                entry["file_path"] = str(doc)
            entries.append(entry)
        path = out_dir / f"{prefix}{n // BATCH_SIZE}.json"
        path.write_text(json.dumps(entries))
        paths.append(path)
    return paths


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sync", default="out/sync.json")
    p.add_argument("--existing", required=True, help="ArtifactData out_dir export of the dashboard database")
    p.add_argument("--versions", help='JSON {"collection/doc_id": version} for the pinned writes')
    p.add_argument("--out", default="out/batches")
    args = p.parse_args(argv)

    unpinned, pinned = plan(json.loads(Path(args.sync).read_text()), load_existing(args.existing))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.json"):
        old.unlink()

    if args.versions:
        versions = json.loads(Path(args.versions).read_text())
        missing = [f"{w['collection']}/{w['doc_id']}" for w in pinned if f"{w['collection']}/{w['doc_id']}" not in versions]
        if missing:
            print("Missing versions for: " + ", ".join(missing), file=sys.stderr)
            return 2
        for w in pinned:
            w["if_version"] = versions[f"{w['collection']}/{w['doc_id']}"]
        files = write_batches(pinned, out, "pinned")
        print(f"{len(pinned)} pinned writes -> {', '.join(map(str, files)) or 'none'}")
        return 0

    files = write_batches(unpinned, out, "new")
    pinned_list = out.parent / "pinned.json"
    pinned_list.write_text(json.dumps([f"{w['collection']}/{w['doc_id']}" for w in pinned], indent=1))
    print(f"{len(unpinned)} new writes -> {', '.join(map(str, files)) or 'none'}")
    print(f"{len(pinned)} writes need versions -> {pinned_list}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
