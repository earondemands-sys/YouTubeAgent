# Instagram setup (one time, about 2 minutes)

You sign in yourself, on instagram.com in your own browser. The agents never see your password.

## 1. Make the Instagram account professional

Instagram app -> your profile -> menu -> **Settings and activity -> Account type and tools ->
Switch to professional account**. Pick **Creator** (or Business). It stays free and public as before.

## 2. Connect

```bash
cd ~/Desktop/YouTubeAgent && python3 scripts/instagram_auth.py
```

Your browser opens Instagram. Sign in with the account you post from and click **Allow**. The
terminal finishes by itself and prints `connected @<your handle>`. That is all: the sign-in renews
itself, so you only do this again if nothing ran for about two months.

Check it any time:

```bash
cd ~/Desktop/YouTubeAgent && python3 scripts/instagram_auth.py --check
```

## 3. For DM replies

1. **Let the API see your messages.** Instagram app -> Settings and activity -> **Messages and
   story replies -> Message controls -> Connected tools -> Allow access to messages: ON**.
2. **What the bot may say:** fill in [`config/business.md`](../config/business.md) - offers, prices,
   links, and what must always come to you. Until it is filled, every price or offer question is
   flagged to you instead of answered.

## Done when

- `python3 scripts/doctor.py` shows INSTAGRAM ready
- `instagram_auth.py --check` prints your account

## Good to know

- **How the connection works.** `instagram_auth.py` uses the project's connect server
  (`instagram.auth_broker` in `config/channel.json`). It holds the project's Meta app secret, sends
  you to Instagram's Allow page, and hands the sign-in straight to your terminal - only your
  terminal can collect it, and the server deletes it right after. After that your computer talks
  to Instagram directly. The privacy policy is at `<server>/privacy`.
- **No private posts.** Instagram's API publishes Reels publicly at once. The Director always asks
  when to post, and later posts wait in a local queue (`instagram.py flush --all` posts them).
- **Limits.** About 100 API posts per 24 hours. `python3 scripts/instagram.py limit` shows yours.
- **Trending sounds can't be added by the API.** The Reels keep their own audio. To use a trending
  sound, add it in the Instagram app after posting, or post that one Reel by hand.
- **Pinning comments** isn't available in the API. The engage agent tells you which one to pin.
- **The 24-hour rule for DMs.** An app can only answer within 24 hours of the person's last message.
  After that the bot leaves it; you answer in the app. Run "answer my DMs" at least every few hours.
- **Remove access** any time: Instagram -> Settings -> Website permissions -> Apps and websites.

## Troubleshooting

| You see | Fix |
|---|---|
| `no way to connect yet` | `instagram.auth_broker` is empty: the project owner has not set up the connect server yet (docs/BROKER-DEPLOY.md), or use your own Meta app below |
| The Allow page says the app is not available / `Insufficient developer role` | The project's Meta app is still in review; until it is Live, only accounts added as testers can connect. Ask the owner to add you, or use your own Meta app |
| Posting fails with an account type error | Step 1: the account must be Creator or Business |
| `no Allow within 10 minutes` | Run `python3 scripts/instagram_auth.py` again |
| `Instagram sign-in expired` | Run `python3 scripts/instagram_auth.py` again |
| DM inbox stays empty though you have messages | Step 3.1 (Connected tools) is off |
| `(#10) ... outside of allowed window` | More than 24 hours since their message - answer it in the app |

---

## Your own Meta app (advanced, optional)

Use this instead of the connect server if you want your own app: for example while the project's
app is still in Meta's review, or to keep everything under your own developer account. About 15
minutes.

1. **Create the app.** https://developers.facebook.com/apps -> **Create app**, any name. Use case:
   the one about **Instagram** ("Manage messaging & content on Instagram").
2. **Instagram login settings.** Dashboard -> **Instagram -> API setup with Instagram login**. Note
   the **Instagram app ID** and **Instagram app secret** (not the Meta App ID at the top). Under
   **Business login settings -> OAuth redirect URIs** add exactly
   `https://localhost:8765/instagram/callback` and save.
3. **Add yourself as a tester.** **App roles -> Roles -> Add people -> Instagram Tester** -> your
   username, then accept at https://www.instagram.com/accounts/manage_access/ -> **Tester invites**.
   The app stays in Development mode; no App Review is needed for your own account.
4. **Keys.** In `.env`: `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`,
   `INSTAGRAM_REDIRECT_URI=https://localhost:8765/instagram/callback`.
5. **Connect.** `python3 scripts/instagram_auth.py --local`. After **Allow** the browser lands on a
   `https://localhost:8765/...` address that **does not load - that is expected**. Copy the whole
   address from the address bar and paste it into the terminal.

In Development mode, DM replies only reach accounts that also have a role on your app. Answering
real customers needs Meta's approval of `instagram_business_manage_messages` - the same App Review
as in [BROKER-DEPLOY.md](BROKER-DEPLOY.md), step 5.

| You see | Fix |
|---|---|
| `Invalid redirect_uri` | The address in step 2 and `INSTAGRAM_REDIRECT_URI` differ, often a trailing `/` |
| `Insufficient developer role` | The tester invite in step 3 is not accepted yet |
| `state does not match` | You pasted an address from an older attempt; run the script again |
