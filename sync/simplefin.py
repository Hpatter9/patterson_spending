"""Minimal SimpleFIN Bridge client (https://www.simplefin.org/protocol.html).

The access URL looks like https://USER:PASS@bridge.simplefin.org/simplefin.
It is read-only and must only ever come from the environment, never from git.
"""
import base64
import json
import time
import urllib.parse
import urllib.request

# SimpleFIN sits behind Cloudflare, which rejects urllib's default User-Agent with a 403.
USER_AGENT = "patterson-spending/1.0 (+https://github.com/Hpatter9/patterson_spending)"


def _split_credentials(access_url):
    parts = urllib.parse.urlsplit(access_url)
    if not parts.username:
        raise ValueError("SimpleFIN access URL is missing its credentials")
    netloc = parts.hostname + (f":{parts.port}" if parts.port else "")
    base = urllib.parse.urlunsplit((parts.scheme, netloc, parts.path.rstrip("/"), "", ""))
    token = f"{urllib.parse.unquote(parts.username)}:{urllib.parse.unquote(parts.password or '')}"
    return base, "Basic " + base64.b64encode(token.encode()).decode()


def fetch_accounts(access_url, days=45, timeout=60):
    """Return the raw /accounts response for the last `days` days, pending included."""
    base, auth = _split_credentials(access_url)
    query = urllib.parse.urlencode({"start-date": int(time.time()) - days * 86400, "pending": 1})
    req = urllib.request.Request(f"{base}/accounts?{query}", headers={"Authorization": auth, "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def claim_setup_token(setup_token, timeout=60):
    """Exchange a one-time SimpleFIN setup token for a long-lived access URL."""
    claim_url = base64.b64decode(setup_token.strip()).decode()
    req = urllib.request.Request(claim_url, method="POST", data=b"", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode().strip()
