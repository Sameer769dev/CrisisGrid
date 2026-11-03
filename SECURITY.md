# Security Policy

## Supported Versions

CrisisGrid receives active security updates and dependency maintenance on the following release lines:

| Version | Supported          |
| :---    | :---:              |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability or potential credential issue in CrisisGrid, please do not disclose it publicly via GitHub issues or discussions.

Instead, please report it through one of the following responsible disclosure channels:

- **Primary Contact:** [baralsamir941@gmail.com](mailto:baralsamir941@gmail.com)
- **GitHub Security Advisory:** Submit a confidential report via [GitHub Security Advisories](https://github.com/Sameer769dev/CrisisGrid/security/advisories/new)

### Report Details
To assist in triage and resolution, please include:
- A description of the vulnerability and its potential impact.
- Steps to reproduce or a minimal proof-of-concept.
- Affected endpoints, scripts, or dependencies.
- Relevant system logs (with sensitive tokens or keys redacted).

All security reports are acknowledged within 48 hours. Coordinated disclosure will follow after a patch has been tested and merged.

## Credential Isolation & Environment Architecture

CrisisGrid enforces server-side credential isolation and strict secret sanitization:

- **Server-Side API Key Containment:** The Meta Model API key (`MODEL_API_KEY`) is consumed strictly within the Python backend runtime ([`backend/config.py`](./backend/config.py)). Credentials are never exposed to the client-side bundle or prefixed with client-exposed environment markers (`NEXT_PUBLIC_`).
- **Sanitized Diagnostics:** Observability endpoints ([`GET /health`](./backend/main.py) and `GET /api/config/status`) report configuration readiness as boolean indicators without echoing bearer tokens or raw request headers.
- **Error Shielding:** Upstream communication exceptions from external APIs are caught and transformed into sanitized HTTP `502` / `503` responses, preventing internal client configurations or authorization headers from appearing in stack traces.
- **Source Control Cleanliness:** Local environment files (`.env`, `backend/.env`, `frontend/.env.local`) are explicitly excluded via [`.gitignore`](./.gitignore). Safe placeholder templates ([`.env.example`](./.env.example)) are provided for deployment configuration.
