# Chunk 2: email/password session hardening

Date: 2026-09-25. Authorized scope: authentication/session backend and existing Flutter adapter correctness only. Chunk 1 remains accepted; no storage, upload routes, clinical functionality, OAuth, screens, CI or live integration is added.

## Contract and migration

Retain existing health and `/api/v1/auth/register`, `/auth/login`, `GET/DELETE /auth/session` routes and successful JSON shapes. Migration 0003 adds nullable `provider_session_id` to existing web sessions, its lookup index and private HMAC-keyed `auth_throttles` counters. Existing rows/tokens remain usable. Downgrade preserves original session fields but removes binding and throttle counters; do not run hardened application code against a downgraded schema. Migrations 0001/0002 remain unchanged.

New sessions bind to a verified provider user AND session UUID. Legacy sessions lazily establish this binding from their signature-verified existing access token (expiry may be ignored only for this binding step). Normal authentication still requires an unexpired verified token, online provider identity check, enabled local account and absence of a local revocation tombstone. No arbitrary client user ID sets ownership.

## Refresh and logout

Browser refresh and logout lock the same session row. Refresh validates unchanged user/session identity, re-encrypts under the primary key and never extends the absolute app-session expiry (maximum 24h). Invalid credentials/ciphertext or uncertain remote refresh invalidate the app session; known provider-session IDs receive a persistent local revocation tombstone. A transient provider failure outside refresh fails closed without destroying a healthy session.

Remote refresh and local database persistence cannot be atomic. If the database fails after remote rotation, the transaction rolls back and the request fails; no protected result is returned. A later provider response may allow recovery, otherwise sign-in is required. No guarantee of exactly-once remote token use is made.

Cookie logout validates Origin and constant-time CSRF and commits provider-session tombstone plus app-session revocation atomically, then attempts provider sign-out. A bound session can log out even when the provider or token decryption is unavailable. Repeated logout with the same cookie requires its CSRF; absent/unknown cookies return 204 after Origin validation. Native logout verifies JWT signature/expiry locally, records revocation and revokes matching bound cookies before best-effort upstream logout. JWKS retrieval may still require network if signing keys are not cached.

Legacy unbound cookies need signature verification to discover the provider session ID before logout; missing signing keys or unreadable legacy ciphertext can prevent complete revocation. This is an explicit migration limitation, not an unverified decode fallback. Normal session restore migrates the binding. Existing encrypted legacy sessions are not forcibly reset.

Both Authorization and app cookie on a protected request are rejected with 400 `ambiguous_authentication`. Malformed Authorization returns 401. Expired/invalid cookie authentication clears the browser cookie. Logout with invalid Origin/CSRF makes no revocation change. Completed requests cannot undo earlier in-flight operations: later upload/worker code must recheck cancellation/fencing at its own mutation boundary.

`GET /user` verifies provider identity; it is not claimed to prove a provider auth.sessions row still exists. Local app logout/disable is enforced locally; externally initiated provider revocation and account-specific provider lifetime policies remain live-service validation requirements before clinical operations. Uploads remain absent.

## Throttling, keys and maintenance

Configured deployments use atomic PostgreSQL counters: ten registration/login attempts per peer address per 60-second window, shared across app instances. Counts saturate at eleven. Only HMAC hashes are stored; no IP/email/password. All replicas must share `MEDLM_AUTH_RATE_LIMIT_KEY` (independent random >=32-character secret), required in production. Development can use the existing session key as a compatibility fallback; rotating it resets those development buckets. This limiter covers the app's auth endpoints, not direct native Supabase authentication; provider rate limits require separate live configuration.

Unconfigured local development/test shells retain their in-memory limiter. Database failure never switches a configured deployment to memory. The application does not read forwarded headers; run local Uvicorn with `--no-proxy-headers`, or explicitly configure only trusted reverse proxies in deployment. Spoofed/untrusted forwarded addresses must not become rate-limit identities.

Keep `MEDLM_SESSION_ENCRYPTION_KEY` as the primary Fernet key. `MEDLM_SESSION_DECRYPTION_KEYS` is an optional JSON array of at most three previous keys. New writes and successful access use primary encryption; old keys are only for reading. Malformed key configuration is rejected. Do not retire a fallback until all affected sessions were rewritten or their maximum original app lifetime has elapsed; staged deployment must keep old and new keys readable across replicas. Key rotation does not extend session lifetime.

`python -m medlm_api.session_maintenance --batch-size 500` deletes at most 500 expired browser sessions and 500 expired throttle records using SKIP LOCKED. No timer/background worker is installed. It deliberately never removes provider-session tombstones based solely on stored token expiry: refreshed tokens can share the same session ID. Tombstones persist until account deletion or a future proven retention policy. Counts alone are printed; no tokens/identities.

## Client adapters and ownership

The native token coordinator shares adapter refreshes, bounds their wait and blocks results during local logout. Installed GoTrue 2.27.2 also deduplicates refreshes and removes the in-memory session before provider sign-out. Cleanup independently removes secure-storage state even on backend/provider failure; secure-storage deletion failure is reported. A backend failure remains visible, so local sign-out does not claim confirmed server revocation. HTTP 401 restoration clears local auth; 503 retains state for retry. Web cannot erase HttpOnly cookies itself; unsuccessful logout retains CSRF for retry.

The reusable authenticated dependency exposes principal/CSRF, not provider tokens. Its owned-connection dependency sets transaction-local context from the verified principal and rechecks local account/revocation state. Existing restricted database roles and upload denial remain intact. No production test-auth bypass exists.

## Validation and sources

Use synthetic provider responses and real disposable PostgreSQL databases, including concurrent refresh/logout, key rotation, cleanup, shared limits and owner-context tests. Flutter tests use injected adapters/storage; this is not physical Keystore validation. Live Supabase/email/JWKS project configuration remains untested without credentials.

Official sources checked 2026-09-25: [Supabase sessions](https://supabase.com/docs/guides/auth/sessions), [Fernet/MultiFernet](https://cryptography.io/en/latest/fernet/). SDK behavior checked against installed GoTrue 2.27.2 source before modifying adapters. No new dependencies.
