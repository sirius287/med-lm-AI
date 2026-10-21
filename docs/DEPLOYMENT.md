# Staging deployment preparation — not a deployed service

No cloud account, paid resource, domain, database or public URL is provisioned.
Provider choice, costs/current quotas, project identities, region and access require
the owner's decision and current provider documentation. No free tier is assumed.
Do not point local setup/test scripts at staging or production.

## Architecture

Serve the Flutter static build and FastAPI `/api/v1` through the **same HTTPS
origin**. Do not put the browser frontend and cookie API on unrelated domains:
the current SameSite=Lax browser session depends on same-site cookies.
Use separate staging PostgreSQL and Supabase Auth projects, backend-only secret
management, and a private database network. The runtime must not own tables or
have superuser/CREATE DATABASE/CREATE ROLE/BYPASSRLS. Apply only normal runtime
grants; analysis/upload capabilities remain unavailable.

`infra/api.Dockerfile`, `infra/Caddyfile` and `infra/compose.staging.yml` are
reviewable preparation, not proof of a tested deployment. Container builds,
TLS issuance, browser CSP compatibility and provider resources require validation.
The API image excludes `.env`, Git history, local test databases and Flutter files.
It runs as non-root with access logs and proxy headers disabled. Compose exposes
only the edge's HTTP/HTTPS ports, never the API. Caddy owns TLS and SPA fallback;
`/api/*` must return API JSON/404 rather than the Flutter shell.

## Required gates before starting public staging

1. Confirm the account, hostname, region, visibility and expected cost privately.
   Use synthetic accounts and manual data only. Publish known limitations prominently.
2. Provision an isolated empty staging PostgreSQL database and distinct schema-owner
   and restricted runtime roles. Have an operator verify target identity, migrations
   to the actual head, runtime grants, FORCE RLS, backups and restore. The local
   `init-db` helper intentionally refuses non-local targets and is not a cloud tool.
3. Configure the intended staging Supabase Auth project: confirmed email, delivery,
   exact HTTPS Site URL/redirects, ES256/RS256 signing/JWKS, abuse controls and quotas.
   No OAuth flow is claimed. Do not change an unrelated project.
4. Put the MEDLM_ variables from the compose file in the hosting secret manager.
   Use distinct stable session/medication keys and a separate rate-limit key.
   Never use owner credentials at runtime. No OpenAI credential is needed.
5. Review proxy trust **before public registration**. With proxy headers disabled,
   API throttling sees the proxy address and can throttle all users together. This
   is fail-closed, not a public multi-user configuration. Configure a verified fixed
   internal proxy address/allowlist and overwrite untrusted forwarded headers at
   the edge before enabling Uvicorn proxy headers. Never trust `*` or an arbitrary
   client X-Forwarded-For header. Validate separate-client rate limits and spoofing.
6. Schedule/test the documented expiry-only medication replay cleanup using its
   separate maintenance role, key rotation, incident response and erasure/backup
   retention policy. Do not grant maintenance privileges to normal runtime.
7. Review Flutter's self-hosted CanvasKit build and CSP in a real HTTPS browser;
   do not allow arbitrary third-party script/medical telemetry to fix rendering.
   Test cookies, CSRF, CORS, session expiry, owner isolation and request-log redaction.

## Operator commands after the gates and explicit deployment approval

Build Flutter from `apps/medlm` with its pinned toolchain:

```text
flutter pub get --enforce-lockfile
flutter build web --release --dart-define=APP_ENV=production --no-web-resources-cdn
```

Keep API_BASE_URL unset to use same-origin `/api/v1`. Configure secrets privately
through the provider, not a committed Compose env file. To validate interpolation
locally without revealing values, use `docker compose ... config --quiet`, never
print the expanded configuration. After approval and secret configuration:

```text
docker compose --env-file .env.example -f infra/compose.staging.yml build
docker compose --env-file .env.example -f infra/compose.staging.yml up -d
```

Do not run these now against an unverified account/host. The explicit blank example
env file prevents Compose from
automatically loading the local development .env; the operator supplies verified
staging values through the secret-manager process environment. Never substitute
the populated development file. Pin tested container image
digests before release; tags alone can move. Confirm licenses/maintenance of all
deployment dependencies. A managed static/API host may replace Compose if it
preserves the same-origin/security architecture; no provider is presumed available.

## Public smoke test and rollback

- Verify real frontend/API HTTPS URLs and TLS; signed-out session is JSON 401.
- Register/confirm/login/logout an account entered privately. Verify HttpOnly,
  Secure, SameSite cookies, rejected CSRF/origins, expiry, and cross-owner 404s.
- Exercise manual add/edit/schedule/taken/skipped/history/delete with clearly
  synthetic text. Confirm no analysis/review/report route is present normally.
- Verify no request bodies, cookies, medication data or secret values enter logs.
- Check backup/restore and operator erasure before inviting real people.

Rollback the application artifact to a tested prior version without schema
downgrades/data deletion. Use a reviewed migration/backup plan for incompatibilities.
Do not claim public readiness until these checks, CI, translations/accessibility
review and privacy/India release review are recorded. No clinical readiness follows
from passing engineering checks.
