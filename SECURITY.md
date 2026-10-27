# Security Policy & Credential Isolation

## 1. Strict `MODEL_API_KEY` Protection

CrisisGrid authenticates with the official Meta Model API (`https://api.meta.ai/v1`) using a single environment variable: `MODEL_API_KEY`.

To protect credentials across local development, CI, and hackathon judging:

1. **Never Commit Secrets:** `.env`, `backend/.env`, and `frontend/.env.local` are strictly ignored by [`.gitignore`](./.gitignore). Only template files ([`.env.example`](./.env.example), [`backend/.env.example`](./backend/.env.example), [`frontend/.env.local.example`](./frontend/.env.local.example)) with empty placeholders are tracked in Git.
2. **Backend-Only Isolation:** `MODEL_API_KEY` is read exclusively by [`backend/config.py`](./backend/config.py). It is never prefixed with `NEXT_PUBLIC_` and never sent to the browser.
3. **Zero Leakage in Responses or Logs:**
   - `GET /health` and `GET /api/config/status` return only a boolean `"model_api_key_configured": true | false`.
   - Upstream exceptions from `https://api.meta.ai/v1` are mapped through `_meta_error()` in [`backend/main.py`](./backend/main.py) to sanitized HTTP `502`/`503` responses that never echo authorization headers or raw client objects.

## 2. Verifying No Secrets Are Tracked

Before pushing commits, run:

```bash
git status --ignored
python backend/test_meta_api.py
```

## 3. Reporting a Vulnerability

If you discover a potential credential leak or security issue in this repository, please open a GitHub issue or contact the repository maintainers directly.
