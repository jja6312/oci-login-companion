# OCI Companion

A Chrome/Brave Manifest V3 extension for OCI operators managing many tenancies. They search a tenancy or customer alias with Ctrl+Shift+Space, press Enter, and continue through the fixed OCI login flow using their saved username, password and administrator-issued Bypass Code.

Profiles live in extension-local storage or a read-only team JSON file connected by file picker or the optional Windows native file reader. No own server, analytics or Chrome sync. Same-path offline updates preserve the extension ID and stored configuration. Store publishing was cancelled by the user.

The approved interface follows the user's Proton Pass screenshot: search above a tenancy list and credential detail, dark default, user-chosen accent. Preserve this interface while adding functions.

Version1.2 adds: same originating normal/private window for login; a visible customer alias field (existing JSON name); separate Excel-column bulk paste with row validation, secret-free preview and single append; six round accent presets directly below search. Bulk adds to personal storage, never writes directly into read-only team files. Incognito requires the browser's per-extension allow setting. Accounts and explicit theme changes are shared; incognito login metadata is not persisted.

Success: pick the intended customer/account quickly, retain exact password/code text and row alignment, and log in in the same browser privacy context. Never select a different OCI session arbitrarily. External SSO, CAPTCHA and changed Oracle page structures can require manual handling.

1.2.1: reliably adapt Oracle JET nested inputs/validated values and disabled Korean sign-in; inject at DOM readiness. User explicitly removed empty-state marketing copy: keep only Add account with local Alt+N.

1.2.2: observed global→regional OAuth→IDCS redirect support, with routing-only intermediaries and no new regional host privileges. User-triggered diagnostics contain only safe categories/flags for support; never credentials/account/URL data. Version is visible in the existing footer. No new marketing copy.

1.2.3 MFA completion: choose the explicit Oracle BYPASSCODE factor even when its icon button has no useful text; wait for its verified generic JET code view, fill/commit the code and verify once. Never classify an SMS/TOTP field from a nearby alternative-method heading.
