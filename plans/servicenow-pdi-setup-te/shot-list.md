# Shot list: ServiceNow Telugu Ep 2 (free PDI, first login, first incident)

Record these and hand them over in one folder. The beat numbers match `script.md` / `script.json`.
"Spoken" is about how long your talking takes in that clip at 150 wpm. Screen clips will run longer
than that (typing, page loads, waiting), and that is fine: record it all and the edit cuts the dead time.

Record the screen clips **in order, in one sitting**, because each one starts where the last one ended
(account, then PDI, then login, then incident). Record clip 13 before clip 01, because the hook cuts away
to the finished incident.

## Raw footage checklist

| # | Filename | Type | Shows | Beats | Spoken | Raw length |
|---|----------|------|-------|-------|--------|------------|
| 1 | `01-facecam-hook.mp4` | Face cam | Cold open, both hook lines, straight to lens. Record **both hooks** (Hook 1 and Hook 2 from script.md), 2-3 takes each, so the pick at the script gate costs nothing. | 1-2 | ~25 s | 1-2 min with takes |
| 2 | `02-facecam-turn.mp4` | Face cam | Ep 1 comment story (read it off the screenshot), "no job guarantee", the 4-step roadmap. | 3-4 | ~50 s | 1-2 min |
| 3 | `03-facecam-what-is-pdi.mp4` | Face cam (optional slide) | Office example, what a PDI is, why it helps in interviews, what you need. | 5-8 | ~66 s | 2 min |
| 4 | `04-screen-signup.mp4` | Screen (+ face cam PiP) | Type developer.servicenow.com, home page, click the sign-up control, fill the sign-up form. **Blur email + password.** | 9-11 | ~41 s | 2-4 min |
| 5 | `05-facecam-verify-email.mp4` | Face cam (optional 3-5 s of the "check your email" page) | "Verification mail vasthundhi, spam folder check cheyyandi". **Never record the inbox.** | 12 | ~12 s | 30 s |
| 6 | `06-screen-first-signin.mp4` | Screen | Sign in to the developer site, any first-time questions. **Blur email + password.** | 13 | ~17 s | 1-2 min |
| 7 | `07-screen-request-instance.mp4` | Screen | Request-instance button, release choice (if shown), the progress page. Keep recording through the wait; write down the real wait time. | 14-16 | ~34 s | as long as setup takes |
| 8 | `08-screen-instance-details.mp4` | Screen | The panel with instance URL, username, password. **Blur URL number + password.** | 17 | ~13 s | 30 s |
| 9 | `09-facecam-privacy.mp4` | Face cam | "URL, password evvariki share cheyyakandi." | 18 | ~14 s | 30 s |
| 10 | `10-screen-first-login.mp4` | Screen (+ face cam PiP) | Open the instance URL, log in, password change prompt if any, landing page. **Blur address bar + password fields.** | 19-20 | ~30 s | 1-2 min |
| 11 | `11-screen-ui-tour.mp4` | Screen | Navigation menu + filter ("incident"), Favorites/History, profile menu, where the release name is shown. **Blur any email in the profile menu.** | 21-23 | ~46 s | 2-3 min |
| 12 | `12-facecam-incident-intro.mp4` | Face cam | "Last video lo VPN example gurthundha?" | 24 | ~11 s | 30 s |
| 13 | `13-screen-first-incident.mp4` | Screen | Create new incident: number, Caller, Short description "VPN not connecting", Description, Category, Impact/Urgency/Priority, save, list view, form view, State, activity history. | 25-31 | ~95 s | 4-6 min |
| 14 | `14-screen-pdi-inactivity.mp4` | Screen (+ face cam PiP) | Developer-site text about inactivity / sleep / reclaim, highlighted while you read it out. | 32 | ~18 s | 1 min |
| 15 | `15-facecam-close.mp4` | Face cam | Homework, backup pointer, recap, comment question, Ep 3 pointer, "See you in the next video. Bye, bro." Hold 3 s still at the end for the end screen. | 33-37 | ~60 s | 2 min |
| 16 | `16-facecam-during-screen.mp4` (optional) | Face cam | Keep the face cam running during clips 4-14 as one long file, for picture-in-picture. Clap once on camera at the start of each screen clip so the editor can sync. | 9-32 | n/a | whole screen session |

Total spoken: about 1,329 words, about 8:52 at 150 wpm (target 9:00).

### Stills / assets

- **A1 Thumbnail face:** not needed. `assets/brand/faces/` already has six presenter photos
  (`presenter-confident`, `-idea`, `-money`, `-point-down`, `-think`, `-welcome`). Optional: one new
  photo of you pointing at a laptop showing the PDI home page (URL blurred), if you want an
  episode-specific thumbnail.
- **A2 Ep 1 comment screenshot** (`a2-ep1-comment.png`): the MERN-stack comment on
  https://youtu.be/s93rIkJhFgs, for beat 3. Blur the handle and avatar.
- **A3 Finished incident still** (`a3-first-incident.png`): screenshot of your VPN incident form, URL
  blurred. Thumbnail option and backup for the beat-2 cutaway.
- **A4 Room tone** (`a4-room-tone.wav`): 10 seconds of silence in the recording room, same mic.

## Recording settings

- **Resolution / frame rate:** 1920x1080, 30 fps, for both screen and face cam. Set the display to a
  16:9 resolution if you can, so nothing gets letterboxed.
- **Browser:** a fresh, clean browser profile (new Chrome profile or a guest window) with no saved
  passwords, no autofill, no extensions, no history. Bookmarks bar hidden. Only one tab open. Close
  every personal tab, mail, WhatsApp Web and chat.
- **Browser zoom:** 125% (try 110% if the ServiceNow form gets cramped). Text must be readable on a phone.
- **System:** turn on Do Not Disturb / Focus so no notification banners appear. Hide the Dock and
  desktop icons. Make the cursor bigger (System Settings > Accessibility > Display > Pointer size) and
  move it slowly. Pause one second before each click.
- **Mic:** use the same external or lavalier mic for every clip, 15-20 cm from your mouth, fan and AC
  off, same room for all clips. Record a level check first and listen back. Talk over the screen clips
  live (it sounds more natural than a voice-over added later).
- **Face cam:** lens at eye level, light in front of you (window or lamp behind the camera), same
  framing and same shirt in every face cam clip so the cuts match.
- **Mistakes:** if you fumble, pause 2 seconds and say the whole sentence again. Do not stop the
  recording. The edit removes the bad take.

## Privacy: what must never appear unblurred

Never show these on screen. If they do appear, tell the editor the timestamp so it gets blurred:

1. **Any password**: sign-up form (clip 4), developer-site sign-in (clip 6), the instance credentials
   panel (clip 8), instance login and password-change prompt (clip 10). Best: pause the screen recorder
   while typing a password, or type it with the field off-screen.
2. **Your email inbox**: never record it at all (beat 12 is face cam on purpose).
3. **Your email address**: sign-up form, sign-in, the profile menu in the instance (clip 11), any
   account page.
4. **Instance URL / instance number**: details panel (clip 8), address bar during login and the whole
   tour (clips 10, 11, 13), the hook cutaway (beat 2). Blur the address bar for the whole instance part.
5. **Browser autofill dropdowns** that show saved emails or names.
6. **The commenter's handle and avatar** in the Ep 1 comment screenshot (A2).
7. Anything in the developer site's account or profile pages beyond your name.

## VERIFY WHILE RECORDING

The script was written without access to the live site. Each item below is something you **read off
your own screen** and say as it is. If your screen differs, say what you see and tell the editor; do
not read the script's guess. Write the answers down; the description and chapters will use them.

| ID | Beat | Check on screen | What to say if it differs |
|----|------|-----------------|---------------------------|
| V1 | 6, 9, 16 | developer.servicenow.com is still where you get a PDI, and sign-up plus instance is free (no payment details asked). | If anything paid or a card is asked, stop and tell the director before publishing. |
| V2 | 10 | The name of the sign-in / sign-up button and where it is. | Say the real label. |
| V3 | 11 | Which fields the sign-up form actually asks for. | Name only the fields you see. |
| V4 | 12 | Whether a verification email is sent, and roughly how fast. | No email step: drop beat 12. |
| V5 | 13 | Whether first sign-in asks onboarding questions (student / developer etc.). | None: cut the second half of beat 13. |
| V6 | 14 | The label and place of the request-instance button. | Say the real label. |
| V7 | 15 | Whether you can pick a release, the release names shown, and which one is marked recommended / latest. | No choice: "naaku release choice raaledhu". |
| V8 | 16 | How long setup actually took for you. Say it as "naaku ... minutes pattindhi", with no promise for others. | Say your real time. |
| V9 | 17 | Instance URL format and the username shown (the script assumes the panel shows a username; it does not assume "admin"). | Read the real username; blur the URL. |
| V10 | 19 | Whether the first instance login forces a password change. | No prompt: cut that sentence. |
| V11 | 21 | Name and position of the main navigation menu (script says "All") and its filter box. | Say the real name. |
| V12 | 22 | Whether "Favorites" and "History" exist with those names. | Say what is there, or cut beat 22. |
| V13 | 23 | What the profile menu shows (name, settings). | Say what you see. |
| V14 | 23 | Where the release name of your instance is shown, and the name itself. | Read it from wherever it is. |
| V15 | 25 | The label of the "create new incident" module under Incident. | Say the real label. |
| V16 | 25 | That the number is filled in automatically and its prefix (script does not say "INC" aloud; you do, if that is what shows). | Read the number prefix you see. |
| V17 | 26 | That demo users exist in the Caller lookup. Read the name you pick. | If the list is empty, pick your own user and say so. |
| V18 | 28 | Category options (is there a network-type option?). | Pick the closest and say its name. |
| V19 | 28 | Whether Priority changes on its own when Impact and Urgency change, and to what. | If it does not, say so; do not claim the rule. |
| V20 | 29 | Label of the save button (script says "Submit"). | Say the real label. |
| V21 | 31 | Name and position of the activity / history section on the incident form. | Say what it is called. |
| V22 | 32 | The developer site's own wording on inactivity, sleep/hibernation, reclaim and how to wake an instance. Read it off the page. **Say no number of days that is not on that page.** | If there is no such text, say "rules developer site lo check cheyyandi" and nothing more. |
| V23 | 30 | The State value of your new incident. | Read it. |
| V24 | 2, 6, 17, 20 | That your account in the instance has the admin role ("meeru admin" is said four times). | If not admin, tell the director: beats 2, 6 and 20 need a rewrite. |

Also: the description link in beat 9 ("link description lo pedathanu") means the metadata step must
put https://developer.servicenow.com in the description, as Ep 1 did.
