# Disaster History Channel — Autonomous Pipeline

Fully automated documentary-style channel covering aviation, industrial, and
engineering disaster history. Script, voiceover, visuals, captions, and
upload all run on a GitHub Actions schedule with no manual steps.

## How it works

`scripts/run_pipeline.py` runs these stages in order, twice a day:

1. **generate_topics.py** — tops up the topic queue via Claude when it runs low
2. **generate_script.py** — pulls the next topic, writes narration + a scene
   breakdown, rotating between 4 structure styles so videos don't look templated
3. **generate_voiceover.py** — narration → audio (free, via edge-tts)
4. **generate_visuals.py** — one AI-generated illustration per scene (no real
   photos of real tragedies — avoids both copyright and graphic-imagery issues)
5. **generate_captions.py** — transcribes the voiceover for accurate burned-in captions
6. **assemble_video.py** — combines everything into `final.mp4` with Ken Burns
   pans, captions, and background music
7. **upload_youtube.py** — publishes to your channel with generated title/description/tags

If any stage fails, the run stops before upload — you'll never get a broken
or half-finished video posted. You'll just see a red X in the Actions tab
and, if you have notifications on, an email from GitHub.

## One-time setup

### 1. API keys you'll need
- `GEMINI_API_KEY` — for script writing, **free tier, no credit card**:
  1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
  2. Sign in with any Google account
  3. Click **Create API key**, copy it
- Image generation needs **no key at all** (Pollinations.ai)
- YouTube OAuth credentials (see below) — free, just a one-time setup

### 2. Get YouTube upload credentials
1. In [Google Cloud Console](https://console.cloud.google.com), create a project,
   enable the **YouTube Data API v3**, and create an OAuth client of type **Desktop app**.
   Download it as `client_secret.json`.
2. On your own machine (not in CI):
   ```
   pip install google-auth-oauthlib
   python scripts/get_youtube_refresh_token.py
   ```
   This opens a browser, you log into the YouTube channel's Google account,
   and it prints three values.

### 3. Add repo secrets
In your GitHub repo: **Settings → Secrets and variables → Actions**, add:
- `GEMINI_API_KEY`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

Tip: make the repo **public**. Public repos get unlimited free GitHub
Actions minutes; private repos are capped at 2,000 free minutes/month. Your
API keys stay safe either way — GitHub Secrets are encrypted and never
appear in logs or the repo itself, regardless of visibility.

### 4. Add background music
Drop a royalty-free mp3 into `assets/music/` (YouTube Audio Library has free
tracks with no attribution required). Without one, videos will just have
narration only, which also works fine.

### 5. Push and enable Actions
Push this repo to GitHub. The workflow in `.github/workflows/daily_pipeline.yml`
will start running on schedule automatically. You can also trigger a run
manually from the **Actions** tab to test it before the first scheduled run.

## Cost estimate

$0/month. Every stage runs on a free tier or open-source tool:

| Item | Cost |
|---|---|
| Script (Gemini free tier) | Free |
| Voiceover (edge-tts) | Free |
| 14 images (Pollinations.ai) | Free |
| Captions (local whisper) | Free (CI compute only) |
| Upload (YouTube Data API) | Free (well under daily quota at 2 uploads/day) |
| Hosting/scheduling (GitHub Actions) | Free (unlimited on a public repo) |

The only limits you might hit are free-tier *rate* limits, not cost — Gemini's
free tier allows more requests/day than this pipeline needs at 2 videos/day,
and Pollinations' anonymous rate limit is why `generate_visuals.py` pauses
between image requests.

## Things worth knowing

- **Monetization eligibility takes time and human signal.** YouTube's
  inauthentic-content policy specifically watches for zero-variation,
  fully templated output. The structure rotation and per-topic scripts help,
  but consider periodically adding something distinctly human — a short
  intro card, a real narrator for a handful of videos, a pinned comment —
  especially before applying for the Partner Program.
- **Recent tragedies need extra care.** The seed topic list and guardrails
  in `config.yaml` steer away from very recent events with living victims'
  families. If `generate_topics.py` suggests something that feels too raw,
  just delete it from `data/topics_queue.json` before the next run.
- **You still own this channel.** Check in periodically — watch a video,
  read comments, glance at Studio analytics. "Hands-off" should mean you
  don't have to produce anything, not that you never look at it.
