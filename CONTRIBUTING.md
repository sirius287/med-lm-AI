# Contributing

Read README.md, AGENTS.md, the relevant ADR and SECURITY.md. Preserve medical
abstention, literal observations, review/verification separation and owner isolation.
Discuss clinical capability, schema, authentication or retention changes first.
Keep patches focused and include meaningful regression tests.

Use pinned toolchains/lockfiles. Run the isolated backend runner, Ruff, parity
checks and relevant Flutter tests/analysis/builds from SETUP_WINDOWS.md. Never aim
database tests at development/shared/production data. CI uses disposable resources.

Bug reports should include expected/actual behavior, commit, platform and a
synthetic reproduction. Never attach .env, access tokens, cookies, database URLs,
patient images or medication histories. Use .github/SECURITY.md for private reports.

Translations need fluent human review. Medical translation validation is separate;
automated key parity does not approve translations. No security support SLA or
clinical validation is promised. Source licensing awaits the owner's decision.
