# OCI Companion release workflow

This public Git repository is the source of truth. Pull main before changing the product; do not replace its installer or visual guide from an older standalone checkout.

When delivering a versioned program change, update this repository, run the appropriate checks and publish the matching GitHub release with the latest Install.cmd alongside the required Nextcloud deliverables. Verify Windows CI and an anonymous download of the released Install.cmd before reporting completion. Keep the latest/download/Install.cmd link working. This is the user's standing preference; no repeated publication confirmation is needed for requested program updates.

Keep the approved single-CMD installation and red-box screenshot guide. Supporting files belong under _support. The installer opens its guide only and must not launch Explorer. Preserve the extension path, stored profiles, theme and team-file binding during updates. Preserve unrecognized/modified installations and previous releases.

Publish only reviewed program source and clean release outputs. Never commit customer vaults, credentials, browser profiles, personal screenshots, allowed.json or authentication material. Preserve byte-identical extension assets across platforms. The user manually enables browser security features and reloads the extension; publishing a release does not mean the installed browser extension updated itself.
