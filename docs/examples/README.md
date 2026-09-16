# Worked example: quest progress and nearby loot

[Documentation index](../README.md) · [Observation model](../03-data/observation-model.md)

**All data is synthetic.** [quest-and-loot-session.json](quest-and-loot-session.json) is a readable example of the proposed export structure. It is not a WF trace, a supported client adapter, or proof of any API capability.

It is also not an executable replay fixture: it supplies illustrative output without the event/API input trace needed to reproduce it. The [fixture protocol](../06-testing/fixtures-and-replay.md) explains what a regression test must add and how its expected records are reviewed independently.

Quest/item/map IDs in the `990000` range, names, the `SYNTHETIC-CREATURE-A` identity, coordinates, rewards, and timings are invented. That identity is deliberately not presented as a real WoW GUID format. The example contains selected observations, not every notification a real client would emit.

## What happens in the example

| Record | Time after session start | Observation | What a reader can conclude |
| --- | --- | --- | --- |
| 1 | 0 s | Quest accepted | A new observed quest run begins |
| 2 | 0.2 s | Objective snapshot: 0/2 | A baseline exists |
| 3 | 25 s | Creature sighting | The player observed a creature near their own sampled position |
| 4 | 30.2 s | Objective snapshot: 1/2 | Progress occurred between snapshots |
| 5 | 30.3 s | Derived delta: +1 | A comparison establishes progress, without identifying its cause |
| 6 | 31 s | One item visible in a loot slot | Visibility is recorded; source and receipt remain unknown |
| 7 | 31.1 s | Candidate creature/objective association | Close timing suggests a question to investigate, not a confirmed relation |
| 8 | 90 s | Objective snapshot: 2/2, finished | The observed objective is now complete |
| 9 | 90.1 s | Quest ready state | The client reports readiness; no turn-in has yet been observed |
| 10 | 120 s | Reward panel event | An interaction occurred; it does not establish reward receipt |
| 11 | 125 s | Quest turned in | A turn-in was reported; selected item reward and follow-up are unknown |
| 12 | 130 s | Item metadata resolves | The item from record 6 can gain a name without changing its observation time |

Record 7 illustrates a candidate recorded locally at that point in the session. It preserves uncertainty and points to the underlying observations. More expensive analysis can happen externally, with its own creation time and identifiers rather than insertion into an existing immutable addon stream.

## Why fields look this way

- All capability statuses remain `wf_unverified`. Invented data cannot verify a client.
- Locations say `subject: player`; the coordinates do not locate the creature itself.
- Record 4 distinguishes the trigger at 30 seconds from the actual state/location sample at 30.2 seconds.
- The delta links the two snapshots that support it. It has no invented causal entity.
- The empty loot-source array has an explicit `unknown_source` reason.
- There is no `unit.death`, kill-credit, or `item.received` record: the example does not contain that evidence.
- The reward-panel event and turn-in are separate records.
- Item enrichment references record 6 and has no replacement acquisition location.
- The sample ends with no known follow-up quest. A completed quest does not prove a chain ended.

## Reading the JSON

The top-level `session` supplies build/locale/adapter context shared by the records. Every observation has a unique ID, sequence, time, kind, evidence method, related IDs, and missing-field reasons. It follows the proposed fields in the [observation model](../03-data/observation-model.md), but is not a normative JSON Schema.

An implementation can separate derived relationships into their own export section/table. The essential invariant is that derived records refer to preserved observations and never overwrite them.
