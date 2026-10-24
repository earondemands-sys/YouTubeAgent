#!/usr/bin/env python3
"""setup_instagram_server.py - deploy the Instagram connect server in one go (project owner, once).

    python3 scripts/setup_instagram_server.py                       # everything below, safe to rerun
    python3 scripts/setup_instagram_server.py --subdomain myname    # pick the workers.dev name
    python3 scripts/setup_instagram_server.py --contact you@x.com   # email shown on /privacy

What it does, with only one thing from you - signing in to Cloudflare in the browser if this Mac is
not signed in yet:

  1. Cloudflare sign-in (`wrangler login`, opens the browser, only when needed)
  2. the KV store the server keeps logins in for a few minutes (created once)
  3. your free workers.dev address (registered once, named after the channel)
  4. broker/wrangler.toml filled in with the Instagram app ID from .env
  5. deploy, then the app secret straight from .env into Cloudflare's encrypted secrets
     (piped, never printed, never written anywhere else)
  6. instagram.auth_broker in config/channel.json, so instagram_auth.py uses the server
  7. a live check of the server and its privacy page

What it cannot do: Meta has no API for its app dashboard, so at the end it prints the three
addresses to add there (docs/BROKER-DEPLOY.md step 2). The Director can fill those in the browser.
"""
import argparse, json, os, re, secrets, shutil, subprocess, sys, time, tomllib, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imagegen import env  # noqa: E402

BROKER = os.path.join(ROOT, "broker")
TOML = os.path.join(BROKER, "wrangler.toml")
CONFIG = os.environ.get("YTA_CONFIG") or os.path.join(ROOT, "config", "channel.json")
WRANGLER_AUTH = os.path.expanduser("~/Library/Preferences/.wrangler/config/default.toml")
KV_TITLE = "yta-instagram-connect-sessions"
CF = "https://api.cloudflare.com/client/v4"


def say(msg):
    print(f"\n==> {msg}", flush=True)


def wrangler(*args, input=None, interactive=False, check=True):
    cmd = ["npx", "--yes", "wrangler@4", *args]
    if interactive:
        return subprocess.run(cmd, cwd=BROKER).returncode
    r = subprocess.run(cmd, cwd=BROKER, input=input, capture_output=True, text=True)
    out = r.stdout + r.stderr
    if check and r.returncode != 0:
        sys.exit(f"wrangler {' '.join(args)} failed:\n{out[-1500:]}")
    return out


def account_id():
    out = wrangler("whoami", check=False)
    if "not logged in" in out.lower() or "not authenticated" in out.lower():
        say("Signing in to Cloudflare - your browser opens; sign in and click Allow")
        if wrangler("login", interactive=True) != 0:
            sys.exit("Cloudflare sign-in did not finish")
        out = wrangler("whoami")
    ids = sorted(set(re.findall(r"\b[0-9a-f]{32}\b", out)))
    if not ids:
        sys.exit(f"could not read the Cloudflare account from `wrangler whoami`:\n{out[-800:]}")
    if len(ids) > 1 and not os.environ.get("CLOUDFLARE_ACCOUNT_ID"):
        sys.exit(f"this login has {len(ids)} Cloudflare accounts; rerun with CLOUDFLARE_ACCOUNT_ID=<one of {', '.join(ids)}>")
    return os.environ.get("CLOUDFLARE_ACCOUNT_ID") or ids[0]


def cf(method, path, body=None):
    """Cloudflare API as the wrangler login (the token is read from wrangler's own file, never shown)."""
    tok = tomllib.load(open(WRANGLER_AUTH, "rb"))["oauth_token"]
    req = urllib.request.Request(CF + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except json.JSONDecodeError:
            return {"success": False, "errors": [{"message": f"HTTP {e.code}"}]}


def ensure_subdomain(acc, wanted):
    r = cf("GET", f"/accounts/{acc}/workers/subdomain")
    have = (r.get("result") or {}).get("subdomain") if r.get("success") else None
    if have:
        print(f"    workers.dev address: {have}.workers.dev (already registered)")
        return have
    for name in wanted:
        r = cf("PUT", f"/accounts/{acc}/workers/subdomain", {"subdomain": name})
        if r.get("success"):
            print(f"    registered {name}.workers.dev")
            return name
        print(f"    {name}.workers.dev not available ({'; '.join(e.get('message', '') for e in r.get('errors', []))})")
    sys.exit("no workers.dev name worked; rerun with --subdomain <another name>")


def ensure_kv(text):
    m = re.search(r'(?m)^id = "([0-9a-f]{32})"', text)
    if m:
        print(f"    KV store: {m.group(1)} (already set)")
        return text
    out = wrangler("kv", "namespace", "list")
    found = [n["id"] for n in json.loads(out[out.index("["):]) if n.get("title") == KV_TITLE]
    if found:
        kv = found[0]
    else:
        out = wrangler("kv", "namespace", "create", KV_TITLE)
        kv = re.search(r'"id":\s*"([0-9a-f]{32})"', out).group(1)
    print(f"    KV store: {kv}")
    return re.sub(r'(?m)^id = ".*"', f'id = "{kv}"', text, count=1)


def set_var(text, name, value):
    return re.sub(rf'(?m)^{name} = "[^"]*"', f'{name} = "{value}"', text, count=1)


def slug(s):
    return re.sub(r"[^a-z0-9-]+", "-", (s or "").lower()).strip("-")[:40]


def live(url, tries=36):
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                return r.status, r.read().decode(errors="replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(5)
    return None, str(last)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--subdomain", help="workers.dev name to register (default: from the channel name)")
    p.add_argument("--contact", help="email shown on the privacy page (Meta's review wants one)")
    a = p.parse_args()

    if not shutil.which("npx"):
        sys.exit("needs Node (npx): brew install node")
    app_id, secret = env("INSTAGRAM_APP_ID"), env("INSTAGRAM_APP_SECRET")
    if not (app_id and re.fullmatch(r"\d{8,20}", app_id) and secret):
        sys.exit("INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET must be in .env (Meta dashboard -> Instagram -> "
                 "API setup with Instagram login)")
    cfg = json.load(open(CONFIG))

    say("1/7 Cloudflare account")
    acc = account_id()
    print(f"    account {acc}")
    os.environ["CLOUDFLARE_ACCOUNT_ID"] = acc

    say("2/7 KV store")
    text = ensure_kv(open(TOML).read())

    say("3/7 workers.dev address")
    base = slug(a.subdomain or cfg.get("channel", {}).get("handle", "").lstrip("@") or cfg.get("channel", {}).get("name")) or "yta"
    sub = ensure_subdomain(acc, [base] if a.subdomain else [base, f"{base}-agent", f"{base}-{secrets.token_hex(2)}"])

    say("4/7 wrangler.toml")
    text = set_var(text, "INSTAGRAM_APP_ID", app_id)
    if a.contact:
        text = set_var(text, "CONTACT_EMAIL", a.contact)
    open(TOML, "w").write(text)
    print("    app ID and KV store written")

    say("5/7 deploy + secret")
    out = wrangler("deploy")
    m = re.search(r"https://[\w.-]+\.workers\.dev", out)
    url = m.group(0) if m else f"https://yta-instagram-connect.{sub}.workers.dev"
    wrangler("secret", "put", "INSTAGRAM_APP_SECRET", input=secret)
    print(f"    live at {url}; app secret stored encrypted at Cloudflare")

    say("6/7 config/channel.json")
    cfg.setdefault("instagram", {})["auth_broker"] = url
    with open(CONFIG, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"    instagram.auth_broker = {url}")

    say("7/7 live check (a new workers.dev address can take a minute)")
    for path, must in (("/", "connects an Instagram"), ("/privacy", "Privacy policy")):
        status, body = live(url + path)
        ok = status == 200 and must in body
        print(f"    {'OK  ' if ok else 'FAIL'} {url}{path} ({status})")
        if not ok:
            sys.exit(f"the server is deployed but {path} is not answering yet - rerun this script in a minute")

    print(json.dumps({"server": url, "meta_dashboard": {
        "OAuth redirect URI": f"{url}/callback",
        "Deauthorize callback URL": f"{url}/deauthorize",
        "Data deletion request URL": f"{url}/data-deletion",
        "Privacy Policy URL": f"{url}/privacy"}}, indent=2))
    print("\nLast step - Meta's dashboard has no API: add those four addresses to the app "
          "(docs/BROKER-DEPLOY.md step 2). Then: python3 scripts/instagram_auth.py")


if __name__ == "__main__":
    main()
