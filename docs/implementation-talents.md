# Talent acquisition and dump contract

`ForeverTome/Talents.lua` supports the inspected Forever client **1.60.1, build 69893**, through `Profile.talents = "traits"`. It reads the player's active class configuration and every readable node enumerated for its trees, including unselected talents. It does not load or switch configurations, commit a build, purchase a rank, or inspect another player. User-supplied loadout names are omitted.

This is source-grounded coverage, not an in-game verification claim. Generated APIs can be unavailable, restricted, or return incomplete data on a particular character. Such results are recorded as partial observations; they are not replacements for complete trees or evidence of talent removal.

## Installed-client evidence

The inspected source root is `../ForeverTome/artifacts/datamining/1.60.1.69893/raw/interface/addons/`.

| Source | Contract used |
| --- | --- |
| `blizzard_playerspells/classtalents/blizzard_classtalentsframe.lua`, especially `UpdateConfigID` | The shared class talent UI selects `C_ClassTalents.GetActiveConfigID()`; Camelot extends this UI. |
| `blizzard_playerspells/camelot/classtalents/blizzard_classtalentsframe.lua`, `RefreshTreeHeaders` | Forever tree headings come from `C_Traits.GetGroupDisplayInfoByTreeID`, including skill-line names, ordering, and icons. |
| `blizzard_playerspells/camelot/classtalents/blizzard_classtalentutil.lua` | Camelot class specialization visuals and custom entry appearance establish the relevant client flavor. |
| `blizzard_apidocumentationgenerated/classtalentsdocumentation.lua` | `GetActiveConfigID` and active configuration events. |
| `blizzard_apidocumentationgenerated/sharedtraitsdocumentation.lua` | Configuration/tree/node/entry/definition/condition/subtree schemas; read signatures; traits events. `GetTreeNodes(treeID)` explicitly includes nodes for all class specializations. |
| `blizzard_playerspells/classtalents/blizzard_classtalentimportexport.lua` | The UI itself uses `activeRank`, `ranksPurchased`, and `maxRanks` for builds. These are preserved separately rather than collapsed into one inferred rank. |

The acquisition path is `C_ClassTalents.GetActiveConfigID()` → `C_Traits.GetConfigInfo(configID).treeIDs` → `GetTreeNodes(treeID)` → `GetNodeInfo(configID,nodeID)` → `GetEntryInfo(configID,entryID)` → `GetDefinitionInfo(definitionID)`. `GetTraitDescription(entryID,rank)` records descriptions for each readable rank. `GetConditionInfo`, `GetNodeCost`, `GetTreeInfo` gates, and node `visibleEdges` describe prerequisites and costs. `GetSubTreeInfo` records subtrees encountered through nodes or entries. `GetTreeCurrencyInfo(...,true)` excludes staged currency changes.

Only exposed `visibleEdges` are available through this contract. No hidden prerequisite edges or unexposed rank-specific spell IDs are invented. Definitions reference the API's `spellID` and optional `overriddenSpellID`; each is sent to `FT.RequestSpell`, including spells on unselected talents. Manual dumps force a metadata refresh request for these spells. Class-tree enumeration does not imply that trees for other character classes are available.

## Observation records

| Kind | Data |
| --- | --- |
| `talent.metadata` | `entity_type`, `entity_id` when available, `config_id`, optional `tree_id`, whitelisted source `info`, and completeness. Entity types are `config`, `tree`, `group`, `node`, `entry`, `definition`, `condition`, and `subtree`. Source field names inside `info` retain API spelling. |
| `talent.rank` | `entry_id`, `rank`, rank description when readable, and completeness. |
| `talent.build` | `scan_id`, `config_id`, `chunk_index`, and at most 32 `nodes`. Each node has `tree_id`, `node_id`, `node_observation_id`, readable purchased/active/current ranks, active entry, and `committed_entry_ids`. `related_observation_ids` also links the referenced node metadata. |
| `talent.snapshot` | Final scan marker: `scan_id`, current configuration, readable `tree_ids`, `has_staged_changes`, scope, node/chunk counts, completeness, previous snapshot ID, and links to all build chunks. |

Metadata is emitted when its whitelisted values or missing-field markers change. A fresh build references the applicable node observation even when that metadata was recorded earlier. Pause and zone boundaries reuse retained metadata; clearing the history clears the cache as well. A manual dump always creates a new build/snapshot even if it is unchanged.

Consumers must join build chunks by `scan_id`, use the final snapshot's completeness, and use node references or entity IDs to recover metadata. A scan without its final marker is unfinished. Partial snapshots must never be interpreted as removals or empty replacement catalogs. Unavailable lists are omitted; readable empty lists remain empty arrays. Per-field failures and truncation are carried in `missing_fields`. `expected_node_count` is omitted when full node enumeration is unknown.

`has_staged_changes` explicitly distinguishes a configuration containing proposed edits. Active and purchased ranks, `activeEntry`, `nextEntry`, and `entryIDsWithCommittedRanks` remain distinct API facts. A scan checks active configuration and staged state again before finishing. Events during the scan invalidate consistency and queue a fresh scan; the interrupted scan stays partial.

## Scheduling and limits

Baseline scans run on entering the world and `FT_BASELINE`. `/ft dump` dispatches `FT_CATALOG`; pending automatic requests are upgraded to preserve manual intent. Trait/configuration/tree/node/condition/subtree/currency and player specialization/talent changes trigger debounced rescans. Requests are coalesced, and scans process four nodes per scheduler step. `FT.TalentStatus()` reports queued/running work and the most recent completeness result.

Limits are explicit: 16 trees per configuration, 2,048 enumerated nodes per tree, 4,096 queued nodes per scan, 64 entries/conditions/groups/edges/gates per corresponding collection, 32 currencies/costs per collection, and 32 rank descriptions per entry. Truncation produces partial coverage. Observations stay small through separate metadata/rank records and 32-node build chunks. The metadata cache retains at most 8,192 records; the existing SavedVariables storage cap still governs all retained observations.

The collector stops safely if storage capacity or record validation resets collectors. It never continues dereferencing a canceled scan. Unknown client profiles do not invoke these APIs.

## Verification

`tests/talents.lua` supplies synthetic client contracts, including selected/unselected nodes and ranks, costs, gates, conditions, tree headings, and uncast spell references. It verifies metadata deduplication; fresh manual dumps; pending manual priority; staged and changed builds; immutable earlier evidence; unreadable/missing data; recovery after partial scans; configuration changes during scanning; bounded build chunks; reload validation; pause/resume and zone behavior; clear/reset behavior; and capacity exhaustion at multiple emission boundaries. These are contract tests, not in-game recordings.
