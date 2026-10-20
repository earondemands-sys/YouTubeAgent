# Instagram setup (one time, about 15 minutes)

You do these steps yourself: they need your Instagram and Facebook logins. The agents never see
your password or your token.

This uses **Instagram API with Instagram Login**: an Instagram Business or Creator account, no
Facebook Page needed.

## 1. Make the Instagram account professional

Instagram app -> your profile -> menu -> **Settings and activity -> Account type and tools ->
Switch to professional account**. Pick **Creator** (or Business). It stays free and public as before.

## 2. Create a Meta app

1. Open https://developers.facebook.com/apps and sign in (any Facebook account works; it does not
   have to be linked to the Instagram one).
2. **Create app**. Name it `EarOnDemands Agent`. When asked for a use case, pick the one about
   **Instagram** ("Manage messaging & content on Instagram"). Finish creating it.

## 3. Instagram login settings

In the app's dashboard: **Instagram -> API setup with Instagram login**.

1. Note the **Instagram app ID** and **Instagram app secret** shown there. These are not the Meta
   App ID at the top of the page.
2. Under **Set up Instagram business login** -> **Business login settings** -> **OAuth redirect
   URIs**, add exactly:

```
https://localhost:8765/instagram/callback
```

   Save. It must match `.env` character for character.

## 4. Add yourself as a tester

The app stays in **Development** mode. That is fine for your own account and means no App Review.

1. **App roles -> Roles -> Add people -> Instagram Tester** -> your Instagram username.
2. Accept the invite on Instagram: https://www.instagram.com/accounts/manage_access/ -> **Tester
   invites** -> **Accept**.

## 5. Keys, then sign in once

Open `~/Desktop/YouTubeAgent/.env` and fill in:

```
INSTAGRAM_APP_ID=<Instagram app ID from step 3>
INSTAGRAM_APP_SECRET=<Instagram app secret from step 3>
INSTAGRAM_REDIRECT_URI=https://localhost:8765/instagram/callback
```

Then in the terminal:

```bash
cd ~/Desktop/YouTubeAgent && python3 scripts/instagram_auth.py
```

Your browser opens Instagram. Sign in and click **Allow**. The browser then goes to a
`https://localhost:8765/...` address that **does not load. That is expected.** Copy the whole
address from the address bar, paste it into the terminal and press Enter.

Check it:

```bash
cd ~/Desktop/YouTubeAgent && python3 scripts/instagram_auth.py --check
```

It should print `signed in as: @<your handle> (MEDIA_CREATOR)` or `(BUSINESS)`.

## 6. DMs (for auto-replies to messages)

1. **Let the API see your messages.** Instagram app -> Settings and activity -> **Messages and
   story replies -> Message controls -> Connected tools -> Allow access to messages: ON**.
2. **Testing:** in Development mode the bot can only DM accounts that have a role on the app.
   Add a second Instagram account (a friend's or a spare) as an Instagram Tester (step 4), message
   your business account from it, and say "answer my DMs" to try it.
3. **Real customers need Meta's approval** of the `instagram_business_manage_messages` permission
   (App Review, one time):
   - App dashboard -> **App settings -> Basic**: add a **Privacy Policy URL** (a simple page on your
     site saying what the app reads and that nothing is shared) and an app icon.
   - **App Review -> Permissions and features** -> `instagram_business_manage_messages` ->
     **Request advanced access**. Explain it honestly: "Replies to DMs sent to my own business
     account, in my voice, within 24 hours." Attach a short screen recording of the bot answering
     a tester's DM.
   - Meta may ask for **Business verification** first. Approval usually takes a few days to a
     couple of weeks. Then switch the app to **Live**.
   Comments and Reels keep working the whole time. Only DMs to non-testers wait for this.
4. **What the bot may say:** fill in [`config/business.md`](../config/business.md) - offers, prices,
   links, and what must always come to you. Until it is filled, every price or offer question is
   flagged to you instead of answered.

## Done when

- `python3 scripts/doctor.py` shows INSTAGRAM ready
- `instagram_auth.py --check` prints your account

## Good to know

- **The sign-in renews itself.** The token lasts 60 days and is renewed whenever it is past a day
  old with under 15 days left. You only sign in again if nothing ran for about two months.
- **No private posts.** Instagram's API publishes Reels publicly at once. The Director always asks
  when to post, and later posts wait in a local queue (`instagram.py flush --all` posts them).
- **Limits.** About 100 API posts per 24 hours. `python3 scripts/instagram.py limit` shows yours.
- **Trending sounds can't be added by the API.** The Reels keep their own audio. To use a trending
  sound, add it in the Instagram app after posting, or post that one Reel by hand.
- **Pinning comments** isn't available in the API. The engage agent tells you which one to pin.
- **The 24-hour rule for DMs.** An app can only answer within 24 hours of the person's last message.
  After that the bot leaves it; you answer in the app. Run "answer my DMs" at least every few hours.
- **Already signed in before DMs were added?** Run `python3 scripts/instagram_auth.py` once more so
  the token includes the messages permission.

## Troubleshooting

| You see | Fix |
|---|---|
| `Invalid redirect_uri` | The address in step 3 and `INSTAGRAM_REDIRECT_URI` differ, often a trailing `/` |
| `Insufficient developer role` | The tester invite in step 4 is not accepted yet |
| Publishing fails with an account type error | Step 1: the account must be Creator or Business |
| `state does not match` | You pasted an address from an older attempt; run the script again |
| `Instagram sign-in expired` | Run `python3 scripts/instagram_auth.py` again |
| DM inbox stays empty though you have messages | Step 6.1 (Connected tools) is off, or the sender has no role on the app yet (step 6.2/6.3) |
| `(#10) ... outside of allowed window` | More than 24 hours since their message - answer it in the app |
