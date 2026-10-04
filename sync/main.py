"""Pull from SimpleFIN and write out/sync.json for the daily routine to load into the dashboard.

Usage:
  SIMPLEFIN_ACCESS_URL=... python -m sync.main [--days 45] [--overrides overrides.json]
  python -m sync.main --fixture tests/fixtures/simplefin_sample.json   # offline, fake data
  python -m sync.main --claim <setup-token>                             # one-time setup
"""
import argparse
import json
import os
import sys
from pathlib import Path

from .categorize import DEFAULT_RULES, load_rules
from .normalize import normalize
from .simplefin import claim_setup_token, fetch_accounts


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--days", type=int, default=44, help="how many days of transactions to pull")
    p.add_argument("--fixture", help="read a saved SimpleFIN response instead of calling the API")
    p.add_argument("--rules", default=str(DEFAULT_RULES))
    p.add_argument("--overrides", help="JSON file of merchant -> category rules saved from the dashboard")
    p.add_argument("--out", default="out/sync.json")
    p.add_argument("--claim", metavar="SETUP_TOKEN", help="exchange a SimpleFIN setup token for an access URL")
    args = p.parse_args(argv)

    if args.claim:
        print(claim_setup_token(args.claim))
        print("Save this as the SIMPLEFIN_ACCESS_URL environment secret. Do not commit it.", file=sys.stderr)
        return 0

    if args.fixture:
        raw = json.loads(Path(args.fixture).read_text())
    else:
        access_url = os.environ.get("SIMPLEFIN_ACCESS_URL")
        if not access_url:
            print("SIMPLEFIN_ACCESS_URL is not set", file=sys.stderr)
            return 2
        # SimpleFIN serves at most 90 days and warns if asked for exactly 90 (clock skew).
        raw = fetch_accounts(access_url, days=min(args.days, 89))

    overrides = json.loads(Path(args.overrides).read_text()) if args.overrides else None
    result = normalize(raw, load_rules(args.rules, overrides))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    uncategorized = sum(t["category"] == "Uncategorized" for t in result["transactions"])
    print(f"{len(result['accounts'])} accounts, {len(result['transactions'])} transactions "
          f"({uncategorized} uncategorized), {len(result['errors'])} errors -> {out}")
    for err in result["errors"]:
        print(f"SimpleFIN: {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
