# Testing persistence, exports, and upgrades

[Testing strategy](README.md) · [Persistence design](../03-data/persistence-and-export.md)

**Status: proposed test responsibilities.** Offline storage tests can protect our code now; actual WF serialization, flush timing, and restored client state still require the named in-client cases.

## Distinguish the checkpoints

| Checkpoint | Meaning | How to verify |
| --- | --- | --- |
| Captured | Volatile API fields copied into owned data | Mutate source objects immediately and compare |
| Accepted/committed | Record admitted to the in-memory store according to the append contract | Inspect full record and immutable prefix; inject append/acknowledgment faults |
| Client-saved | WoW wrote declared SavedVariables | Real reload/logout test and inspection of the resulting stable file |
| Exported | A frozen batch was encoded or copied | Independently parse and compare expected records without mutating the store |
| Imported | External destination accepted records | Check idempotency, conflicts, batch outcome and recovery |

An in-memory acceptance is not a claim of disk durability. A successful local export UI interaction is not an upload acknowledgment. The UI and diagnostics should use those distinctions, and tests should assert them.

## SavedVariables simulation

The host model holds a mutable **live generation** and an independent **last-saved snapshot**. A simulated save copies only the supported SavedVariables content into the saved snapshot. Restart destroys the entire Lua environment and restores from that snapshot, then loads the real bootstrap and modules in their declared order.

This simulation tests our restoration and data-loss handling, not the native game's writer. A custom test serializer must not be described as WoW's actual serializer. Add round-trip cases using real sanitized SavedVariables files once WF can produce them.

The test must not accidentally keep old globals, pending requests, cached objects, session IDs or scheduler callbacks alive across restart. Restored records belong to their original sessions; new capture begins in a distinct session with fresh transient baselines.

## Minimum save/restart scenarios

| Scenario | Expected outcome |
| --- | --- |
| First boot with no saved data | Valid empty database initialized once; other addons' load notifications ignored |
| Existing supported data | Old records preserved; defaults added only where permitted; no fabricated historical acceptance/turn-in |
| Save, restart, and record more | Saved prefix preserved; new identities and session context are valid |
| Append after the last save, then simulate abrupt termination | Only the last saved snapshot survives; no claim that the unsaved suffix was durable |
| Repeated saves without data change | Semantically identical restored observations; no duplicate records |
| Save while metadata is pending | Original observations survive; restoration follows an explicit pending-request policy |
| Late response after restart | No mutation or cross-session attachment from stale request state |
| Unsupported newer schema | Clear unsupported-state result; original data left intact rather than overwritten |
| Malformed or oversized restored data | Bounded rejection/recovery path with preserved recoverable input; no silent reset |

Pending requests are transient by default. If restart requeues unresolved metadata, it must do so from stable stored observation IDs with a new request generation and bounded policy. No old callback is resumed by reference.

## Test loss honestly

A simulator knows which unsaved events it discarded; the real addon may not. After an unclean restart, record interrupted/unknown prior coverage according to available evidence. Do not invent an exact count or end time for events that were never saved.

Test that a crash after an export was created does not cause automatic local deletion on next boot. Explicit clearing requires its own tested operation, preview/scope, and recording-state transition. A failed or cancelled clear/export must not partially erase history.

## Serialization and immutable export

Freeze an export's selected record set before encoding or chunking. Concurrent new recording may append to the live log but must not change the batch, sequence order, chunk count, or hashes already promised by the export manifest.

Test nested tables, arrays, empty containers, nil/omitted values, false, zero, Unicode, newlines, quotes, backslashes, WoW markup, large allowed strings and numeric boundaries. Reject cyclic/unsupported structures before they reach serialization. Preserve record-array order; object-key ordering is a formatting concern.

Use an independent parser/comparator for exported output. Include a fixture with a field that would be easy to lose, such as an explicit false flag or missing reason, and demonstrate that dropping it fails even if the writer and reader share the same bug.

For chunked exports, test repeated/out-of-order chunks, a missing final chunk, wrong count, mixed export IDs, modified bytes, truncated text and duplicate submission. Incomplete data can be staged with an incomplete status; it cannot be acknowledged as a complete import.

## Migration contract

Each migration declares its source schema, target schema, preserved semantics, expected transformation, and unsupported cases. Include saved-version fixtures from every schema we promise to support. Do not manufacture an old-format fixture by running the current serializer in an “old version” mode; keep authentic versioned examples or independently authored representatives.

Migration follows this logical transaction:

1. Validate the input version and resource bounds.
2. Preserve the original representation in a recoverable location/generation appropriate to the implementation.
3. Build the new representation separately; record deterministic ID/reference mappings when needed.
4. Validate record counts, identities, ordering, relationships, types, missing-data semantics and version-specific expected output.
5. Commit the new active generation and schema version only after success.

Inject failure at every boundary, including before the final generation switch. The prior valid generation must remain usable or exportable. Test an already-migrated input, every supported starting version to the current version, and a failure partway through a chain.

Immutability is semantic preservation across explicit migration, not a requirement that renamed fields or native SavedVariables text stay byte-for-byte identical. Preserve original source-version data for audit/recovery. Do not silently migrate a data-format change without a schema version and fixtures.

An old addon encountering newer data must fail closed for writes to that database. Its normal initialization path must not replace the unknown version with an empty default that the client later saves over it.

## Importer tests when that component exists

Feed the actual parser/import path data-only fixtures, not executable uploaded Lua. Test limits for record count, nesting, strings and identifiers; reject malformed data without execution. Repository-authored trusted Lua test code is separate from externally supplied SavedVariables/trace content.

For identical record identities and content, repeated import has one database effect. Conflicting content under one identity is surfaced/quarantined, not “last write wins.” Simulate a failure between batches and verify the chosen transaction/checkpoint policy: committed records remain correct and retries add only what is missing.

Test references arriving before their related records according to the import contract: stage unresolved links explicitly or reject the batch with a recoverable result. Never silently relink by a matching name or timestamp.

## Performance and capacity checks

Use declared, versioned test parameters for record/byte limits, pending requests, retries and queue budgets. Tiny limits in deterministic tests make overflow easy to exercise. Include reserved diagnostic capacity and confirm that repeated failures cannot consume unbounded memory.

On PRs, prefer stable assertions such as bounded queue length, API calls, allocations measured through owned counters where appropriate, and serialized size over fragile wall-clock thresholds. Add longer seeded sessions and measured benchmarks on a controlled runner; preserve hardware/runtime context. Set production performance budgets from measurements and document them before enforcing them.

## Required real-client evidence

Use V01–V03 for startup/save/reload/interruption, V17 for delayed metadata, V26 for long sessions/capacity, and V27–V28 for export/migration behavior in the [WF validation plan](../04-validation/wf-test-plan.md). Record actual file content and build/revision provenance. An offline passing restore test must not close a native save-timing question.
