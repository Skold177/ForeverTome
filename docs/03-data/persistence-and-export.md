# Persistence, retention, and export

[Documentation index](../README.md)

**Status:** established WoW persistence baseline with a proposed ForeverTome pipeline; WF file paths and save behavior require runtime tests. Manifest/lifecycle references: [R-TOC](../reference/sources.md#r-toc), [R-LIFECYCLE](../reference/sources.md#r-lifecycle).

## SavedVariables is the normal storage boundary

A TOC declaration such as `## SavedVariables: ForeverTomeDB` identifies a global for the client to restore and save. `SavedVariablesPerCharacter` provides a separate character-scoped declaration. This is client-managed persistence, not an API for appending arbitrary files.

**Proposed design:** use one account-scoped database with explicit session separation. The declaration's name is an implementation proposal. Initialize/migrate the restored data on the addon's own `ADDON_LOADED`, without overwriting valid saved observations.

The normal WoW persistence model writes SavedVariables at logout and UI reload. Appending to a Lua table, closing an export window, or running a timer does not by itself force a disk flush. A crash or forced termination can lose the current unsaved interval. There is no general “flush this SavedVariables table now” API assumed by this design.

The exact WF behavior must be verified through the save/reload/relaunch cases in the [test plan](../04-validation/wf-test-plan.md). These source declarations do not expose the native serialization implementation or prove crash durability.

## Storage locations are templates until measured

Typical WoW layouts place saved files under the actual product's `WTF` directory:

```text
<product>/WTF/Account/<account>/SavedVariables/ForeverTome.lua
<product>/WTF/Account/<account>/<realm>/<character>/SavedVariables/ForeverTome.lua
```

The first corresponds to account-scoped data; the second to per-character data. Neither is a verified WF installation path. Identify the actual file created by a controlled WF persistence test instead of assuming a launcher folder.

Copy files after a normal logout/exit or a validated reload/save cycle. Do not edit a SavedVariables file while the client may later overwrite it with its in-memory version. A companion tool should read a stable copy and never use the live game file as a shared writable database.

## Proposed data flow

```text
Permitted game events/state
  -> ForeverTome's bounded plain-data records
  -> client-managed SavedVariables
  -> user-selected saved file or copied export
  -> external parser and validation
  -> review/redaction
  -> database import
  -> evidence-backed items, quest routes, and guides
```

The addon is responsible for observation and local export preparation. A separate program or website handles parsing, transcription, upload, aggregation, and publication. No uploader or server is implemented by this PR, and no addon-side HTTP capability is assumed.

## Two possible export routes

| Route | Benefit | Limits and required behavior |
| --- | --- | --- |
| User selects a saved file | Handles larger batches without copying UI text | Must explain save timing, identify the actual product path, and parse safely |
| User copies a serialized text export | Allows reviewing an export during the session | Needs a tested edit-box size/chunking strategy and explicit copy action; not automatic clipboard or network access |

For chunked exports, include an export ID, schema version, chunk index/count, and integrity checks in the external format. A partial chunk set must not be accepted as a complete dataset. Snapshot the selected records before export so live recording cannot change a batch midway.

Never delete recorded data merely because an export dialog opened or a file was selected. Successful upload acknowledgment belongs to the external workflow; clearing local history should be a separate explicit action.

## Safe import and representation

SavedVariables files contain Lua syntax. **Do not execute uploaded files with Lua, `load`, `loadstring`, or another evaluator.** Use a deliberately restricted data parser or export a non-executable format such as validated JSON. Treat names, descriptions, and hyperlinks as untrusted text when rendering.

Validate schema version, field types, allowed record kinds, collection size, nesting depth, string length, identifiers, timestamps, and coordinate systems. Reject secrets/unsupported objects at the addon boundary; an importer cannot repair an invalid capture policy.

Use stable observation IDs for idempotent imports. The same file can be uploaded twice or copied before all metadata is resolved. Preserve enrichments and detect conflicting IDs rather than double-counting or overwriting silently.

## Growth and performance

An event recorder can grow for hours. Define limits for retained records, estimated bytes, metadata queues, and per-kind capture rate before implementation ships. A record-count limit alone does not control large dialogue strings.

Recommended initial policy: bound all queues; stop or reduce collection visibly at capacity; emit a `coverage.gap`/capacity diagnostic. Do not silently evict old unexported records. If an opt-in rolling history is later added, document exactly what is lost and retain its gap markers.

Deduplicate descriptive metadata by product/build/locale/content identity. Coalesce identical state snapshots where their repetition adds no value, but retain distinct occurrences. Avoid continuous high-frequency location or combat logging when event-context samples answer the project's questions.

Measure memory usage, saved file size, serialization/reload time, event-handler cost, and gameplay responsiveness during a long session. Choose limits from those measurements rather than treating an arbitrary number as a client guarantee.

## Schema migrations and recovery

Store `schema_version` in the saved database/export. A migration should validate the input, preserve a recoverable prior representation, and advance the version only after success. Unknown newer schemas should be left intact with a clear error, not reset to an empty database.

Test empty, older, truncated, malformed, and oversized data. Preserve readable old records when an optional collector fails. Record an interrupted session as interrupted/unknown-end rather than inventing a clean logout.

The [persistence test strategy](../06-testing/persistence-and-recovery.md) specifies simulated saves, interrupted writes/migrations, independent output comparisons, immutable export batches, and the real-client evidence needed to verify native saving.

## Data minimization

ForeverTome needs gameplay evidence, not private communications. Default to excluding chat conversations, real names, Battle.net identifiers, guild/member lists, and other players' names/GUIDs. Optional loot-message parsing should retain the item/quantity and validated recipient classification, not the full chat payload.

Use local opaque session/character references where continuity is necessary. Keep NPC text and readable non-player content identity because they serve the database purpose. Make recording state, pause/resume, export preview, and deletion understandable to the player. Account/character folder names in a saved-file path are not export metadata.

This is a proposed product behavior, not a claim that the client automatically anonymizes exports.
