# Event ledger

The V3 event ledger lives at `docs/events/ledger.jsonl`. Each JSONL row has a monotonically increasing sequence, unique event ID, event type, phase, original event time (nullable for historical imports), import/record time, actor, optional commit/evidence references, source, details, previous hash and event hash.

The event hash is SHA-256 over canonical JSON excluding `event_hash`. The first `prev_hash` is 64 zeroes; each later event links to the preceding `event_hash`. This detects edits relative to retained trusted history. It is tamper-evident, not proof of identity and not a security sandbox. Human approvals continue to use the separate HMAC approval mechanism.

Writers append and fsync an event before atomically replacing `docs/state.json`. State snapshots keep at most five recent event summaries and remain below 4,096 bytes. If a process stops after event append but before snapshot replacement, replay can restore the snapshot embedded in the latest state event.

The V2 schema-2 importer preserves every log row, including repeated phase entries, null values, deviations, commit/evidence references and original approver/timestamp/signature fields. Missing original timestamps remain null. Import timestamps are recorded separately. Historical `(gate:off)` labels are not human approvals.

Commands:
- `python -m vibe events verify`
- `python -m vibe events migrate-v2 --input PATH --dry-run`
- `python -m vibe events migrate-v2 --input PATH --apply`
- `python -m vibe events replay`
- `python -m vibe events rollback --reason "why the previous durable snapshot is being restored"` (interactive HMAC-signed human approval required)

Rollback appends a signed rollback-approval event and a snapshot-restored event. It restores the previous snapshot but never deletes or rewrites earlier ledger rows. A rollback is always human-controlled, including in autonomous mode.
