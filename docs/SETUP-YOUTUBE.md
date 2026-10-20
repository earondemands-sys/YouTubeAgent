# YouTube upload setup (one time, about 20 minutes)

You do these steps yourself: they need your Google login. The agents never see your password.

## 1. Create a Google Cloud project

1. Open https://console.cloud.google.com/ and sign in with the Google account that owns the channel.
2. Top bar -> project picker -> **New project**. Name it `EarOnDemands Agent`. Create, then select it.

## 2. Turn on the two APIs

**APIs & Services -> Library**, search and **Enable** each:

- **YouTube Data API v3** (uploads, thumbnails, comments)
- **YouTube Analytics API** (retention for the analytics agent)

## 3. OAuth consent screen

**APIs & Services -> OAuth consent screen** (also called **Google Auth Platform**):

1. App name `EarOnDemands Agent`, your email as support and developer contact. User type **External**.
2. **Audience -> Test users -> Add users**: your own Gmail.
3. Leave it in **Testing** for now.

Testing mode has one catch: Google expires the sign-in after **7 days**, so you would rerun step 5
weekly. To stop that, click **Publish app** under Audience. For an app only you use, Google shows
an "unverified app" warning when you sign in. Click **Advanced -> Go to EarOnDemands Agent**. It
is your own app.

## 4. Create the client file

**APIs & Services -> Credentials** (or **Clients**) -> **Create credentials -> OAuth client ID**:

- Application type: **Desktop app**, name `agent`.
- Download the JSON and save it as:

```
~/Desktop/YouTubeAgent/secrets/client_secret.json
```

## 5. Sign in once

```bash
cd ~/Desktop/YouTubeAgent && .venv/bin/python scripts/youtube_auth.py
```

Your browser opens. Pick the channel's account and allow access. Then check it:

```bash
cd ~/Desktop/YouTubeAgent && .venv/bin/python scripts/youtube_auth.py --check
```

It should print `signed in as: EarOnDemands`.

## 6. The audit (so uploads can go public)

YouTube locks every video uploaded from a new API project to **private** until the project passes
an audit. Uploads still work; you would flip each one to public in Studio yourself.

To lift the lock, submit the **YouTube API Services - Audit and Quota Extension Form**. Search for
that name or find it in the YouTube API docs under "Quota and compliance audits". Describe it
honestly: a personal tool that uploads your own channel's videos. Approval can take a few weeks.
The same form raises the 10,000 units/day quota (about 6 uploads a day) if you ever need more.

## 7. Verify the channel

https://www.youtube.com/verify. Phone verification is needed for **custom thumbnails** and videos
**longer than 15 minutes**. Without it the upload works, but the thumbnail step fails with a 403.

## Done when

- `python3 scripts/doctor.py` shows UPLOAD ready
- `youtube_auth.py --check` prints your channel
