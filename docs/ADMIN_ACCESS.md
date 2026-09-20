# Administrator access

The public entry point is the homepage. `/login` permits administrator authentication; all analysis pages, profile, saved sites, climate data, catalog APIs, reports, downloads, API documentation and OpenAPI schema require a valid administrator session. There is no public registration or visitor analysis role. The homepage never requests or renders saved sites for visitors.

Configure `SOLARYN_ADMIN_USERNAME` (default `admin`) and `SOLARYN_ADMIN_PASSWORD_HASH` in the host environment. Generate the latter using `foundation_auth.password_hash` with a securely obtained password. Never commit plaintext passwords or hashes. Missing configuration fails closed: the homepage remains accessible but nobody can log in or use private endpoints.

Passwords use salted scrypt. Random 256-bit session tokens are stored only as SHA-256 hashes in SQLite, expire after eight hours, and are revoked on logout or credential rotation. HTTPS/Render cookies use Secure, HttpOnly and SameSite=Strict. Dynamic responses are not cacheable. Cross-site writes are rejected. Login attempts are limited to ten per client address per 15-minute window. The existing free Render disk remains ephemeral; restarts may remove sessions and demo results.

2026-09-20 verification: 92 tests pass across authentication, foundation, climate, performance and reports. Tests cover guest direct-page/API/export access, malformed credentials, forged cookies, throttling, expired sessions, logout replay, credential rotation, missing configuration, cross-site requests, and authenticated analysis regressions. Frontend lint, syntax and TypeScript checks pass. No numerical science was changed.

Admin credentials are handed to the owner in a local file outside the Git repository. Only the password hash is configured in Render. Changing that environment value and redeploying invalidates existing sessions.
