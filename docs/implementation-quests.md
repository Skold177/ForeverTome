# Quest recorder contract

`ForeverTome/Quests.lua` uses the installed build's modern quest API profile. Legacy tuples are not guessed. The profile's source evidence does not establish live-server behavior; the in-client validation cases remain required.

## Capture and identity

An observed `QUEST_ACCEPTED` creates a new `quest_run_id`. A quest first found in the log creates `quest.baseline` with `acceptance = not_observed`. Acceptance of a previously seen quest creates another run. Reset, pause, world-transition and storage-gap boundaries discard transient comparisons; resumed quests obtain fresh baseline runs. Ordinary zone/subzone changes preserve active runs, objective comparisons, and pending metadata requests.

`quest.snapshot` contains the quest ID, run ID, title/flags, available log narrative, objective text, objective rows, layout revision, reported readiness and historical completion flag. Log narrative uses the verified `GetQuestLogQuestText(logIndex)` signature without changing the player's selection. Snapshot `complete` describes objective readability, independently of `quest.log_scope.complete`, which describes visible enumeration.

Log notifications coalesce for 0.35 seconds. Deferred records preserve trigger and sample times; their location is the observer's position when sampled. Identical snapshots are suppressed. Known quests hidden behind collapsed headers receive a direct refresh only when `C_QuestLog.IsOnQuest` reports true. Missing rows never cause removal or abandonment records.

## Progress semantics

An objective delta requires complete snapshots from the same run with matching row order, type, optional objective type, required quantity and description template. The description comparison normalizes the numerator of textual `current/required` counters; observations retain the original counters with player-name substitution applied. Changed layouts, unreadable objectives, uncertain presence and reset boundaries require a new baseline. Increases and decreases both survive. A delta is an interval observation and does not identify individual kills or credit sources.

`quest.ready` records reported readiness changes, including false. `QUEST_COMPLETE` records the reward dialogue only. `quest.turned_in` requires the explicit turn-in event. `quest.removed` always retains `reason = unknown`; turn-in and removal observations can link to each other when delivered within 30 seconds. `QUEST_FINISHED` closes dialogue context without claiming completion.

## Dialogue and enrichment

`quest.dialogue` immediately captures readable offer, progress or reward text, NPC context, and offered rewards, choices or required items. The interacting NPC is sampled through `npc`; missing NPC identity stays unknown. Reward choices do not identify the chosen reward or prove receipt. The item collector receives linked metadata requests for observed items.

Quest narratives, titles, objective rows, gossip, and greetings replace the current player's exact name and known name-realm forms with `adventurer` before entering the recording or comparison caches. Identity is read through the existing guarded `UnitName("player")` call and is never added to SavedVariables, session headers, or exports. Matching is literal and case sensitive, recognizes word boundaries and game color codes, and preserves names embedded in longer words. NPC identity fields and numeric quest/objective data keep their existing meanings. If the player's name is unavailable or restricted, potentially personalized text is omitted and a bounded `privacy:player_name_unavailable` diagnostic explains the omission. Previously saved observations are unchanged and still need separate sanitization when published.

Acceptance links the latest matching offer through `related_observation_ids` and its `interaction_id`, labeled `dialogue_context = recent_dialogue`. One active dialogue survives closure for up to two seconds, is consumed by the next valid acceptance or a matching quest turn-in, and is replaced by new dialogue, gossip, or greeting activity. Unrelated turn-ins preserve a pending offer. Quest ID and dialogue phase must match; a conflicting live NPC blocks the link. Reset boundaries clear it. Reading an open dialogue for longer than two seconds does not expire the context.

Each active quest run also retains its latest successful `QUEST_COMPLETE` snapshot. A turn-in can link that reward dialogue after a long closed-panel interval or unrelated interactions, labeled `dialogue_context = quest_run_reward_dialogue`. The cache belongs to the exact quest run; a replacement acceptance or reset discards it. Removal-before-turn-in ordering retains it with the closed run for 30 seconds. A conflicting live NPC still prevents carrying that dialogue context into the turn-in. This fixes the observed 43-second reward-dialogue-to-turn-in case without extending the acceptance closure window.

The event's `npc` remains a contemporaneous sample. If it is unavailable, `dialogue_npc` can retain the linked dialogue's historical NPC snapshot, while `missing_fields.npc = unknown_source` remains explicit. This is observed offer/reward context, not proof of the acceptance source: canceling an offer and accepting a shared, item-started, or automatic quest can be indistinguishable within the short closure window. Consumers must preserve that distinction rather than promote `dialogue_npc` to a confirmed questgiver.

`interaction.snapshot` records gossip text, available and active quests, and permitted option fields. Quest greetings use the source-verified greeting getters and record their available/active quest IDs. No dialogue option, reward, quest or log selection is changed by the collector.

Missing titles/objectives can request quest metadata. `quest.metadata` appends a linked title observation; it never edits an earlier record. `quest.metadata_unavailable` records a timeout. Unrelated and already-resolved callbacks are ignored.

## Received reward items

`QUEST_LOOT_RECEIVED(questID, itemLink, quantity)` directly emits `quest.reward_received`, with the event's quest ID, item ID/link, quantity, local recipient, and `source_status = quest_event`. Its evidence method is `direct_event`. This remains separate from reward options displayed in dialogue and from generic `CHAT_MSG_LOOT` receipts. No time-based matching or reward-choice click is treated as proof of receipt.

When available, the record includes the observed run ID and links to its turn-in and reward dialogue. Closed-run context lasts 30 seconds; the observed 11-second item delivery delay fits within that window. Reaccepting the same quest within a prior turn-in's context window leaves the reward run unknown to avoid attaching a delayed receipt to the new run. Expired, missing, or reset context does not discard the native receipt: its explicit quest ID remains valid and `missing_fields.quest_run_id = not_observed` labels the unavailable run.

Native reward receipts, chat receipts, and inventory changes can describe the same items. Consumers must not sum these observation streams as independent acquisitions. Prior saved chat receipts are not retroactively assigned to quests. The source confirms the native event contract; delivery for ordinary Forever quests still needs an in-game retest.

## Bounds and failure behavior

The transient cache permits 256 quests, with at most one reward-dialogue context per run; enumeration permits 512 log rows, and each quest permits 64 objective rows. Dialogue reward categories permit 64 entries and gossip/greeting arrays permit 256 entries. Truncated or unreadable snapshots retain missing-field reasons and cannot form complete progress baselines.

At most 32 quest metadata requests are pending, each with eight reference IDs and two request attempts separated by ten seconds. A timeout ends that request. Cache saturation emits a bounded quest coverage-gap observation. The shared store additionally enforces record, byte, string, scheduled-task and diagnostic limits.

The replay suite in `tests/quests.lua` checks baseline meaning, argument decoding, repeated runs, objective counters, decreases, changed layouts, missing reads, collapsed headers, reward-panel cancellation, explicit turn-in, reset boundaries and metadata immutability. It runs against the production addon bootstrap and rejects swallowed collector exceptions. Mock results do not establish native client permissions or server semantics.
