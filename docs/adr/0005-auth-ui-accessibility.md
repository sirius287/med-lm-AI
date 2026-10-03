# ADR 0005: Chunk 4 auth UI and accessibility

Date: 2026-09-26. Status: approved scope, implemented locally.

## Context and scope

The earlier plan did not number Chunk 4. The user confirmed email/password auth UI and accessibility, with Android/Web required and English/Hindi/Telugu nonclinical UI localization. Preserve the Phase 1 shell and Chunk 2 authentication adapters. This does not authorize upload UI, OAuth, CI, deployment, clinical functionality or live integrations.

## Decision

Add an account route reached from Home. Home and Settings remain public foundation screens. A UI controller initializes the existing auth adapter and verifies the session before displaying signed-in account content. Route entry and application resume revalidate the session. Server-side authentication and ownership remain authoritative; the UI state is not an authorization boundary.

Registration shows neutral confirmation instructions, not a claim of email delivery or authentication. Login must succeed and restore a verified user. Failed restoration hides signed-in content. Expiry returns the account screen to sign-in with a localized message. Unresolved Web logout or native cleanup failure locks account content and offers retry; no automatic restoration bypasses that lock during the controller lifetime. The lock is in memory, not a persistent revocation mechanism: an application restart can restore a still-valid server session. Existing backend revocation and native/web token storage behavior are unchanged.

## Recovery correction (2026-10-04)

Local tests using the real adapters reproduced two recovery failures missed by the original controller fake. The user approved narrowly scoped fixes and regression validation.

- Native logout continues to clear local credentials even if server revocation fails. After successful local cleanup, report a distinct local-sign-out outcome with an explicit warning that the previous server session may remain. Permit a fresh login; do not retain bearer tokens or attempt unauthenticated revocation retries. Automatic restoration must not erase the warning during the controller lifetime. A fresh login does not prove the old session was revoked. If secure-storage cleanup fails, remain locked and retry cleanup. Remember successful server logout only in memory so cleanup retry need not repeat a now-unauthenticated request.
- Web logout with a missing CSRF token first bootstraps through the existing authenticated session GET. It never publishes a signed-in UI state during this recovery. An invalid 200 bootstrap response fails closed; a verified 401 permits signed-out UI. Deletion still requires the normal cookie/Origin/CSRF checks. A `csrf_failed` response clears the stale in-memory token for the next explicit retry; other failures retain the token. No backend authorization changes or new endpoint are needed.
- Registration failures use registration-specific copy. Rate-limit copy no longer guesses a one-minute wait. Nonclinical localization changes still require human language review.

These corrections add no persistent credential store, live integration, database migration or dependency. Remote revocation after native credential loss remains unconfirmed; this is reported honestly rather than retaining credentials contrary to cleanup safeguards.

Passwords are obscured by default and cleared from the field before submission, on backgrounding and when switching forms. Raw provider exceptions are not displayed. No credentials, user IDs or tokens are persisted by the new controller. Existing native configuration is required; unavailable services produce an explicit unavailable state, never simulated authentication.

Use scrollable bounded forms, Material focus behavior, semantic headings/status announcements, localized field labels and visibility tooltips, and minimum 48-pixel buttons. Keep shadows decorative. Test all three locales in both themes, narrow layouts at 2x text scaling, keyboard navigation and Flutter accessibility guidelines. UI translations require human review before release and are not medical translations.

## Acceptance and limits

Local completion requires controller and widget behavior tests, existing backend/Flutter regression suites, clean analysis, Android debug and Web builds, and `git diff --check`. No new dependencies, APIs or migrations are required. Live provider calls/email delivery, real Android TalkBack and browser screen-reader checks, human language review, and iOS/desktop validation remain separate release evidence. Automated semantics checks are not an accessibility certification.

Official Flutter guidance consulted 2026-09-26: [accessibility tests](https://docs.flutter.dev/ui/accessibility/accessibility-testing), [accessible styling](https://docs.flutter.dev/ui/accessibility/ui-design-and-styling), [web accessibility](https://docs.flutter.dev/ui/accessibility/web-accessibility), and [keyboard/input](https://docs.flutter.dev/ui/adaptive-responsive/input). Existing installed SDK APIs were used; no package upgrades were needed.
