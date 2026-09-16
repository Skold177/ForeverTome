# Client compatibility and evidence

[Documentation index](../README.md)

**Status:** reference research; WF runtime unverified. **Reviewed:** 2026-09-16.

## Why the client matters

The game client determines the addon API. Similar content, a familiar user interface, or a Classic product name does not establish which functions exist, which events an addon can register, or which returned values it can inspect.

Blizzard's WF announcement establishes the product context and announces beta access beginning September 17. It does not provide the API contract used in this handbook. We therefore use source snapshots as explicitly labeled references until the actual WF client can be identified and tested. [B-WF](../reference/sources.md#b-wf)

## Inspected reference builds

| Reference | Mirror branch | Version from `version.txt` | Immutable commit | What it establishes |
| --- | --- | --- | --- | --- |
| R | `live` | `12.1.0.69814` | `4e3cbb8c5609e4bfc332c0aebbfa4d79731fab59` | Current Retail reference declarations and UI call sites |
| T | `classic_titan` | `3.80.2.69815` | `1303c9bdbb7f320fa45db1eaee73acaae3b71fe8` | A contrasting client source snapshot; its mapping to WF is **unconfirmed** |
| WF | Unknown | Not measured | No matched source revision | No runtime conclusions yet |

Both inspected commits are dated 2026-09-12. The mirror is not Blizzard's official GitHub repository; the files contain Blizzard-authored client UI code and generated API declarations. Source inspection cannot reproduce native engine permission checks. [R-BUILD](../reference/sources.md#r-build), [T-BUILD](../reference/sources.md#t-build)

## Differences that affect ForeverTome

| Topic | R reference | T reference | Implementation implication |
| --- | --- | --- | --- |
| `QUEST_ACCEPTED` | `questId` | `questIndex, questId` | Decode through an explicit build adapter; never assume argument 1 is always a quest ID |
| `LOOT_OPENED` | `autoLoot, isFromItem` | `autoLoot` | An absent argument is unknown, not a false observation |
| Combat-log reader | `C_CombatLogSecure.GetCurrentEventInfo`, secure-only environment | `C_CombatLog.GetCurrentEventInfo`, marked restricted | Neither declaration proves ordinary-addon access |
| Profession API | Extensive `C_TradeSkillUI` recipe and crafting functions | Much smaller namespace plus legacy UI call sites | Do not transplant Retail crafting recipes into a Classic-style collector |

Sources: [R-QUEST](../reference/sources.md#r-quest), [T-QUEST](../reference/sources.md#t-quest), [R-LOOT](../reference/sources.md#r-loot), [T-LOOT](../reference/sources.md#t-loot), [R-COMBAT](../reference/sources.md#r-combat), [T-COMBAT](../reference/sources.md#t-combat), [R-PROFESSION](../reference/sources.md#r-profession), [T-PROFESSION](../reference/sources.md#t-profession).

## Capture the real client identity

On the WF client, record the product selected in the launcher and these non-sensitive diagnostics:

```lua
/dump GetBuildInfo()
/dump WOW_PROJECT_ID
/dump GetLocale()
```

The R declaration returns `buildVersion, buildNumber, buildDate, interfaceVersion, localizedVersion, buildInfo`. The first four are the essential compatibility identifiers; record all available outputs. The build number and version are strings in this declaration. `WOW_PROJECT_ID` is supporting context, not a substitute for the full build. Do not invent a WF project constant or hardcode a guessed TOC interface number. [R-BUILD](../reference/sources.md#r-build)

Record the addon version, schema version, adapter identifier, and client identity together. A session spanning a UI reload gets a new session identifier; a patch requires a fresh capability check.

## Evidence states

| State | Required evidence | Permitted claim |
| --- | --- | --- |
| `reference` | Pinned source declaration or actual call site | “This reference build declares/uses this API.” |
| `historical_candidate` | Dated original implementation or direct observation | “This was observed before; inspect and test it again.” |
| `wf_verified` | Named WF build, ordinary-addon test, scenario, payload, result | “It worked on this build in these tested contexts.” |
| `wf_unverified` | No qualifying WF test | “Candidate capability; do not promise it.” |
| `unavailable` | Absence or permission failure reproduced on a named build | “This capture path is unavailable in this context.” |

**Proposed design** is a separate label: it describes what ForeverTome should do, regardless of whether a candidate API passes validation.

## Capability checks are layered

1. Confirm the function or namespace exists.
2. Confirm the event is known, if `C_EventUtils.IsEventValid` is available.
3. Confirm an ordinary addon may register/call it.
4. Confirm the returned values are readable in the tested context.
5. Confirm their meaning with a controlled gameplay action.

A function existing does not establish its signature. An event being valid does not establish permission. A successful registration does not establish delivery. A successful call does not establish non-secret output. [R-EVENT](../reference/sources.md#r-event), [R-SECRET](../reference/sources.md#r-secret)

The [test plan](../04-validation/wf-test-plan.md) specifies the evidence needed to graduate a capability to `wf_verified`.
