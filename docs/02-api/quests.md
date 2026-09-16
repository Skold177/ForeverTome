# Recording quests and objectives

[Documentation index](../README.md) · [Event catalog](event-catalog.md)

**Status:** R reference unless stated; all WF behavior unverified. Sources: [R-QUEST](../reference/sources.md#r-quest), [T-QUEST](../reference/sources.md#t-quest), [R-OFFER](../reference/sources.md#r-offer), [R-GOSSIP](../reference/sources.md#r-gossip), [R-UI](../reference/sources.md#r-ui).

## The questions we can answer

A useful quest history records what was offered, what was accepted, which objective values changed, where the player observed those changes, when the client considered the quest ready, and whether a turn-in occurred. These are separate observations.

```text
offer observed -> acceptance observed -> objective snapshots/deltas
                                      -> ready state observed
                                      -> turn-in observed
                                      -> later offer observed
```

This is a conceptual path, not a guaranteed event sequence. Auto-accepted quests can omit an observed offer; repeatable quests can create multiple runs of the same quest ID; a recorder may start halfway through a run.

## Read APIs

| R API | Reference result | Recording use |
| --- | --- | --- |
| `C_QuestLog.GetNumQuestLogEntries()` | `numShownEntries, numQuests` | Enumerate visible log entries; headers and visibility affect completeness |
| `C_QuestLog.GetInfo(questLogIndex)` | `QuestInfo` or nil | Read quest ID/title/flags; skip header rows |
| `C_QuestLog.GetQuestObjectives(questID)` | Array of `QuestObjectiveInfo`, or no result | Snapshot objective state |
| `C_QuestLog.IsComplete(questID)` | Boolean | Sample quest readiness/completion state, not reward receipt |
| `C_QuestLog.IsQuestFlaggedCompleted(questID)` | Boolean | Historical completion flag; does not supply a new turn-in time |
| `C_QuestLog.RequestLoadQuestByID(questID)` | Request; observe `QUEST_DATA_LOAD_RESULT` | Resolve missing metadata with bounded retries |
| `C_GossipInfo.GetAvailableQuests()` | Quest offer records | Capture currently offered quests in gossip context |
| `C_GossipInfo.GetActiveQuests()` | Active quest records | Capture interaction-specific active quests |
| `GetQuestID()` | Current dialogue's quest ID, used by the R UI | Associate dialogue with a quest while it is open |
| `GetQuestText()`, `GetObjectiveText()` | Current dialogue text, used by the R UI | Capture narrative/instructions with locale |

The last three globals are established here by UI call sites, not full generated return contracts. Namespaced quest APIs and old global APIs are not interchangeable aliases unless the selected build establishes that.

T includes legacy `GetQuestLogTitle(index)` call sites with the quest ID in the eighth returned position. That is a comparison reference, not permission to hardcode the tuple on WF. `GetQuestLogLeaderBoard` is a historical fallback candidate whose exact WF contract still needs source/runtime verification.

## Quest identity and baseline completeness

Use the numeric quest ID as the content identifier, scoped to WF and its build. A title is localized display text. A quest-log index is a temporary UI position and changes as entries move.

**Proposed design:** assign a quest-run identifier for each observed acceptance. If the quest is already active when recording begins, create a run with `start_reason = baseline` and unknown acceptance time.

A visible-log scan may omit quests behind collapsed headers or filters. Test enumeration with collapsed and expanded headers. Keep a cache of observed active quest IDs and refresh those directly where supported. A missing row in an incomplete scan must not become a removal or abandonment record. Avoid changing the player's log selection/expansion merely to run a passive scan; if a complete supported enumeration path is unavailable, record the scope as partial.

## Objective structure and comparison

R's `QuestObjectiveInfo` contains:

| Field | Meaning for recording |
| --- | --- |
| `text` | Localized description; preserve verbatim as observed |
| `type` | API-provided type string; retain unknown values |
| `finished` | Reported completion flag |
| `numFulfilled` | Reported current progress |
| `numRequired` | Reported target progress |
| `objectiveType` | Optional enum; do not confuse it with an objective identifier |

This structure does **not** provide a stable objective ID. Record the objective's array index together with the quest run and a locally tracked objective-layout revision. An index alone is not safe across changes in quest stages or objective ordering.

For a reliable delta:

1. Keep a complete, readable baseline for the quest's observed objective layout.
2. On a relevant update, capture a new snapshot and its own sampling time/location.
3. Verify the same quest run and comparable objective layout before subtraction.
4. Emit changes in counts and completion flags, including decreases.
5. If the layout changes, record a layout transition and a fresh baseline instead of comparing unrelated rows.

A transition from `3/5` to `5/5` establishes two units of progress between snapshots. It does not establish two distinct observed kills or their individual positions. Item use, shared credit, looting, exploration, scripted interactions, and group actions can all complicate causality. Missing metadata is not a zero-progress baseline.

## Acceptance, readiness, turn-in, and removal

- Decode `QUEST_ACCEPTED` according to the tested build. R supplies only the quest ID; T supplies log index then quest ID.
- `QUEST_COMPLETE` is used by the R UI to display the reward panel. A player can close that panel without completing the transaction.
- Use validated `QUEST_TURNED_IN` as the direct turn-in notification. Its R payload contains quest ID, XP reward, and money reward, not a complete item-reward selection.
- `QUEST_REMOVED` does not state why the quest left the log. Correlate it with turn-in or other explicit evidence; otherwise retain `reason = unknown`.
- `QUEST_FINISHED` closes the interaction in the R UI. Its name must not be interpreted as a successful quest completion.

Separate a current run's readiness from historical completion flags, especially for repeatable and account-related behavior. WF semantics for those cases remain test items.

## Dialogue and quest-giver context

Copy readable quest text, objective text, offered quest IDs, and NPC context during the interaction. Prefer a validated interacting-unit token such as `npc` when the client supplies it; a selected target can be unrelated. If identity cannot be read, retain the dialogue with unknown giver.

Associate the player's map position with the interaction. This is a useful **giver-location sample**, but must remain labeled as observer position. Item-started, remote, and automatic quests may have no NPC giver at all.

Record offered and selected rewards separately if the relevant WF API exposes them. The set of choices is not proof of what the player received.

## Building guides and quest chains

An observed sequence “turned in A, was offered B” is useful evidence for a guide, but does not prove that A is required for B. Level, faction, class, reputation, other quests, or hidden conditions may affect availability.

Keep the sequence as an observation. Promote it to a prerequisite or mandatory-step relationship only through explicit client data with verified meaning or controlled repeated evidence. Never fill a WF quest chain with Retail/Classic IDs just because titles match.

## Validation cases

Test accept, abandon, reaccept, partial progress, progress loss, shared credit, multi-objective completion, reward-panel cancellation, actual turn-in, item-started quests, repeatables, and login with collapsed log headers. The [WF test plan](../04-validation/wf-test-plan.md) defines what to retain for each result.
