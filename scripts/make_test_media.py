#!/usr/bin/env python3
"""make_test_media.py - synthetic inputs for the end-to-end tests. macOS only (uses `say`).

    python3 scripts/make_test_media.py            # writes tests/fixtures/

raw-recorded.mp4  a 1920x1080 "recording" whose speech has dead air, a filler-only cue and a
                  restarted sentence - everything the editor agent is supposed to cut
face.png          a transparent cutout stand-in for the creator's face
music.m4a         a quiet pad for the music bed
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tests", "fixtures")

SPEECH = (
    "Hello friends, welcome back. Today we learn how incidents work in ServiceNow, step by step. "
    "[[slnc 2600]] Um. [[slnc 900]] "
    "So the first thing you need is the incident table. [[slnc 700]] "
    "So the first thing you need is the incident table, which stores every ticket your users raise. "
    "When a VPN stops working, the user raises a ticket, and it lands in this table with a number. "
    "[[slnc 1500]] "
    "Next, let us talk about assignment groups. Every incident goes to a group, and the group decides "
    "who works on it. If the group is wrong, the ticket waits, and the user gets angry. "
    "[[slnc 1400]] "
    "Third, priority. Priority comes from impact and urgency. High impact and high urgency means "
    "priority one, and priority one means people are watching the clock. "
    "[[slnc 1500]] "
    "Finally, resolution. When you fix the problem, you write the resolution notes, you set the state "
    "to resolved, and the user gets an email. That is the whole life of an incident. "
    "Comment below which table you want next, and see you in the next video. Bye, bro."
)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"failed: {' '.join(cmd)}\n{r.stderr[-800:]}")


def main():
    os.makedirs(OUT, exist_ok=True)
    aiff = os.path.join(OUT, "speech.aiff")
    run(["say", "-v", "Rishi", "-r", "175", "-o", aiff, SPEECH])
    raw = os.path.join(OUT, "raw-recorded.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30",
         "-i", aiff, "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-ar", "48000", raw])
    os.remove(aiff)
    # A round, warm "face" with real transparency.
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0xE0A070:s=800x900,format=rgba",
         "-vf", "geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lte(pow(X-400,2)/pow(330,2)+pow(Y-430,2)/pow(400,2),1),255,0)'",
         "-frames:v", "1", os.path.join(OUT, "face.png")])
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         "aevalsrc=0.2*sin(2*PI*220*t)*(0.6+0.4*sin(2*PI*0.25*t))+0.15*sin(2*PI*330*t):s=48000:d=120",
         "-c:a", "aac", "-b:a", "128k", os.path.join(OUT, "music.m4a")])
    print(f"wrote {OUT}: raw-recorded.mp4, face.png, music.m4a")


if __name__ == "__main__":
    main()
