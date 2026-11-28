# OCI Companion 2.0 security design

This document describes the shipped implementation, not an independent security certification.

## Threat model and boundaries

Protect credential confidentiality and integrity when an attacker obtains browser-profile files,
selected team JSON files or encrypted exports without the vault password or live session key.
No application backend, telemetry, Chrome Sync or remote code is introduced. Oracle receives
selected login fields through its normal HTTPS page; OneDrive synchronization is external.

An unlocked compromised device/extension, malicious code with access to the login page DOM,
OS swap or memory dumps, clipboard history, weak/reused passwords, authorized team members,
old plaintext backups and authenticated old-file replay are outside this guarantee. Vault lock
does not log out OCI. Password/code co-storage still reduces MFA-factor independence.

## Envelope and cryptographic operations

`lib/vault-crypto.js` uses browser Web Crypto only. Envelope `oci-companion-vault`, version1,
contains a random UUID, fixed algorithm identifiers, PBKDF2-HMAC-SHA-256 parameters,
16-byte random salt, encrypted32-byte random data key, and encrypted normalized profile JSON.
PBKDF2 uses600,000 iterations; parsing accepts600,000–2,000,000 to prevent downgrade and
unbounded work. New passwords require12+ characters, maximum512; long unique passphrases
are recommended. There is no server verifier, recovery secret or password cache.

Both data-key wrapping and profile encryption use AES-256-GCM with fresh random12-byte IVs
and128-bit authentication tags. AAD canonically binds format/version/vaultID/purpose/KDF.
Envelope shape, base64 canonical form, algorithms and size are strictly checked before KDF.
Inner data retains the512KiB/300-profile limits; envelope input is bounded to1MiB.
Unknown encrypted formats never fall back to legacy parsing.

Password change creates a fresh data key, salt and vaultID and reencrypts the whole payload.
Rewrapping the old data key alone would let someone holding an old file/password decrypt
future files. Old credentials and past versions nevertheless remain usable until separately
revoked at OCI and access to shared storage is withdrawn.

## Key lifecycle and plaintext

Personal ciphertext is stored in `chrome.storage.local.personalVault`; team ciphertext is in
the selected file. File handles remain in IndexedDB. No clear password or unwrapped key is
stored in local/sync storage, IndexedDB, exports, URLs or installer backups.

Unwrapped data keys are kept in **chrome.storage.session**, which Chrome documents as
in-memory, and are restricted to TRUSTED_CONTEXTS. This deliberately survives MV3 worker
suspension without an offscreen keepalive or persistent key cache. The password is used only
to derive a nonextractable wrapping CryptoKey and cleared from UI fields after the attempt.
JavaScript garbage collection and OS memory erasure are not claimed to be controllable.

The UI keeps decrypted records/drafts only while unlocked. Login jobs keep one selected
profile in session memory for at most3minutes. Global lease expiry is5minutes after trusted
extension interaction; browser restart/reload/update clears session storage, explicit Alt+L/
lock and supported device idle/locked events clear it sooner. A session epoch invalidates
pending KDF results, stale editors and queued job writes. A mutex serializes lease operations;
commit guards prevent a completed KDF from reinstalling a key after lock. START and bulk-write requests are also bound to their originating vaultID/unlock epoch, so a queued request cannot regain authority after a later unlock.

Lock scrubs customer list/detail DOM, inputs and staged data, removes keys/job/status/identity
cache, and sends cancellation to tracked content drivers. The engine checks cancellation
through asynchronous validation and before submit; fields already delivered to Oracle's DOM
cannot be recalled. Learned identity bindings and last-used metadata are memory-only; old
persistent metadata is removed on update. Content scripts cannot read local/session stores
and receive stage fields only after current document/origin/window checks. Every CLAIM also
rereads the encrypted source, binding and normalized selected-profile fingerprint, stopping
when credentials, file password/key or the source change.

## Migration, sharing and exports

Legacy data is never automatically displayed for use. A leftover personal plaintext list must
be protected before opening a team source. Personal migration writes verified ciphertext,
reads/decrypts it, then removes `profiles`; an interruption can temporarily retain both forms.
The next authenticated unlock verifies exact equality before cleanup; divergent copies stop
without deleting either. Unsupported/corrupt input does not create an empty replacement.

Team migration requests actual browser write permission within the submit gesture, performs
revision/binding checks, writes through createWritable and verifies readback before success.
No automatic plaintext backup is created. Previously authenticated encrypted team bindings
are marked with nonsensitive local pins so a plaintext/empty downgrade is rejected. Pins do
not prevent replay of an older valid encrypted file. Existing user backups/OneDrive history
and disk remnants are not securely erased; operators must manage and rotate exposed secrets.

Team files use a separately chosen shared password. All holders can decrypt all entries;
there is no per-user authorization, audit service, remote wipe or distributed revocation.
Existing write serialization/revision checks protect local concurrent changes and preserve
newer data, but are not a cross-PC lock or proof of OneDrive upload completion.

Exports are authenticated encrypted envelopes. Import requires an unlocked destination and,
for encrypted input, its source password. Legacy JSON import is explicit and warns that the
original stays plaintext. Templates contain placeholders only. Native file/host permissions
remain user-controlled. CSP/packaging integrity is defense in depth, not proof against all
exfiltration or supply-chain compromise.

## Evidence and sources

Web Crypto vectors and negative tests include independently generated Python cryptography
AESGCM/hashlib fixtures in both directions, not just a self-roundtrip. Browser integration uses
synthetic credentials, real encrypted storage/handles and controlled lock races. Disposable
per-file permission records model native consent; actual customer OS/OneDrive/Android and
physical device-lock behavior are separate verification boundaries.

- [OWASP PBKDF2 guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#pbkdf2)
- [AES-GCM IV and AAD](https://developer.mozilla.org/en-US/docs/Web/API/AesGcmParams)
- [Chrome local/session storage](https://developer.chrome.com/docs/extensions/reference/api/storage)
- [Chrome idle API](https://developer.chrome.com/docs/extensions/reference/api/idle)
- [Shared DOM boundary](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts)
- [Oracle bypass expiry/use controls](https://docs.oracle.com/en-us/iaas/Content/Identity/users/generate-bypass-codes-user-accounts.htm)
