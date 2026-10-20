#!/usr/bin/env python3
"""instagram_auth.py - sign in to Instagram once, so the reels, ig-publish and engage steps can work.

    python3 scripts/instagram_auth.py            # opens your browser, you sign in, paste the address back
    python3 scripts/instagram_auth.py --check    # which account the saved sign-in is for, days left
    python3 scripts/instagram_auth.py --refresh  # renew the 60-day token now (it also renews itself)

Uses "Instagram API with Instagram Login": an Instagram Business or Creator account, no Facebook
Page needed. Needs INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET and INSTAGRAM_REDIRECT_URI in .env
(docs/SETUP-INSTAGRAM.md walks through it). Writes secrets/instagram_token.json.

You sign in on instagram.com in your own browser; this script never sees your password. Meta only
accepts https redirect addresses, so after you allow access the browser lands on an address that
does not load. That is expected: copy the whole address from the address bar and paste it into
this terminal. The code in it works once, for a few minutes.

The long-lived token lasts 60 days. token() renews it whenever it is older than a day and has under
15 days left, so as long as anything runs at least once every ~45 days you never sign in again.
"""
import json, os, secrets, sys, time, urllib.error, urllib.parse, urllib.request, webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imagegen import env  # noqa: E402

CONFIG = os.environ.get("YTA_CONFIG") or os.path.join(ROOT, "config", "channel.json")
TOKEN = os.path.join(ROOT, "secrets", "instagram_token.json")
SCOPES = [
    "instagram_business_basic",            # profile, media list, insights
    "instagram_business_content_publish",  # post Reels
    "instagram_business_manage_comments",  # read, reply to and hide comments on your posts
    "instagram_business_manage_messages",  # read and answer DMs (inside Meta's 24-hour window)
]
DAY = 86400
RENEW_UNDER = 15 * DAY
TRANSIENT = {1, 2, 4, 17, 341}  # Meta's "try again" error codes


class IGError(Exception):
    def __init__(self, status, err):
        self.status, self.code = status, err.get("code")
        self.subcode, self.message = err.get("error_subcode"), err.get("error_user_msg") or err.get("message", "")
        super().__init__(f"Instagram API {status} (code {self.code}): {self.message}")


def api_version():
    try:
        return json.load(open(CONFIG)).get("instagram", {}).get("api_version") or "v23.0"
    except (FileNotFoundError, json.JSONDecodeError):
        return "v23.0"


def graph_url(path):
    return f"https://graph.instagram.com/{api_version()}/{path.lstrip('/')}"


def http(method, url, params=None, data=None, headers=None, body=None, timeout=120):
    """One request. JSON back, IGError on an API error. Never puts the token in an error message."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded", **(headers or {})}
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            err = json.loads(raw).get("error") or {}
        except (json.JSONDecodeError, AttributeError):
            err = {}
        if not isinstance(err, dict):
            err = {"message": str(err)}
        err.setdefault("message", raw.decode(errors="replace")[:300])
        raise IGError(e.code, err) from None
    return json.loads(raw) if raw.strip() else {}


def call(method, path, params=None, data=None, tries=4):
    """A Graph API call as the signed-in account, retried on Meta's transient errors."""
    tok, _ = token()
    for attempt in range(tries):
        try:
            if method == "GET":
                return http("GET", graph_url(path), params={**(params or {}), "access_token": tok})
            return http("POST", graph_url(path), params=params, data={**(data or {}), "access_token": tok})
        except IGError as e:
            if attempt + 1 < tries and (e.status >= 500 or e.code in TRANSIENT):
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt + 1 < tries:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def load():
    try:
        return json.load(open(TOKEN))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save(tok):
    os.makedirs(os.path.dirname(TOKEN), exist_ok=True)
    fd = os.open(TOKEN, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(tok, f, indent=2)


def refresh(tok):
    r = http("GET", "https://graph.instagram.com/refresh_access_token",
             params={"grant_type": "ig_refresh_token", "access_token": tok["access_token"]})
    tok.update(access_token=r["access_token"], obtained_at=int(time.time()),
               expires_at=int(time.time()) + int(r.get("expires_in", 60 * DAY)))
    save(tok)
    return tok


def token():
    """(access_token, ig_user_id) for the saved account, renewed when it is getting old."""
    tok = load()
    if not tok:
        sys.exit("Instagram not signed in: run python3 scripts/instagram_auth.py (docs/SETUP-INSTAGRAM.md)")
    t = time.time()
    if tok.get("expires_at", 0) <= t:
        sys.exit("Instagram sign-in expired (60 days unused): run python3 scripts/instagram_auth.py again")
    if tok["expires_at"] - t < RENEW_UNDER and t - tok.get("obtained_at", 0) > DAY:
        try:
            tok = refresh(tok)
        except IGError as e:
            print(f"warning: could not renew the Instagram token yet: {e}", file=sys.stderr)
    return tok["access_token"], tok["user_id"]


def app_settings():
    need = {k: env(k) for k in ("INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET", "INSTAGRAM_REDIRECT_URI")}
    missing = [k for k, v in need.items() if not v]
    if missing:
        sys.exit(f"missing in .env: {', '.join(missing)}. Step by step: docs/SETUP-INSTAGRAM.md")
    if not need["INSTAGRAM_REDIRECT_URI"].startswith("https://"):
        sys.exit("INSTAGRAM_REDIRECT_URI must start with https:// - Meta rejects anything else")
    return need["INSTAGRAM_APP_ID"], need["INSTAGRAM_APP_SECRET"], need["INSTAGRAM_REDIRECT_URI"]


def sign_in():
    app_id, app_secret, redirect = app_settings()
    state = secrets.token_urlsafe(16)
    url = "https://www.instagram.com/oauth/authorize?" + urllib.parse.urlencode({
        "client_id": app_id, "redirect_uri": redirect, "response_type": "code",
        "scope": ",".join(SCOPES), "state": state, "enable_fb_login": "0", "force_reauth": "true"})
    print("\nOpening Instagram in your browser. Sign in with the account you post from and allow access.")
    print(f"If the browser does not open, paste this into it:\n\n  {url}\n")
    webbrowser.open(url)
    print("After allowing, the browser goes to an address that does not load - that is fine.")
    landed = input("Paste that whole address here and press Enter:\n> ").strip()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(landed).query)
    if q.get("error"):
        sys.exit(f"Instagram said: {q.get('error_description', q['error'])[0]}")
    if q.get("state", [""])[0] != state:
        sys.exit("that address is not from this sign-in (state does not match). Run the script again.")
    code = q.get("code", [""])[0].split("#")[0]
    if not code:
        sys.exit("no code in that address - copy it from the address bar after you click Allow")

    short = http("POST", "https://api.instagram.com/oauth/access_token", data={
        "client_id": app_id, "client_secret": app_secret, "grant_type": "authorization_code",
        "redirect_uri": redirect, "code": code})
    if "data" in short:  # older response shape
        short = short["data"][0]
    long = http("GET", "https://graph.instagram.com/access_token", params={
        "grant_type": "ig_exchange_token", "client_secret": app_secret, "access_token": short["access_token"]})
    now = int(time.time())
    me = http("GET", graph_url("me"), params={"fields": "user_id,username,account_type",
                                               "access_token": long["access_token"]})
    save({"access_token": long["access_token"], "user_id": str(me.get("user_id") or short["user_id"]),
          "username": me.get("username"), "account_type": me.get("account_type"),
          "obtained_at": now, "expires_at": now + int(long.get("expires_in", 60 * DAY))})
    print(f"\nsaved {TOKEN} for @{me.get('username')} ({me.get('account_type')}).")
    print("Check it any time with: python3 scripts/instagram_auth.py --check")


def check():
    me = call("GET", "me", {"fields": "user_id,username,account_type,media_count,followers_count"})
    days = (load()["expires_at"] - time.time()) / DAY
    print(f"signed in as: @{me.get('username')} ({me.get('account_type')}), "
          f"{me.get('followers_count', '?')} followers, {me.get('media_count', '?')} posts")
    print(f"token renews itself; {days:.0f} days left on the current one")
    if me.get("account_type") not in ("BUSINESS", "MEDIA_CREATOR", "CREATOR"):
        print("warning: publishing needs a Business or Creator account (Instagram -> Settings -> Account type)")


def main():
    if "--check" in sys.argv:
        check()
    elif "--refresh" in sys.argv:
        tok = load() or sys.exit("not signed in yet")
        refresh(tok)
        print(f"renewed; {(load()['expires_at'] - time.time()) / DAY:.0f} days left")
    else:
        sign_in()


if __name__ == "__main__":
    try:
        main()
    except IGError as e:
        sys.exit(str(e))
