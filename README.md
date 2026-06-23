# AI Rundown Reader

Personal Android + local backend workflow for reading The Rundown AI newsletter with Korean chunk translations and vocabulary review.

## What It Does

- Reads a Naver Mail IMAP folder such as `AI rundown`.
- Stores newsletter HTML/text in SQLite.
- Can upload processed articles to Supabase for outside-home mobile reading.
- Uses local Ollama, default `qwen3:4b`, for sentence analysis.
- Serves article data over a small local HTTP API.
- Provides an Android APK project for reading articles and saving vocabulary.
- Exports saved vocabulary as tab-separated text for Anki import.

## Project Layout

```text
backend/            Python stdlib backend
mobile/android/     Native Android Java app
supabase/migrations/ Supabase SQL schema
.github/workflows/  GitHub Actions APK build
```

## Backend Setup

1. Copy `.env.example` to `.env`.
2. Fill in your Naver email and app password.
3. Optional but recommended: create Supabase tables from `supabase/migrations/0001_ai_rundown_schema.sql`.
4. Set `STORAGE_BACKEND=supabase` and fill `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
5. Start Ollama and make sure `qwen3:4b` is available.
6. Run the backend:

```powershell
python backend\app.py
```

Catch up missed newsletters and exit:

```powershell
python backend\app.py --sync-once
```

The worker scans recent mail based on `FETCH_DAYS` and skips messages whose UID already exists, so missed days are processed the next time your laptop is on.

The API starts at:

```text
http://0.0.0.0:8787
```

On your phone, use your laptop LAN IP, for example:

```text
http://192.168.0.12:8787
```

## Useful Backend Endpoints

- `GET /api/health`
- `GET /api/articles`
- `GET /api/articles/{id}`
- `POST /api/sync`
- `POST /api/sample`
- `POST /api/vocab`
- `GET /api/vocab.tsv`

## Android APK Build

This repo includes a GitHub Actions workflow that builds a debug APK:

```text
.github/workflows/android-apk.yml
```

After pushing to GitHub, open the Actions tab and download the `ai-rundown-reader-debug-apk` artifact.

## Notes

- Do not commit `.env`.
- The backend must be running when the Android app refreshes or syncs.
- If Supabase is configured in the app, the app can read already-processed articles anywhere with internet access.
- If Windows Firewall asks whether Python can accept connections, allow it for your private network.
- Direct AnkiDroid insertion is not included in this first MVP. Use the TSV export first, then direct AnkiDroid integration can be added next.
