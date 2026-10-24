# The Instagram connect server (for the project owner)

This is what lets every creator who uses YouTubeAgent connect Instagram with one click. You set it
up **once**. Creators never see any of this - they run `python3 scripts/instagram_auth.py` and
click Allow.

**What it is:** `broker/src/worker.js`, a Cloudflare Worker (free plan is plenty). It holds your
Meta app's secret, sends creators to Instagram's Allow page, trades the code for a 60-day token and
hands it to the creator's own terminal - only that terminal can collect it, once, within five
minutes, then it is deleted. It stores nothing else. It also serves the pages Meta requires:
`/privacy`, `/deauthorize`, `/data-deletion`.

**What you need:** the Meta app (you have one already if `INSTAGRAM_APP_ID` is in `.env`), a free
Cloudflare account, and for real users, Meta's App Review.

You do the sign-ins and paste the secret yourself; never paste the secret into a chat.

## 1. Deploy the worker (one command)

```bash
cd ~/Desktop/YouTubeAgent && python3 scripts/setup_instagram_server.py
```

It signs in to Cloudflare (your browser opens if this Mac is not signed in yet), creates the KV
store, registers your free `workers.dev` address, fills `broker/wrangler.toml`, deploys, moves the
app secret from `.env` into Cloudflare's encrypted secrets (never printed), sets
`instagram.auth_broker` in `config/channel.json`, and checks the server is live. It prints the four
addresses for step 2. Safe to rerun; `--contact you@example.com` puts your email on the privacy page.

## 2. Point the Meta app at it

Meta dashboard -> your app:

1. **Instagram -> API setup with Instagram login -> Business login settings**:
   - **OAuth redirect URIs**: add `https://<your worker>/callback`
   - **Deauthorize callback URL**: `https://<your worker>/deauthorize`
   - **Data deletion request URL**: `https://<your worker>/data-deletion`
   Save.
2. **App settings -> Basic**: **Privacy Policy URL** `https://<your worker>/privacy`, an **app
   icon** (1024x1024), a **category**, and your contact email. Save.

## 3. Point the project at it

The setup script already set `instagram.auth_broker` in [`config/channel.json`](../config/channel.json).
Commit it - that is how everyone who clones the repo gets one-click connect.

## 4. Try it (Development mode)

While the app is in Development mode, only accounts with a role on it can connect.

1. **App roles -> Roles -> Add people -> Instagram Tester** -> your Instagram username; accept at
   https://www.instagram.com/accounts/manage_access/ -> **Tester invites**.
2. Clear your own keys so the script uses the server: empty `INSTAGRAM_APP_ID` and
   `INSTAGRAM_APP_SECRET` in `.env` (the worker has them now).
3. `python3 scripts/instagram_auth.py` -> Allow -> the terminal prints `connected @...`.
4. `python3 scripts/instagram_auth.py --check`.

To let a few friends test before review, add them as Instagram Testers the same way.

## 5. App Review - so any creator can connect

Meta has to approve the permissions before people without a role on the app can use it. Meta
dashboard -> **App Review -> Permissions and features** -> **Request advanced access** for each:

| Permission | What to say it is for | What to show in the screen recording |
|---|---|---|
| `instagram_business_basic` | Shows the creator which account is connected and reads their own posts so the tool knows what to answer | Running `instagram_auth.py`, the Allow page, `--check` printing the account |
| `instagram_business_content_publish` | Publishes Reels the creator made and approved, at the time they choose | The publish gate in Claude asking "when should the Reels go up?", then the Reel appearing on the profile |
| `instagram_business_manage_comments` | Reads comments on the creator's own posts, posts the replies the creator approved, hides spam | "reply to my comments": the drafted replies, the approval, the reply visible under the post |
| `instagram_business_manage_messages` | Answers DMs sent to the creator's business account within 24 hours, from the creator's own business notes; flags anything about money to the creator | A tester account sending a DM, the draft, approval, the reply arriving in the tester's inbox |

Tips that get approvals through:

- **Be specific and honest.** "A tool creators run on their own computer to post their own Reels
  and answer comments and DMs on their own account, with their approval."
- **One recording per permission**, 1-3 minutes, showing the full path from login to the result
  in the Instagram app. Add captions or narration in English.
- **Test credentials**: Meta reviewers need to try it. Add a reviewer test account as described in
  the review form, or explain that it is a command-line tool and the recording shows the full flow.
- **Business verification** (Meta asks for it with Advanced Access): **Settings -> Business
  verification** in Meta Business Manager - legal business name, address, a document. Because the
  app serves other people's accounts, Meta may also ask for **Access verification** (tech provider);
  answer that you provide a tool to creators.
- Reviews usually take a few days to two weeks. A rejection says what is missing - fix that one
  thing and resubmit.

When the permissions are approved, switch the app from **Development** to **Live** (top of the
dashboard). From then on, any creator can connect with one click.

## Running it

- **Logs:** `cd broker && npx wrangler@4 tail` shows requests live (tokens are never logged).
- **Rotate the secret** (if it ever leaks): Meta dashboard -> reset the Instagram app secret, then
  `npx wrangler@4 secret put INSTAGRAM_APP_SECRET` again. Creators' saved sign-ins keep working.
- **Tests:** `node --test broker/test/` (server alone) and `python3 scripts/test_instagram.py`
  (the client signing in against the real server code on localhost).
- **Cost:** a sign-in is three requests. The free plan's 100,000 requests a day covers it many
  times over.
