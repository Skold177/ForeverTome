# WF client validation plan

[Documentation index](../README.md)

**Execution status: not run.** No WF client, test character, or runtime trace was available to this documentation contribution. The cases below are a reproducible plan, not reported results.

The complementary [test harness strategy](../06-testing/README.md) protects production-code behavior through offline replay, immutable-record assertions, and persistence checks. Its [regression matrix](../06-testing/regression-matrix.json) links scenarios to the V-cases below. Passing synthetic tests does not mark a client case passed; sanitized client traces should later become replay fixtures while retaining their build/context evidence.

## Objective

Determine which observation paths work from an **ordinary third-party addon** on a named WF build, which payloads they deliver, what fields are readable, and what limitations must accompany exported data. A built-in Blizzard UI working is not sufficient evidence.

## 1. Establish the client and test context

Record the launcher product, actual installation directory, full `GetBuildInfo()` output, `WOW_PROJECT_ID`, `GetLocale()`, addon revision, enabled addon set, date, and relevant gameplay context. Exclude account names and character-identifying paths from published evidence.

Reference diagnostic commands:

```text
/dump GetBuildInfo()
/dump WOW_PROJECT_ID
/dump GetLocale()
/dump C_Map and type(C_Map.GetPlayerMapPosition)
/dump C_QuestLog and type(C_QuestLog.GetQuestObjectives)
/dump C_Item and type(C_Item.RequestLoadItemDataByID)
/dump type(GetLootSourceInfo)
/dump type(issecretvalue)
```

These inspect identity/function presence. They do not prove permissions, argument order, event delivery, or complete coverage. Do not dump potentially secret gameplay payloads or whole social-data tables.

Identify the client UI/API extraction corresponding to that exact build and record an immutable revision or local extraction checksum. Keep an unmatched source branch labeled as a reference.

## 2. Create a minimal test recorder in a later implementation change

The current PR deliberately contains no runnable addon. The test implementation should have the measured TOC version, a basic frame event subscriber, allowlisted readable fields, a bounded log, and SavedVariables. Enable collectors one at a time.

Use the client's event-tracing tools if available to inspect permitted event timing, but verify the same behavior from ordinary addon code. Broad “record every event and argument” tracing is not a production collector and may expose unrelated or restricted values.

Verify both function presence and behavior. On R, `C_EventUtils.IsEventValid` and frame registration have distinct meanings; check the actual return value and observe delivery. Do not infer success just from a non-throwing call. [R-EVENT](../reference/sources.md#r-event)

For combat, inspect the actual client restrictions first. A secure-only or denied path is an unavailable result, not a request to try alternative privileged routes.

## 3. Execute the scenario matrix

Every case starts **not run**. Preserve expected versus actual outcomes, including failures. Use controlled gameplay with other unrelated actions minimized, then repeat realistic mixed-activity cases.

| ID | Scenario | Evidence to capture | Pass criterion for the collector |
| --- | --- | --- | --- |
| V01 | Fresh install/login | Load order, own `ADDON_LOADED`, initialized storage | One session, valid restored/default data, no premature state reads |
| V02 | UI reload then normal logout/relaunch | In-memory IDs and stable saved-file contents | Previously saved records survive without duplication; new session boundary is explicit |
| V03 | Interrupted session with disposable test data | Last confirmed saved batch versus recovered records | Loss boundary is understood; no claim of crash-proof persistence |
| V04 | Zone/instance/indoor transition | Map ID, position, sample time and transition events | No stale coordinates silently reused; unavailable positions have reasons |
| V05 | Known map points and boundaries | On-screen map and normalized samples | Correct axes/units/map/floor; real zero components not confused with missing data |
| V06 | Accept a quest | Exact `QUEST_ACCEPTED` arguments and resulting log entry | Correct quest ID decoded; one acceptance/run created |
| V07 | Login with active quests and collapsed headers | Enumeration scope and known active IDs | Baselines are not acceptances; omitted rows are not abandoned quests |
| V08 | Advance one objective, then several rapidly | Before/after snapshots, times and locations | Correct counts/flags; merged increments not fabricated as individual kills |
| V09 | Shared credit or credit without local damage | Objective delta and available entity context | Delta recorded without invented killer/causal link |
| V10 | Abandon/reaccept; change objective layout | Removal, new acceptance, objective arrays | Distinct runs/layouts; no cross-run subtraction |
| V11 | Open reward panel, cancel, reopen, turn in | `QUEST_COMPLETE`, `QUEST_FINISHED`, `QUEST_TURNED_IN`, removal | Only actual turn-in produces a turn-in record; ordering handled without assuming one fixed sequence |
| V12 | Repeatable/item-started/automatic/follow-up quest | Offers, acceptances, giver identity if any | No forced NPC or prerequisite relationship; repeat runs remain distinct |
| V13 | Manual loot and auto-loot | Ready/open/slot-change/clear/close timing, slot contents | Contents captured before clearing; repeated notifications deduplicated within session |
| V14 | Reopen corpse; leave items; full bags | Visibility snapshots, slot changes, receipt evidence | No extra kill/drop/receipt inferred from reopening or failed collection |
| V15 | Two sources with area loot | Source tuples, per-source and visible quantities | Mapping verified or left unresolved; no last-target shortcut |
| V16 | Money, currency, container, fishing, skinning | Slot kinds, source kinds, full allowed links | Correct record variants; no automatic monster-drop classification |
| V17 | Uncached/new item or quest | Request, response ID/success, delayed data | Original observation kept; bounded enrichment; no blocking loop |
| V18 | Move an item between bags; receive one from trade/reward | Before/after scoped inventory and receipt events | Moves are not acquisitions; unrelated gains are not monster loot |
| V19 | Change target; lose/reuse a nameplate token | Token/GUID mapping and dead-state readings | Token lifecycle respected; disappearance not treated as death |
| V20 | Inspect direct combat/death capability | Build permissions, registration/call result, permitted payload | Supported capture verified, or explicitly disabled with a reason |
| V21 | Restricted unit/spellcast contexts | Readability decisions, no copied secret values | Collector skips unreadable fields and continues other streams |
| V22 | Learn/view/craft a recipe; interrupt/queue casts | Recipe source, filters, result event and inventory changes | Recipe metadata separated from attempts/results; unavailable recipe association remains unknown |
| V23 | Gather adjacent nodes and skin a looted corpse | Cast/loot interactions and source availability | Separate sessions/source kinds; ambiguous associations retained as candidates |
| V24 | Gossip continuation and vendor update | NPC context, offers, costs, stock and closure | Shown options/offers not treated as selections/purchases |
| V25 | Non-English locale | Quest/item/NPC text and any receipt classification | IDs remain stable; parsing does not rely on English wording |
| V26 | Long session and artificial capacity limit | Memory, handler cost, queue depth, file size/save time | Bounded growth; visible recording state and explicit dropped-data coverage |
| V27 | Export twice; partial/corrupt/oversized import | Export IDs, records, importer decisions | Idempotent accepted data; malformed input rejected without execution |
| V28 | Older/newer saved schema | Migration/rejection result and original data | No silent wipe; recoverable prior data; unknown newer schema preserved |

Repeat relevant permission/readability tests in open world, dungeons/raids if available, and combat/noncombat contexts. Do not extrapolate from one context to all others.

## 4. Record a result

Use this template for each tested capability/scenario. Place future evidence under a build-specific directory, linking sanitized traces and screenshots only where they help establish the result.

```text
Case ID:
Test date:
WF launcher product:
GetBuildInfo outputs:
WOW_PROJECT_ID / locale:
Addon revision / adapter ID:
Matched source revision or extraction checksum:
Context (zone, instance type, combat state, loot/profession mode):
Preconditions and exact player steps:
Expected behavior:
Actual event names and permitted payload shape:
Readability/permission result:
Observed recorder output and SavedVariables result:
Coverage limits / unresolved alternatives:
Result: passed | failed | unavailable | inconclusive
Evidence links:
```

`unavailable` can be a successful product outcome when the collector disables itself cleanly. `inconclusive` must not be relabeled as supported. Log absence alone does not establish absence of an API; rule out bad subscriptions, wrong context, and missing triggers first.

## 5. Promote only the tested capability

To mark a capability `wf_verified`, require the named build, a matched signature or directly measured payload, ordinary-addon permission, meaningful controlled results, relevant failure cases, and saved/exported evidence without restricted values.

Update the domain page, source/evidence register, capability entry, and associated [open question](open-questions.md). Specify contexts still untested. Revalidate after a relevant client patch; keep old results rather than rewriting history.

## Checks completed for the documentation PR

Source files and declarations were inspected; documentation links and JSON fixtures can be checked without a game client. Such checks validate documentation consistency only. They do not satisfy any WF runtime case above.
