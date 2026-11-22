# OCI Companion

A Chrome/Brave Manifest V3 extension for OCI operators managing many tenancies. They search a tenancy or customer alias with Ctrl+Shift+Space, press Enter, and continue through the fixed OCI login flow using their saved username, password and administrator-issued Bypass Code.

Profiles live in extension-local storage or a team JSON file connected by the browser file picker, editable by default, subject to the browser’s actual file write permission. No own server, analytics or Chrome sync. Same-path offline updates preserve the extension ID and stored configuration. Store publishing was cancelled by the user.

The approved interface follows the user's Proton Pass screenshot: search above a tenancy list and credential detail, dark default, user-chosen accent. Preserve this interface while adding functions.

Version1.2 adds: same originating normal/private window for login; a visible customer alias field (existing JSON name); separate Excel-column bulk paste with row validation, secret-free preview and single append; six round accent presets directly below search. Bulk adds to personal storage, never writes directly into read-only team files. Incognito requires the browser's per-extension allow setting. Accounts and explicit theme changes are shared; incognito login metadata is not persisted.

Success: pick the intended customer/account quickly, retain exact password/code text and row alignment, and log in in the same browser privacy context. Never select a different OCI session arbitrarily. External SSO, CAPTCHA and changed Oracle page structures can require manual handling.

1.2.1: reliably adapt Oracle JET nested inputs/validated values and disabled Korean sign-in; inject at DOM readiness. User explicitly removed empty-state marketing copy: keep only Add account with local Alt+N.

1.2.2: observed global→regional OAuth→IDCS redirect support, with routing-only intermediaries and no new regional host privileges. User-triggered diagnostics contain only safe categories/flags for support; never credentials/account/URL data. Version is visible in the existing footer. No new marketing copy.

1.2.3 MFA completion: choose the explicit Oracle BYPASSCODE factor even when its icon button has no useful text; wait for its verified generic JET code view, fill/commit the code and verify once. Never classify an SMS/TOTP field from a nearby alternative-method heading.

1.3: personal and team import/export targets are explicit. A team file can remain read-only or allow edits, bulk append and import directly into the selected file. New files start empty. Every UI open/focus/visible refresh and login start rereads the connected local file; OneDrive synchronizes that file between PCs independently. Shared-source records are not copied into personal storage. Revision checks preserve newer local file changes while edits/imports are staged; they are not a distributed lock or a OneDrive upload acknowledgment.

1.3.1: one file-picker connection path; no native helper UI, path entry, messaging or extension permission. Missing Brave APIs receive concise one-time browser flag instructions and a working settings-page action, without copying files into an import snapshot. The user enables the browser feature and relaunches. Existing native mode stops with a reconnect prompt instead of choosing another old handle or personal list.

1.3.2: distinguish a saved file with expired permission from an unconnected file or a missing file. Reopening the popup queries actual access; request restoration once only when the initial toolbar action supplies activation. Otherwise focus an inline restore action, usable with Enter, without requiring file reselection or settings Apply. A persistent browser Always grant is used automatically. Only the browser/user can grant it; do not edit preferences, fake a cached grant or fall back to stale/team secrets copied into personal storage. Missing edit permission is requested on the edit action when team writing was explicitly enabled.

1.3.3: first execution explicitly selects local storage or a shared team file; the file branch chooses create empty JSON or connect existing JSON and completes directly without settings Apply. Cancel/error keeps a retryable unfinished step. Existing installations retain their accounts/theme/source and skip onboarding, including empty users on an extension update. Remove the app editing checkbox and ignore its legacy false flag: editing is available by default, while browser write consent and all revision/binding/conflict protections remain enforced. First completed setup wins across windows. Historical opt-in editing requirements above are superseded.
