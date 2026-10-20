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

## Troubleshooting

| You see | Fix |
|---|---|
| `Invalid redirect_uri` | The address in step 3 and `INSTAGRAM_REDIRECT_URI` differ, often a trailing `/` |
| `Insufficient developer role` | The tester invite in step 4 is not accepted yet |
| Publishing fails with an account type error | Step 1: the account must be Creator or Business |
| `state does not match` | You pasted an address from an older attempt; run the script again |
| `Instagram sign-in expired` | Run `python3 scripts/instagram_auth.py` again |
