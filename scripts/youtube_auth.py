#!/usr/bin/env python3
"""youtube_auth.py - sign in to YouTube once, so the publish and analytics agents can work.

    .venv/bin/python scripts/youtube_auth.py           # opens your browser, you sign in
    .venv/bin/python scripts/youtube_auth.py --check   # says which channel the saved sign-in is for

Needs secrets/client_secret.json (an OAuth "Desktop app" client from Google Cloud Console -
docs/SETUP-YOUTUBE.md walks through it). Writes secrets/token.json. You sign in in your own
browser; this script never sees your password.
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS = os.path.join(ROOT, "secrets")
CLIENT = os.path.join(SECRETS, "client_secret.json")
TOKEN = os.path.join(SECRETS, "token.json")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",       # upload videos, set thumbnails
    "https://www.googleapis.com/auth/youtube.force-ssl",    # read comments on your videos
    "https://www.googleapis.com/auth/yt-analytics.readonly",  # retention curves
]


def credentials(interactive=False):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_file(TOKEN, SCOPES) if os.path.exists(TOKEN) else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save(creds)
    if creds and creds.valid:
        return creds
    if not interactive:
        sys.exit("not signed in: run .venv/bin/python scripts/youtube_auth.py")
    if not os.path.exists(CLIENT):
        sys.exit(f"missing {CLIENT}\nCreate an OAuth Desktop client in Google Cloud Console and save its JSON there.\n"
                 "Step by step: docs/SETUP-YOUTUBE.md")
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", open_browser=True)
    save(creds)
    return creds


def save(creds):
    os.makedirs(SECRETS, exist_ok=True)
    fd = os.open(TOKEN, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(creds.to_json())


def youtube(api="youtube", version="v3"):
    from googleapiclient.discovery import build
    return build(api, version, credentials=credentials(), cache_discovery=False)


def main():
    if "--check" in sys.argv:
        ch = youtube().channels().list(part="snippet,status", mine=True).execute().get("items", [])
        if not ch:
            sys.exit("signed in, but this Google account has no YouTube channel")
        c = ch[0]
        print(f"signed in as: {c['snippet']['title']} ({c['id']})")
        print(f"long uploads allowed: {c.get('status', {}).get('longUploadsStatus', 'unknown')}")
        return
    credentials(interactive=True)
    print(f"saved {TOKEN}. Check it with: .venv/bin/python scripts/youtube_auth.py --check")


if __name__ == "__main__":
    main()
