# Recording invariants and regression requirements

[Testing strategy](README.md) · [Regression matrix](regression-matrix.json)

**Status: proposed acceptance rules.** An invariant is a property that must continue to hold across future implementations. The matrix connects these stable IDs to concrete scenarios; no scenario is implemented yet.

## Record integrity

### INV-01

**Only validated, readable plain data can become an observation.** Validate field types, required fields, supported keys, bounded sizes and schema version before committing. Reject functions, frames/userdata, metatables, cycles, non-finite numbers, unsupported keys and inaccessible values at the relevant boundary.

Do not traverse arbitrary API tables in an attempt to sanitize everything. Collect only allowed readable fields. Tests distinguish field-level omissions with a documented reason from a malformed whole record that must be rejected.

### INV-02

**Accepted data has independent ownership.** Mutating an API return table, caller-owned candidate, nested objective, source list, vector-derived coordinates, or metadata cache after acceptance cannot change the accepted observation, including before a deferred store operation runs.

Test shared nested references as well as a shared top-level table. A shallow copy must fail this suite. Reusing a work buffer after enqueue must not corrupt older queue entries.

### INV-03

**Committed history is immutable during normal operation.** Later event handling, enrichment, deduplication, sorting, diagnostics, reader access, and export cannot alter any existing observation or its position in the committed prefix.

Snapshot the prefix with an independent deep structural reader at each checkpoint, then compare it after every relevant action. A checksum can help locate a change, but cannot replace an independent comparator. Explicit user deletion and versioned migration are different operations with separate tests; they are never silently invoked by normal capture/export.

### INV-04

**Identity and ordering remain valid.** IDs are unique in their declared scope. Sequence numbers strictly increase within a session and are never reassigned to previously committed observations. Do not require contiguity where rejected/aborted operations legitimately consume an ID. Preserve append order during export.

Test repeated timestamps, session-ID collision handling, restore/reload, sequence boundaries, and delayed work from an old session. Human-readable timestamps are not unique keys. Session IDs must not expose a character identity.

## Event meaning

### INV-05

**Records say only what was observed.** Preserve the actual adapter/profile, event or read, evidence method, content IDs, locale, sample time and location subject. A reward panel is not a turn-in; a dead sighting is not kill credit; a visible loot slot is not personal receipt; the player's position is not an NPC position.

Use negative assertions: zero `quest.turned_in` records after cancellation, zero `unit.death` records from nameplate removal, and no invented creature source when a loot mapping is absent. These assertions protect meaning more effectively than a generic snapshot of every event.

### INV-06

**Deduplication follows the domain contract.** Repeated invalidation/readiness notifications for one context can be coalesced. Distinct loot interactions, separate sources, repeated quest runs, and valid repeated acquisitions must remain distinct.

Test both a duplicate that should have no additional effect and a similar-looking separate occurrence that must survive. A global key such as item ID, quest ID, event name, or current second is insufficient. The harness does not promise exactly-once delivery from the game; it protects our documented handling of the inputs actually delivered.

### INV-07

**Unknown values keep their meaning.** Missing, not-ready, restricted, unsupported, false, zero, empty text, and empty collections do not become interchangeable. A missing position does not turn into `(0, 0)`. An empty loot-source list can still carry `unknown_source`.

Assert missing reasons alongside omitted/null fields, including export/restore behavior. Preserve valid zero-valued fields and false flags. Verify localized strings, markup and Unicode survive unchanged.

### INV-08

**Asynchronous enrichment adds evidence without rewriting the event.** Resolve pending requests by the validated identity/build/context. Late metadata creates a separate linked record or permitted metadata entry; it does not change the original acquisition time, position, quantity or evidence.

Test duplicates, unrelated IDs, failures, timeouts, newer request generations, and callbacks after a session/context closes. A response need not belong to our request. The deduplication policy must not erase genuinely changed metadata or confuse a resolved name with an item receipt.

### INV-09

**State comparisons respect boundaries.** A quest delta requires comparable snapshots of the same run/layout. A loot slot belongs to one interaction. Unit tokens can be reused. Transitions, partial scans, reloads and coverage gaps invalidate affected transient baselines.

Test acceptance/removal/reacceptance, changed objective layouts, collapsed/filtered scans, zone changes, token reuse, and old callbacks. Never infer abandonment from an incomplete enumeration or subtract across unknown intervals as if recording were continuous.

## Storage and failure behavior

### INV-10

**A failed operation cannot silently corrupt committed state.** Define an in-memory append boundary: validate/copy first, then commit a complete record and its bookkeeping coherently. On a catchable injected failure, either the record was committed once or it was not committed; existing history remains unchanged and outcome/diagnostics are explicit.

Exercise faults before validation, during allowed copying, before append, and after append but before queue acknowledgment. Retries must inspect the commit outcome and preserve exactly one effect for the same internal submission, without suppressing a different gameplay occurrence. This is not a promise of atomic disk transactions or recovery from process termination/OOM.

An exception in one collector must not stop an independent healthy collector. Diagnostics are bounded and cannot fail by formatting the rejected payload.

### INV-11

**Serialization and restore preserve supported data.** A normal supported save/load/export/import path retains every accepted record's semantic content, IDs, array order, references, and missing-data distinctions. Validate against independently reviewed expected records, not only a writer/reader round trip.

Distinguish in-memory commit, simulated save, actual client save, export copy, and database import. A crash before a client save can lose the unsaved suffix; tests must not pretend it was durable. See [persistence tests](persistence-and-recovery.md).

### INV-12

**Upgrades preserve recoverable prior data.** Every supported old schema has a fixture and declared migration outcome. Successful migration validates a new generation before replacing the active one. Failures and unknown newer versions leave the input recoverable and do not reset it to defaults.

Test intermediate failures, repeated migration, older-version chains, malformed input and a newer version encountered by an older addon. Semantic preservation is checked against the source-version contract; renamed fields can change representation without changing the observation's meaning.

### INV-13

**Capacity limits are observable and bounded.** Record, byte, metadata, retry and queue limits have explicit behavior. Reaching a limit cannot silently evict unexported history or trigger unbounded recursive diagnostics/retries.

Reserve a small bounded diagnostics/health budget outside the main observation capacity. Mutable operational counters are not committed observations. Finalized gap summaries can be appended using reserved capacity or exported through an explicitly defined diagnostic field. Test a full main log and a failing diagnostics sink so the system does not depend on spare space to report missing coverage.

### INV-14

**Repeated import does not duplicate or overwrite evidence.** The importer uses versioned identity and content checks: identical observations are idempotent; the same identity with different content is an explicit conflict. A partial chunk set is not a complete export, and a failed batch is resumable according to a declared transaction/checkpoint policy.

Scope this invariant to the actual importer when it exists. Until then it is a required future boundary, not a passing addon test.

## Scope and enforcement

### INV-15

**Collection stays inside its permitted scope.** Passive collectors do not cast, loot, buy, train, choose rewards or dialogue, or inspect privileged data to populate records. Assert that disallowed action APIs are never called. Event/API profiles remain explicit; a reference signature is not silently selected for an unknown WF build.

Model rejected/secret inputs offline and verify real permissions in the client. A passing mock is never recorded as proof of native secure/secret behavior.

### INV-16

**The regression gate cannot pass without its promised tests.** An admitted mechanic/profile must map to discovered, executed tests and expected results. Missing fixtures, zero discovered tests, unexpected skips, swallowed assertion errors, lost process exit codes and overwritten golden files are failures.

Test the harness by deliberately introducing known errors. At minimum, its tests must detect nested aliasing, wrong payload decoding, an in-place history update, a dropped serialized field, and a disabled required suite. A red/green test demonstration is evidence that the gate can catch the regression, not an invitation to ship the broken variant.

## Baseline preservation and intentional exceptions

Normal capture keeps a structurally identical committed prefix. Explicit deletion may remove data only through its dedicated user action. Migration creates a new versioned representation with a preserved/recoverable original. A schema or behavior change cannot be justified by simply editing golden files until the suite passes.

These invariants protect correctness rather than implementation details. A refactor may change queues, internal tables, or batching, provided it preserves the documented observations and declared operational limits.
