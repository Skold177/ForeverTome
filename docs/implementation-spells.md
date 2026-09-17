# Spellbook and spell observations

`Spells.lua` uses the installed Forever Beta **1.60.1 / 69893** interface source. The adapter is enabled only for that build. Runtime behavior still requires in-game validation.

## Source contract

Source paths below are relative to `ForeverTome/artifacts/datamining/1.60.1.69893/raw/interface/addons/` in the sibling research repository.

- `blizzard_playerspells/camelot/spellbook/blizzard_spellbookframe.lua` enumerates `C_SpellBook.GetNumSpellBookSkillLines` and `GetSpellBookSkillLineInfo`, then adds the pet category.
- `blizzard_playerspells/spellbook/blizzard_spellbookcategory.lua` enumerates slots using the skill line's offset and count and uses `C_SpellBook.HasPetSpells` with `Enum.SpellBookSpellBank.Pet` for the pet book.
- `blizzard_apidocumentationgenerated/spellbookdocumentation.lua` defines book entries, skill lines, spell/base/override identity, known status, level learned, lower ranks, loose flyout membership, and `SPELLS_CHANGED`, `LEARNED_SPELL_IN_SKILL_LINE`, and `SPELL_FLYOUT_UPDATE`.
- `blizzard_apidocumentationgenerated/spellbookconstantsdocumentation.lua` defines `Spell`, `FutureSpell`, `PetAction`, and `Flyout` item types and the player/pet banks.
- `blizzard_actionbar/shared/spellflyout.lua` consumes `GetFlyoutInfo` and `GetFlyoutSlotInfo`, including base/override IDs, known status, name, and specialization.
- `blizzard_apidocumentationgenerated/spelldocumentation.lua` and `spellshareddocumentation.lua` define readable spell information, description/subtext, passive status, power costs, current cooldowns/charges, `RequestLoadSpellData`, `SPELL_DATA_LOAD_RESULT`, and `SPELL_TEXT_UPDATE`.
- `blizzard_playerspells/spellbook/blizzard_spellbookframe.lua` and `blizzard_spellbookitem.lua` use specialization and pet-bar change events.

No `GetSpellBaseCooldown` contract or usage was found in this source. `base_cooldown_status=unsupported_client_contract` and the associated missing-field reason explicitly record that limitation. Current cooldown duration is never used as a base cooldown.

## Recorded evidence

Login, baseline recovery, relevant book events, and `/ft dump` schedule a scan. Every readable skill line is visited, including hidden lines, and entries are retained regardless of passive, future, off-spec, lower-rank, or flyout status. Pet actions remain distinct from spells. Only observed spell IDs are requested; there is no numeric ID sweep.

`spellbook.snapshot` contains up to eight entries per chunk, the player skill lines on the first player chunk, a bank, a shared `snapshot_id`, and a `chunk_index`. `spellbook.scan` is the final manifest: its chunk count and completeness determine whether the scan finished consistently. A consumer must wait for this manifest before treating chunks as a completed snapshot. A later change event can invalidate a scan after some chunks have already been written; the final manifest then reports `changed_during_scan`. An unfinished scan, including a logout before its manifest, is incomplete evidence.

Unknown banks omit their entries and counts and report `bank_status=unavailable`; a successfully read empty bank contains an empty entries array and count zero. Entry-level missing fields identify unreadable fields and truncated flyouts. A scan with unavailable entries or ranges is partial. If a complete scan is identical to the preceding snapshot, its manifest reports `unchanged=true`, emits no chunks, and points to the prior snapshot. A manual scan emits fresh chunks even when membership is unchanged.

`spellbook.changed` compares membership only between complete, uninterrupted scans. Future entries are included, so this difference is explicitly **not** a learned/unlearned event. Pause, transitions, and other collector resets invalidate comparisons. Only the verified `LEARNED_SPELL_IN_SKILL_LINE` event creates `spell.learned`.

`spell.metadata` includes the requested and API-resolved IDs, base/override IDs when available, name, icons, cast time, range, description, subtext, passive status, and supported current power costs/cooldowns/charges. Values describe the character at observation time; cast time, range, rendered text, costs, and override icons can reflect character modifiers. The `current_state` object separates temporary charges/cooldowns/costs from spell identity. Nil costs or charges remain explicitly ambiguous, because the API can return nil for both not-applicable and unavailable data.

Metadata requests keep original observation references, original request time, and original observer location while retries sample at their actual completion location/time. Earlier observations are immutable. Repeated references are coalesced with a visible truncation flag. Callers use `FT.RequestSpell(spellID, observationID[, force])`; manual talent dumps use `force=true` to refresh spells absent from the current book.

## Work and storage limits

Book reads and metadata reads process at most eight entries/IDs per callback. Chunk output processes eight entries per callback. A scan admits 64 skill lines, 2,048 combined player/pet entries, and 32 slots per flyout. Exceeding these limits produces partial evidence, not an assertion that the remaining entries are absent. Metadata supports 1,024 pending requests, 4,096 cached IDs, and 32 original references per request. The first rejected request emits `spell.metadata_unavailable`; diagnostic counters and `FT.SpellStatus().metadata_dropped` count additional rejected requests.

Missing text retries at most three times with delayed load requests. Exhaustion emits `spell.metadata_unavailable`; later verified load/text events can enrich previously observed IDs. `/ft dump` also retries unresolved IDs encountered by its spellbook and talent scans. Missing optional APIs do not create collector exceptions or endless retries.

Ordinary zone/subzone changes retain active scans, comparisons, successful metadata, and pending requests without restarting catalogs. Leaving the world retains successful metadata and pending cast requests with their original evidence, but invalidates membership comparisons and restarts interrupted scheduled work on re-entry. Clear, pause, and error recovery cancel pending work and discard stale references.

`FT.SpellStatus()` includes both scheduled and active scans, pending metadata count, latest book completeness, entry count, cache count, and dropped metadata requests. Idle work and zero pending reads mean the dump has settled; they do not imply all client data was available. `/reload` or logout is still required to flush SavedVariables, followed by the existing JSON/JSONL exporter and optional SQLite import.

## Automated validation

`tests/spells.lua` uses synthetic source-shaped data to exercise passive/future/off-spec/lower-rank entries, base/override and flyout identities, pet data, manual contextual refresh, unavailable versus known-empty lists, restricted values, delayed text and immutable origins, bounded retry exhaustion and late recovery, membership versus learned evidence, mutation during scanning, transition reuse, capacity reporting, bounded callback work, and cancellation after clearing.
