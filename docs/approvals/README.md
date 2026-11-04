# Human approval records

Approval records are machine-verifiable audit evidence. Each record is bound to a target path, phase and exact staged-content SHA-256 digest. The HMAC-SHA256 key is supplied out of band through `VIBE_APPROVAL_KEY`; never commit the key, put it in project configuration, or include it in logs.

A 32-byte minimum is a lower bound, not a recommendation for a manually memorable passphrase. Use a randomly generated secret, keep it in a local secret manager/environment, and provision the same secret to CI only when a workflow must verify a commit changing a protected path. Losing the key makes existing HMAC records unverifiable; rotate only through a human-reviewed migration.

These records are not proof against hostile code running as the same OS user. File-system permissions, restricted credentials, required reviews and sandboxing remain separate controls.
