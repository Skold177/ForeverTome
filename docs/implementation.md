# Recorder implementation contract — schema 1

This describes the runnable 0.2.1 addon. The original handbook, examples, acquisition backlog, and testing matrix remain research/plans; their unverified capabilities have not become runtime guarantees. The implementation uses the installed Forever Beta 1.60.1.69893 source profile, not the earlier Retail/Titan profiles.

## Saved data

`ForeverTomeDB` is account-scoped. Its envelope has `schema_version`, `synthetic`, an opaque 32-hex `installation_id`, `next_session`, `settings`, `sessions`, `record_count`, and `estimated_bytes`. Each session entry holds `session`, `observations`, and mutable bounded `diagnostics`. A UI reload starts another session while preserving previous records. Character names/GUIDs are not part of session identity.

Session IDs combine the installation's random identity and a persistent increasing serial; observation IDs append the per-session sequence. These are not cryptographic identities. The importer rejects conflicting IDs/headers. Clearing preserves the installation identity/serial so later records do not reuse deleted IDs. Copying SavedVariables to another computer can clone an identity; keep those recording streams separate or resolve conflicts externally.

Each observation has `observation_id`, `session_id`, `sequence`, `kind`, `elapsed_s`, optional `observed_at_server_s`, `capture`, `location`, `data`, `evidence`, `related_observation_ids`, and `missing_fields`. Deferred reads preserve trigger/sample timing. Internal refreshes and periodic sampling use a method instead of pretending a game event fired. Historical records are copied at acceptance and never edited by enrichment.

Missing values are omitted, with reasons where the collector can identify them. False/zero/empty text remain values. Empty arrays become JSON arrays through the export schema; empty maps remain objects. Adding an array field or record kind requires updating the exporter and tests. Uploaded Lua data is never evaluated.

## Retention and workload

- At most 60,000 observations, approximately 48 MiB of estimated plain data, and 512 sessions. Each session reserves 32 KiB for header/diagnostics. These are initial engineering budgets, not measured game performance guarantees.
- A record is limited to 256 KiB, 12,000 values, depth 16, and 65,536 bytes per string. Invalid whole records are rejected with diagnostics; collectors select readable fields before copying.
- At most 128 deferred tasks; four execute per 0.1-second update. Quest/inventory invalidations coalesce. Critical loot/dialogue snapshots are taken synchronously while visible.
- Loot: 200 slots, carried bags 0–4/1,000 slots total. Item metadata: 256 pending variants, 64 references per request, 15-second timeout. Quest limits are in the [quest contract](implementation-quests.md).
- Creature sightings throttle unchanged GUID/dead state for a token to once per ten seconds. Route checks occur every five seconds, recording movement of at least 0.002 normalized combined coordinate distance, map/status changes, or a 60-second heartbeat.
- Vendors: 250 offers/16 costs. Recipe schematics: 32 reagent slots/16 alternatives per slot. Spell and talent catalogs use bounded workers/chunks; see the [spell contract](implementation-spells.md) and [talent contract](implementation-talents.md) for their limits and API evidence.

At capacity recording stops visibly without evicting history. Diagnostics persist outside the main record budget. Pausing, unavailable snapshots, leaving the world, and errors invalidate comparisons so gaps do not become invented progress. Ordinary zone/subzone changes refresh location context while preserving collectors and pending work. Metadata timeouts retain original observations and report unresolved information.

## Evidence boundaries

Each kind's fields are selected explicitly by its collector. The kind list and JSON array shapes live in `tools/export_saved_variables.py`. Replay tests assert results and the absence of unsupported claims.

| Relationship | Representation |
| --- | --- |
| Quest accepted at coordinates | Acceptance event, quest/run ID, fresh player sample |
| Quest progressed in an area | Comparable snapshots and a linked delta at sampling time |
| Creature observed nearby | Sighting and observer map sample; entity position only when separately returned |
| Creature dropped an item | Unresolved; loot slots plus named target/mouseover candidates |
| Item obtained locally | Localized client self-receipt match, separate from inventory deltas/loot slots |
| Vendor sells item | Offer, readable NPC context, prices/stock/costs; no purchase inferred |
| Craft produced output | Client result fields; absent recipe association remains unknown |
| Character has a spell | Readable spellbook entry with known/future/passive/override state; a spellbook difference does not become a learned event |
| Talent connects to another node | Readable tree edges, choice IDs, conditions, costs, and layout; selection state is separate from the tree definition |

`/ft dump` requests fresh spellbook and talent scans. `/ft status` shows pending reads and the last scan's completeness. Save with `/reload` after work settles. The new kinds extend schema 1 and retain older observations. Metadata is keyed by content IDs within the existing client/build scope; spell costs/cooldowns describe the character at sampling time, not immutable base values. Collection reads the current character's accessible data without changing specialization, talents, loadouts, or the spellbook UI.

Do not turn a reward panel into a turn-in, a disappearing nameplate into a death, a dead target into kill credit, or a reopened loot window into another drop. Product/build scope applies to content IDs. Website rendering must escape names/text/hyperlinks.

## Verification and remaining client work

`py tools/test.py` runs required Lua suites, parser/SQLite/export tests, package checks, and isolated mutations that must fail intended assertions. It rejects missing/empty suites, incompatible interpreters, skips, and failed subprocesses. CI builds Lua 5.1.5 using the [official distribution and SHA-256](https://www.lua.org/ftp/); Windows additionally checks packaging, and the full gate is exercised locally with Windows LuaJIT.

Before relying on real uploads: confirm `/dump GetBuildInfo()`, load the addon, accept/progress/turn in a quest, loot manually/automatically, inspect a vendor/creature, `/reload`, and inspect JSON. Include collapsed quest headers, uncached items, grouping, interiors/map floors, and a long session. Record build, readable payloads, errors, save path, and observed performance. The offline harness cannot establish these native behaviors.
