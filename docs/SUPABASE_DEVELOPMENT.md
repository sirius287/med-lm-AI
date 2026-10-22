# Connect an existing MedLM development Auth project

Checked against official Supabase documentation on 2026-10-22. This walkthrough
supplements [SETUP_WINDOWS.md](../SETUP_WINDOWS.md), the authoritative local setup
procedure. It does not create a project, rotate keys or change external settings
automatically. Use only the dedicated development project you control.

## 1. Open the correct project

Sign in privately at [Supabase Dashboard](https://supabase.com/dashboard) and select
the existing MedLM development project. Verify its name/organization before saving
settings. Do not create another project, upgrade a plan, or touch another app.

Supabase supplies **identity only** in this local workflow. Application tables and
sessions stay in the isolated local `medlm_dev` database. Do not run MedLM migrations
in Supabase's SQL Editor, copy its database password into the app, or change its
database/RLS settings. The generic Flutter quickstart's sample tables are unnecessary.

## 2. Check signing compatibility before changing anything

Open the project's **JWT Signing Keys** page (or use the
[dashboard shortcut](https://supabase.com/dashboard/project/_/settings/jwt) and
select the verified development project). Inspect the **current/in-use** key's
algorithm, not a standby key. MedLM's `SupabaseGateway.verify_local` accepts only
**ES256** (P-256) or **RS256** with JWKS, issuer, audience and expiry validation.
No private signing key or JWT secret is needed by MedLM.

If the current key is HS256/legacy/shared-secret, stop and report only that
algorithm label. Do not rotate/revoke/import keys, delete legacy keys or weaken
backend verification. Existing projects need a separately reviewed migration after
checking all consumers. Public JWKS availability alone does not prove the current
tokens use the required algorithm. See [signing-key documentation](https://supabase.com/docs/guides/auth/signing-keys).

## 3. Configure email sign-in and the development return URL

In **Authentication**, open the email sign-in provider settings (the dashboard may
label this **Sign In / Providers** or **Providers**). Keep email/password enabled,
allow new email signups for this intended development project, and keep **Confirm
email enabled**. Do not enable anonymous sign-in or add OAuth providers for this test.

In **Authentication > URL Configuration**, set **Site URL** to
`http://localhost:8080` and include that exact URL in the redirect allowlist.
Save only in the verified development project. Keep normal confirmation templates;
MedLM has no custom confirmation callback or automatic web login from a URL token.
After confirming email, type `http://localhost:8080` again and sign in normally.
Never share confirmation links, which can contain tokens.
[Password auth](https://supabase.com/docs/guides/auth/passwords) and
[redirect URL guidance](https://supabase.com/docs/guides/auth/redirect-urls) describe
the provider behavior; the FastAPI cookie login remains MedLM's browser boundary.

## 4. Ensure confirmation mail can reach your test address

Without custom SMTP, Supabase's default sender restricts recipients to the
organization's team addresses and currently limits delivery to two messages per
hour. Use your own authorized team address for this private test, check spam, and
avoid repeated registration clicks. Delivery is best effort, not guaranteed.

Other recipients/public testing require a suitable SMTP service configured privately
in the development project. Review its cost and sender/domain requirements before
creating resources. Never disable email confirmation or manually mark an account
confirmed to bypass this gate. See [SMTP restrictions and configuration](https://supabase.com/docs/guides/auth/auth-smtp).

## 5. Locate the two configuration values privately

The project's **Connect** dialog shows its HTTPS Project URL and publishable key.
Alternatively use **Settings > API Keys** for the **`sb_publishable_`** key.
Use values from the same verified project. MedLM does not need `sb_secret_`,
`service_role`, the database password or a JWT signing secret. Do not paste values
into chat, source code, screenshots or public issues. See [API-key guidance](https://supabase.com/docs/guides/getting-started/api-keys#find-your-keys).

## 6. Save values through the local private prompts

From PowerShell in your checkout (`$env:USERPROFILE\source\medlm-ai` in the Windows
guide), initialize the guarded local
database first using SETUP_WINDOWS.md **only if it has not already been initialized**.
Then run:

```powershell
uv run python scripts/dev.py configure-auth
uv run python scripts/dev.py check --database
git check-ignore .env
```

The helper privately prompts for the Project URL and publishable key and appends
`MEDLM_SUPABASE_URL` / `MEDLM_SUPABASE_PUBLISHABLE_KEY` to ignored root `.env`.
It refuses existing provider settings and preserves encryption keys. Do not delete
an existing `.env` or rerun initialization to force a retry. The check is offline
plus a read-only local database check; it does **not** prove live Supabase sign-in.
No Supabase key needs compiling into Flutter **Web**. Native configuration is separate.

## 7. Verify the real browser journey

Use the exact FastAPI/Flutter terminal commands in SETUP_WINDOWS.md, including
`--dart-define=API_BASE_URL=http://localhost:8000/api/v1`. Open Account, register
your controlled email address, confirm it, return to the app and log in. Check
DevTools Network for JSON from `localhost:8000/api/v1`, not Flutter HTML. Do not
copy request bodies, cookies or tokens into reports.

Only mark live Auth verified after registration/confirmation/login/logout actually
succeed. SMTP limits, an incompatible signing key, missing local setup or network
failure remain distinct blockers. Use synthetic manual medication text only;
clinical uploads and all AI/source-verification capabilities remain unavailable.
