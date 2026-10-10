<!-- GenAI Generated code - Start -->
# ArogyaAI

Home remedies, nutrition and preventive health guidance in six Indian languages.
Chat, speak, or upload a photo. When remedies are not enough, find nearby Ayurvedic,
homeopathy and general hospitals by GPS.

Built deliberately small: **FastAPI + vanilla JS + SQLite**. No npm, no bundler,
no build step, no database server. One container, one process.

## What It Does

| Feature | How it works |
|---|---|
| Multilingual chat | English, Hindi, Tamil, Telugu, Bengali, Marathi - UI strings and model replies |
| Follow-up questioning | The system prompt makes the model ask duration / severity / associated symptoms before advising |
| Voice input | Browser Web Speech API (`SpeechRecognition`), per-language locale codes |
| Voice replies | Browser `speechSynthesis` - toggle the Voice Agent pill |
| Skin / wound photo check | Client-side downscale to 1024px, sent to a vision model as a data URL |
| Emergency guardrail | Keyword triage in all six languages adds a red "call 112 / 108" banner plus tap-to-call |
| Nearby hospitals | Browser GPS + OpenStreetMap Overpass API, classified into Ayurvedic / Homeopathy / General / Pharmacy |
| Helplines | 112, 108, 1075, 104, Tele-MANAS 14416, KIRAN, poison control, Childline, Elderline |
| History | SQLite, last 12 turns sent as context |

## Quick Start (Windows)

```powershell
cd c:\workspace\ArgyoAI
Copy-Item .env.example .env
# add LLM_API_KEY to .env, then:
.\run.ps1
```

Open http://localhost:8000.

### Quick Start (macOS / Linux)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # add LLM_API_KEY
uvicorn app.main:app --reload
```

## Model Provider

Any OpenAI-compatible `/chat/completions` endpoint works - only two env vars change.

```ini
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=gsk_...
LLM_TEXT_MODEL=qwen/qwen3.6-27b
LLM_VISION_MODEL=qwen/qwen3.6-27b
```

Tested shapes: Groq, the official Llama API, OpenRouter, OpenAI, and a local Ollama
server (`LLM_BASE_URL=http://localhost:11434/v1`, `LLM_API_KEY=ollama`).

**Model IDs go stale, so the app diagnoses itself.** Providers retire models on a
few weeks' notice - Groq shut down `llama-3.3-70b-versatile` and
`llama-3.1-8b-instant` for free and developer tiers in August 2026. When the
configured model does not exist, the error in the chat bubble lists every model your
key *can* use, so there is nothing to guess:

```
GET /api/models
{
  "configured_text_model": "openai/gpt-oss-120b",
  "text_model_valid": true,
  "count": 12,
  "available": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", ...]
}
```

Pick one from that list for `LLM_TEXT_MODEL`. For `LLM_VISION_MODEL` pick a
**vision-capable** one - text-only models, `gpt-oss` included, reject images, so the
skin/wound photo feature needs a multimodal model.

## Access Gate

The API has no user accounts. Set `ACCESS_CODE` to a shared passcode and every
paid or private endpoint (`/api/chat`, `/api/hospitals`, `/api/session`,
`/api/history`) requires an `X-Access-Code` header matching it. The frontend
prompts for the code once and keeps it in `localStorage`.

```ini
ACCESS_CODE=pick-something-long-and-random
```

Leave it empty for local development and the gate stays off. **Set it before you
deploy to a public URL** - otherwise anyone who finds the URL can spend your model
quota. `/healthz`, `/api/config` and `/api/helplines` stay open on purpose, so the
emergency numbers are reachable even without the code.

This is one shared secret, not authentication. It stops drive-by abuse. It does
not identify users, and it does not make stored conversations private per-person.

## Deploy

### Render free tier (recommended)

The free Hobby plan costs nothing and needs no credit card. `render.yaml` is
already in the repo.

1. Push this repo to GitHub.
2. In Render: **New > Blueprint**, point it at the repo. It reads `render.yaml`.
3. Set the two secrets it asks for:
   - `LLM_API_KEY` - your provider key
   - `ACCESS_CODE` - a long random passcode
4. Deploy. You get an HTTPS URL, which the mic and GPS features require.

Free tier trade-offs: spins down after 15 minutes idle with a 30-60 second cold
start, 750 instance-hours per month per workspace, 5 GB bandwidth. Chat history
lives in `/tmp` and resets on every spin-down - attach a disk on a paid plan if
you want it to survive.

### Other hosts

**Docker anywhere**

```bash
docker build -t arogyaai .
docker run -p 8000:8000 -e LLM_API_KEY=... -e ACCESS_CODE=... \
  -v arogya-data:/app/data arogyaai
```

**Google Cloud Run** - the Starter Tier needs no billing account and scale-to-zero
cold starts are faster than Render's. Detects the Dockerfile, binds `$PORT`.

Hugging Face Spaces no longer works for this: Docker Spaces require a paid plan as
of late 2026. Koyeb's free tier closed to new signups after the Mistral
acquisition.

Serve over **HTTPS**: browsers block geolocation and microphone access on plain
HTTP for anything except `localhost`.

## Corporate Networks (TLS Inspection)

If outbound model calls fail locally with `CERTIFICATE_VERIFY_FAILED`, a TLS
inspecting proxy (Zscaler, Netskope) is re-signing HTTPS with a private root CA
that Python's certifi bundle does not trust. `truststore` is in `requirements.txt`
and validates against the OS trust store by default, which fixes this with no
manual certificate export.

Controls, in order of precedence:

```ini
CA_BUNDLE=/path/to/corporate-roots.pem   # explicit bundle, wins if set
SSL_USE_SYSTEM_CERTS=true                # default - use the OS trust store
SSL_USE_SYSTEM_CERTS=false               # force plain certifi
```

Verification is never disabled. If the proxy also *blocks* your provider by
policy (you get an HTML block page rather than a certificate error), no client
setting will help - deploy to a host outside the corporate network, point
`LLM_BASE_URL` at a local Ollama, or ask IT to allowlist the domain.

## Project Layout

```
app/
  main.py        FastAPI routes, SSE streaming, rate limit, image validation
  config.py      env-driven settings
  prompts.py     language registry + system prompt composition
  safety.py      emergency keyword triage, helpline data
  llm.py         streaming client for OpenAI-compatible endpoints
  hospitals.py   Overpass query, distance, category classification
  store.py       SQLite sessions and messages (stdlib sqlite3)
web/
  index.html     single page + SVG icon sprite
  styles.css     one stylesheet, CSS variables
  js/
    app.js       wiring and state
    chat.js      SSE consumption + message DOM
    i18n.js      six-language strings and quick prompts
    markdown.js  escape-first markdown subset renderer
    voice.js     Web Speech API wrapper
    hospitals.js GPS + finder modal
    helplines.js helpline modal
    modal.js     shared modal shell
```

## API

| Method | Path | Notes |
|---|---|---|
| POST | `/api/chat` | SSE stream of `meta` / `delta` / `error` / `done` frames |
| GET | `/api/hospitals` | `lat`, `lon`, `radius_km`, `category`, `limit` |
| GET | `/api/helplines` | static helpline list |
| GET | `/api/config` | model label, languages, limits (no secrets) |
| GET | `/api/models` | models your key can use, and whether the configured ones are valid |
| GET/DELETE | `/api/history/{session_id}` | replay or delete a conversation |
| GET | `/healthz` | liveness + whether a key is configured |

## Security Notes

Read these before putting it in front of real users.

- **There is no per-user authentication.** `ACCESS_CODE` is one shared passcode (see
  [Access Gate](#access-gate)) plus a per-IP in-memory rate limit
  (`RATE_LIMIT_PER_MIN`). That is enough to stop drive-by quota theft, not enough for
  real multi-user deployment. Put it behind an auth proxy or your own login for that.
- The "profile" is a name in `localStorage` - a display convenience, not an identity.
  Do not treat stored conversations as authenticated per-user data.
- Chat messages and SQLite rows contain health information. Lock down the volume,
  set a retention policy, and check local privacy rules (India's DPDP Act) before
  storing real user data.
- Set `ALLOWED_ORIGINS` to your own domain in production instead of `*`.
- Model output is HTML-escaped before the markdown subset is applied, so model text
  cannot inject markup.
- Uploaded photos are validated for MIME type and size, held in memory, forwarded to
  the model, and never written to disk.
- Browser speech recognition in Chrome and Edge sends audio to the browser vendor's
  service. Text-to-speech stays on the device.

## Limits and Honest Caveats

- Not a medical device, not a diagnosis, not a substitute for a doctor. The system
  prompt refuses diagnoses and prescriptions, but an LLM can still be wrong.
- Emergency detection is keyword-based. It will miss phrasings and fire on harmless
  ones. It only adds a warning - it never withholds the reply.
- Hospital data comes from OpenStreetMap volunteers. Coverage varies by city, and
  Ayurvedic / homeopathy classification is inferred from tags and clinic names.
- Translations are machine-assisted. Have native speakers review before launch.
- Voice input needs Chrome, Edge, or Safari. Firefox has no `SpeechRecognition`.
- The rate limiter is per-process, so it resets on restart and does not coordinate
  across replicas.

## Dependencies

| Package | Version | License |
|---|---|---|
| fastapi | 0.115.6 | MIT |
| uvicorn[standard] | 0.34.0 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| python-dotenv | 1.0.1 | BSD-3-Clause |
| pydantic | 2.10.5 | MIT |
| truststore | 0.10.4 | MIT |

All pre-approved licenses, exact pins, zero frontend dependencies.
Place data © OpenStreetMap contributors, ODbL.
<!-- GenAI Generated code - End -->
