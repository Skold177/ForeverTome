# Events, snapshots, and timing

[Documentation index](../README.md)

**Status:** reference event mechanics; proposed recording strategy. Sources: [R-EVENT](../reference/sources.md#r-event), [R-LIFECYCLE](../reference/sources.md#r-lifecycle).

## An event tells us when to look

An **event** is a named notification sent by the client. Its **payload** is the ordered list of arguments passed with it. Some events report a specific occurrence, such as a quest turn-in. Others only tell the UI that something changed, such as `QUEST_LOG_UPDATE`.

A **snapshot** is a copy of readable state at a particular time. A **delta** is the difference between two comparable snapshots. ForeverTome needs all three concepts: event notifications, snapshots, and derived deltas.

```text
Game notification
  -> build-specific argument decoding
  -> readable, allowlisted fields + observation time/location
  -> small immutable observation
  -> bounded queue / SavedVariables
  -> optional metadata enrichment and later correlation
```

“Raw observation” in this handbook means minimally interpreted **permitted fields**. It never means blindly copying all event arguments, secret values, player chat, or arbitrary API tables.

## Subscribing

The following is an explanatory Lua example using reference lifecycle events, not a runnable ForeverTome addon:

```lua
local frame = CreateFrame("Frame")
frame:RegisterEvent("ADDON_LOADED")
frame:RegisterEvent("PLAYER_ENTERING_WORLD")

frame:SetScript("OnEvent", function(self, event, ...)
    if event == "ADDON_LOADED" then
        local loadedName = ...
        if loadedName ~= "ForeverTome" then
            return
        end
        -- Initialize the restored saved-data structure here.
    elseif event == "PLAYER_ENTERING_WORLD" then
        local isInitialLogin, isReloadingUi = ...
        -- Refresh context and establish a snapshot baseline.
    end
end)
```

The handler receives `self, event, ...`; it does not receive a universal event table. Use exact event strings. Use `RegisterUnitEvent` for supported unit-scoped events when only `player` is relevant, and `UnregisterEvent` when a subscription is no longer needed.

In R, `RegisterEvent` returns a registration boolean. Other branch behavior must be checked; a `pcall` returning successfully only proves the call did not throw. Inspect the result and then observe delivery. `C_EventUtils.IsEventValid` checks whether a name is known, not whether ForeverTome has permission to receive it. Restricted combat events are not part of the default subscription set.

## Capture volatile state immediately

| State | Why timing matters |
| --- | --- |
| Loot slots | Auto-loot and slot removal can erase the item/source information before deferred work runs |
| Quest dialogue | Quest text and the interacting NPC may disappear when the player closes the interaction |
| Unit tokens | `target`, `mouseover`, and nameplate tokens may refer to a different entity later |
| Location | The player can move between a notification and a deferred scan |

Copy only the necessary readable values in the handler. Queue expensive normalization or enrichment afterward. Record both trigger time and later snapshot time if state is sampled later; do not silently present a later position as the event position.

## Coalesce invalidations, preserve occurrences

Several updates can describe one underlying action. Coalesce broad invalidation events into one pending scan of quest, bag, or profession state. Compare the resulting snapshot with the previous valid baseline.

Do not discard repeated loot sessions or quest acceptances solely because their contents match. They may be separate actions. A repeated notification for one loot session is different from looting a second creature with identical contents.

Registration order does not establish the gameplay order of different API systems. Metadata responses may arrive after a quest update or loot closure. Same-second timestamps do not imply that two events were simultaneous or causally related.

## Asynchronous metadata

Item and quest APIs can lack data at the time the event arrives. For example, R declares `C_Item.RequestLoadItemDataByID` with `ITEM_DATA_LOAD_RESULT`, and `C_QuestLog.RequestLoadQuestByID` with `QUEST_DATA_LOAD_RESULT`. Some reads can return nothing. [R-ITEM](../reference/sources.md#r-item), [R-QUEST](../reference/sources.md#r-quest)

The proposed collector should:

1. Save the observation with the known item/quest ID immediately.
2. Deduplicate pending requests by ID and build.
3. On a matching response, check success and read the metadata again.
4. Add an enrichment record referring to the original observation; keep its original time and location.
5. Stop retrying after a bounded policy and retain an explicit unresolved reason.

Do not busy-wait, assume every result belongs to your request, or assume one API response makes all related APIs ready.

## Ordering and time

Use a strictly increasing sequence number within each recording session. Store a wall-clock timestamp for human interpretation and a monotonic elapsed value for short time intervals. R supplies `GetServerTime`, `GetTime`, and `GetTimePreciseSec`; these are distinct clocks and must not be mixed in arithmetic without a defined conversion. [R-TIME](../reference/sources.md#r-time)

An event counter orders **our observations**, not server actions. After reconnect or reload, begin a new session and mark the visibility gap. A later snapshot cannot reconstruct actions that were never observed.

## Handler failures and performance

Isolate collector failures, count them, and keep the rest of recording operational. Error messages should contain the collector name and a bounded diagnostic, not an uncontrolled payload dump. An exception handler does not grant access to restricted data.

Avoid registering every event, scanning all bags on every frame, or saving every combat packet. Measure handler cost, queue depth, pending requests, dropped observations, and saved-data size. Emit explicit coverage gaps when limits stop recording; otherwise downstream users may mistake missing records for absent gameplay.

The [test harness design](../06-testing/harness-design.md) makes these rules reproducible through strict API responses, controlled clocks, and event schedules. [Replay fixtures](../06-testing/fixtures-and-replay.md) must exercise the production handlers and assert their stored output, including adverse ordering and missing data.
