# Recorder implementation contract — schema 1

This describes the runnable 0.2.3 addon. The original handbook, examples, acquisition backlog, and testing matrix remain research/plans; their unverified capabilities have not become runtime guarantees. The implementation uses the installed Forever Beta 1.60.1.69893 source profile, not the earlier Retail/Titan profiles.

## Saved data

`ForeverTomeDB` is account-scoped. Its envelope has `schema_version`, `synthetic`, an opaque 32-hex `installation_id`, `next_session`, `settings`, `sessions`, `record_count`, and `estimated_bytes`. Each session entry holds `session`, `observations`, and mutable bounded `diagnostics`. A UI reload starts another session while preserving previous records. Character names/GUIDs are not part of session identity.

Session IDs combine the installation's random identity and a persistent increasing serial; observation IDs append the per-session sequence. These are not cryptographic identities. The importer rejects conflicting IDs/headers. Clearing preserves the installation identity/serial so later records do not reuse deleted IDs. Copying SavedVariables to another computer can clone an identity; keep those recording streams separate or resolve conflicts externally.

Each observation has `observation_id`, `session_id`, `sequence`, `kind`, `elapsed_s`, optional `observed_at_server_s`, `capture`, `location`, `data`, `evidence`, `related_observation_ids`, and `missing_fields`. Deferred reads preserve trigger/sample timing. Internal refreshes and periodic sampling use a method instead of pretending a game event fired. Historical records are copied at acceptance and never edited by enrichment.

Missing values are omitted, with reasons where the collector can identify them. False/zero/empty text remain values. Empty arrays become JSON arrays through the export schema; empty maps remain objects. Adding an array field or record kind requires updating the exporter and tests. Uploaded Lua data is never evaluated.

## Retention and workload

- At most 60,000 observations, approximately 48 MiB of estimated plain data, and 512 sessions. Each session reserves 32 KiB for header/diagnostics. These are initial engineering budgets, not measured game performance guarantees.
- A record is limited to 256 KiB, 12,000 values, depth 16, and 65,536 bytes per string. Invalid whole records are rejected with diagnostics; collectors select readable fields before copying.
- At most 128 deferred tasks; four execute per 0.1-second update. Quest/inventory invalidations coalesce. Critical loot/dialogue snapshots are taken synchronously while visible.
- Loot: 200 slots, carried bags 0–4/1,000 slots total. Item metadata: 256 pending variants, 64 references per request, 15-second timeout. Once basic metadata is readable, missing stats/tooltips receive at most three reads including the first. Each read captures at most 64 stats and 64 tooltip lines, with 1,024 bytes per text side. Quest limits are in the [quest contract](implementation-quests.md).
- Creature sightings throttle unchanged GUID/dead state for a token to once per ten seconds. Route checks occur every five seconds, recording movement of at least 0.002 normalized combined coordinate distance, map/status changes, or a 60-second heartbeat.
- Vendors: 250 offers/16 costs. Recipe schematics: 32 reagent slots/16 alternatives per slot. Spell and talent catalogs use bounded workers/chunks; see the [spell contract](implementation-spells.md) and [talent contract](implementation-talents.md) for their limits and API evidence.

At capacity recording stops visibly without evicting history. Diagnostics persist outside the main record budget. Pausing, unavailable snapshots, leaving the world, and errors invalidate comparisons so gaps do not become invented progress. Ordinary zone/subzone changes refresh location context while preserving collectors and pending work. Metadata timeouts retain original observations and report unresolved information.

## Evidence boundaries

Each kind's fields are selected explicitly by its collector. The kind list and JSON array shapes live in `tools/export_saved_variables.py`. Replay tests assert results and the absence of unsupported claims.

| Relationship | Representation |
| --- | --- |
| Quest accepted at coordinates | Acceptance event, quest/run ID, fresh player sample |
| Quest progressed in an area | Comparable snapshots and a linked delta at sampling time |
| Quest awarded an item | `quest.reward_received` from the native event's quest ID, item link, and quantity; chat receipts and inventory gains remain separate evidence of potentially the same acquisition |
| Creature observed nearby | Sighting and observer map sample; entity position only when separately returned |
| Creature dropped an item | Unresolved; loot slots plus named target/mouseover candidates |
| Item obtained locally | Localized client self-receipt match, separate from inventory deltas/loot slots |
| Vendor sells item | Offer, readable NPC context, prices/stock/costs; no purchase inferred |
| Craft produced output | Client result fields; absent recipe association remains unknown |
| Character has a spell | Readable spellbook entry with known/future/passive/override state; a spellbook difference does not become a learned event |
| Talent connects to another node | Readable tree edges, choice IDs, conditions, costs, and layout; selection state is separate from the tree definition |

`/ft dump` requests fresh spellbook and talent scans. `/ft status` shows pending reads and the last scan's completeness. Save with `/reload` after work settles. The new kinds extend schema 1 and retain older observations. Metadata is keyed by content IDs within the existing client/build scope; spell costs/cooldowns describe the character at sampling time, not immutable base values. Collection reads the current character's accessible data without changing specialization, talents, loadouts, or the spellbook UI.

Do not turn a reward panel into a turn-in, a disappearing nameplate into a death, a dead target into kill credit, or a reopened loot window into another drop. Product/build scope applies to content IDs. Website rendering must escape names/text/hyperlinks.

## Item stats and tooltips

Version 0.2.3 extends `item.metadata` with readable `C_Item.GetItemStats` values and `C_TooltipInfo.GetHyperlink` lines. Both APIs are gated to the supported client profile and are called without changing the visible tooltip UI. Existing item metadata, including `icon_id` or `icon_path`, remains available even when the additional reads fail.

| Data field | Meaning |
| --- | --- |
| `stats` | Map from original stat tokens to finite numeric values, including zero; for example, `RESISTANCE0_NAME` for armor and `ITEM_MOD_STAMINA_SHORT` for stamina when returned |
| `stat_labels` | Readable localized global labels for captured stat tokens, when available |
| `stats_status`, `tooltip_status` | `available`, `partial`, `unavailable`, or `unsupported` |
| `stats_link`, `tooltip_link` | Exact requested item link, or the string `item:<id>` when only an item ID was supplied |
| `stats_context`, `tooltip_context` | `character_at_observation`; these are displayed values at sampling time |
| `stats_method`, `tooltip_method` | API used for each capture |
| `tooltip_lines` | Ordered `{index, left_text?, right_text?, type?}` records retaining source line positions and readable text |

`requested_link` and the client's resolved `link` remain separate metadata fields. Requests retain exact item variants; a shared item ID does not merge differently linked items. Tooltip text can retain weapon damage, speed, and equip/use effects without attempting to parse localized text into universal numeric properties.

A returned empty stat table becomes `stats: {}` and an empty tooltip line list becomes `tooltip_lines: []`, both with status `available`. A missing or unreadable result is omitted and marked `unavailable`, with `missing_fields.stats` or `missing_fields.tooltip_lines` set to `not_ready_or_unreadable`. Absent APIs or unsupported profiles use `unsupported`. Invalid fields and capture limits produce `partial` status with `invalid_or_unreadable` or `capacity_limit`; valid fields remain. Stat tokens are limited to 128 bytes and localized labels to 256 bytes.

Basic metadata is emitted immediately. Unavailable stats or tooltip data remain pending for up to two additional reads through item-load callbacks or the existing one-second worker, within the request's 15-second timeout. Changed results append another linked `item.metadata` record; unchanged retries do not duplicate the record. All prior observations remain intact, and resets cancel pending enrichment. Older recordings cannot acquire missing stats or tooltips without another in-game capture.

## Verification and remaining client work

`py tools/test.py` runs required Lua suites, parser/SQLite/export tests, package checks, and isolated mutations that must fail intended assertions. It rejects missing/empty suites, incompatible interpreters, skips, and failed subprocesses. CI builds Lua 5.1.5 using the [official distribution and SHA-256](https://www.lua.org/ftp/); Windows additionally checks packaging, and the full gate is exercised locally with Windows LuaJIT.

Live 0.2.2 saved data confirms quest acceptance links, objective progress, turn-in, ordinary quest-item receipt delivery, loot capture, and persistence on build 69893. The session header also measures interface version `16001`. These observations establish those exercised paths, not every possible reward or gameplay situation.

The 0.2.3 stats/tooltip addition has offline coverage for armor/stamina/zero values, variants, missing versus empty data, secrets, malformed fields, limits, delayed enrichment, bounded retries, and capacity resets. Verify new item captures in game before relying on their displayed values. Further client checks include collapsed quest headers, uncached items, grouping, interiors/map floors, vendors, and long sessions. Record build, readable payloads, errors, and observed performance. The offline harness cannot establish native behavior beyond the captured live evidence.
