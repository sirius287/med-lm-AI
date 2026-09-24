# Phase 1 foundation decisions

Date: 2026-09-24. The explicit Phase 1 implementation request supersedes the original prototype-only phase sequence.

- Preserve the planned monorepo: Flutter in `apps/medlm`, FastAPI in `services/api`, shared Python interfaces in `packages/backend_domain`. `services/worker` is reserved, not runnable.
- Canonical API prefix is `/api/v1`, matching the implementation request. `/health` is a liveness alias. `contracts/openapi.json` describes only implemented endpoints. Clinical routes remain design contracts, not empty success handlers.
- Supabase owns credentials. Native sessions use secure storage; web uses backend opaque HttpOnly cookies with encrypted upstream tokens, Origin/CSRF checks and serialized refresh. Phase 1 implements email/password exchanges; OAuth authorization-code/PKCE remains planned. There is no login UI yet.
- Use an application-owned `medlm.users` subject projection instead of coupling local migrations to Supabase's managed `auth.users`. Only a verified provider identity creates the projection. Future account deletion needs a verified provider event/reconciliation process; cascades alone do not delete the provider account.
- `medlm_auth` is server-only. Runtime credentials must not be available through Supabase browser Data API roles. Domain tables enforce RLS and transaction-local owner context; clinical tables have no runtime grants yet. Migration owner and runtime role are separate.
- The initial schema prepares clinical tables but does not implement their state machines, immutable history, outbox, idempotency, confirmations or reminder activation. Those must precede clinical write endpoints. JSON fields are placeholders for future versioned validated contracts.
- Image validation and owner-scoped memory storage are internal prototypes only. Memory storage is bounded and expires on access/explicit purge; it is not a durable purge worker or production retention guarantee. No upload endpoint is exposed.
- No OpenAI client is instantiated. Model name is configuration, not evidence of account access. No medical outputs, sources or prescriptions are seeded.
- UI preferences are session-local for now. Hindi/Telugu strings are nonclinical scaffolding and need native-language review before release.

Next phase: Phase 2, secure foundation completion and platform validation. Validate real Supabase sessions and refresh/revocation, physical Android and macOS/iOS builds, durable image lifecycle, accessibility, CI and distributed abuse protection. Resolve source/model/privacy gates before clinical AI phases. Manual reminder functionality remains a later phase.
