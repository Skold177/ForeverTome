# Quest recorder contract

`ForeverTome/Quests.lua` uses the installed build's modern quest API profile. Legacy tuples are not guessed. The profile's source evidence does not establish live-server behavior; the in-client validation cases remain required.

## Capture and identity

An observed `QUEST_ACCEPTED` creates a new `quest_run_id`. A quest first found in the log creates `quest.baseline` with `acceptance = not_observed`. Acceptance of a previously seen quest creates another run. Reset, pause, world-transition and storage-gap boundaries discard transient comparisons; resumed quests obtain fresh baseline runs.

`quest.snapshot` contains the quest ID, run ID, title/flags, available log narrative, objective text, objective rows, layout revision, reported readiness and historical completion flag. Log narrative uses the verified `GetQuestLogQuestText(logIndex)` signature without changing the player's selection. Snapshot `complete` describes objective readability, independently of `quest.log_scope.complete`, which describes visible enumeration.

Log notifications coalesce for 0.35 seconds. Deferred records preserve trigger and sample times; their location is the observer's position when sampled. Identical snapshots are suppressed. Known quests hidden behind collapsed headers receive a direct refresh only when `C_QuestLog.IsOnQuest` reports true. Missing rows never cause removal or abandonment records.

## Progress semantics

An objective delta requires complete snapshots from the same run with matching row order, type, optional objective type, required quantity and description template. The description comparison normalizes the numerator of textual `current/required` counters; the original text remains unchanged in observations. Changed layouts, unreadable objectives, uncertain presence and reset boundaries require a new baseline. Increases and decreases both survive. A delta is an interval observation and does not identify individual kills or credit sources.

`quest.ready` records reported readiness changes, including false. `QUEST_COMPLETE` records the reward dialogue only. `quest.turned_in` requires the explicit turn-in event. `quest.removed` always retains `reason = unknown`; turn-in and removal observations can link to each other when delivered within 30 seconds. `QUEST_FINISHED` closes dialogue context without claiming completion.

## Dialogue and enrichment

`quest.dialogue` immediately captures readable offer, progress or reward text, NPC context, and offered rewards, choices or required items. The interacting NPC is sampled through `npc`; missing NPC identity stays unknown. Reward choices do not identify the chosen reward or prove receipt. The item collector receives linked metadata requests for observed items.

`interaction.snapshot` records gossip text, available and active quests, and permitted option fields. Quest greetings use the source-verified greeting getters and record their available/active quest IDs. No dialogue option, reward, quest or log selection is changed by the collector.

Missing titles/objectives can request quest metadata. `quest.metadata` appends a linked title observation; it never edits an earlier record. `quest.metadata_unavailable` records a timeout. Unrelated and already-resolved callbacks are ignored.

## Bounds and failure behavior

The transient cache permits 256 quests, enumeration permits 512 log rows, and each quest permits 64 objective rows. Dialogue reward categories permit 64 entries and gossip/greeting arrays permit 256 entries. Truncated or unreadable snapshots retain missing-field reasons and cannot form complete progress baselines.

At most 32 quest metadata requests are pending, each with eight reference IDs and two request attempts separated by ten seconds. A timeout ends that request. Cache saturation emits a bounded quest coverage-gap observation. The shared store additionally enforces record, byte, string, scheduled-task and diagnostic limits.

The replay suite in `tests/quests.lua` checks baseline meaning, argument decoding, repeated runs, objective counters, decreases, changed layouts, missing reads, collapsed headers, reward-panel cancellation, explicit turn-in, reset boundaries and metadata immutability. It runs against the production addon bootstrap and rejects swallowed collector exceptions. Mock results do not establish native client permissions or server semantics.
