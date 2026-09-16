# Open WF API questions

[Documentation index](../README.md)

**As of 2026-09-16:** all questions below are open. They are deliberate boundaries on what the documentation promises, not reasons to discard the reference research.

| ID | Question | Why it matters | Evidence that closes it |
| --- | --- | --- | --- |
| WF-001 | What is the actual WF client version/build/interface/project identity and product directory? | Determines manifest, source extraction, installation and saved-file path | V01 identity output plus observed installation and generated file |
| WF-002 | Does the inspected `classic_titan` branch correspond to WF, another product, or an incomplete comparison source? | Prevents declaring an unrelated branch to be the target contract | Exact build/source mapping supported by client identity and extraction provenance |
| WF-003 | Are third-party addons enabled, and what ordinary-addon restrictions apply? | A source file existing does not prove addons may use it | Minimal addon load plus per-capability registration/call tests |
| WF-004 | What are the quest event payloads and complete-enumeration APIs? | Wrong `QUEST_ACCEPTED` decoding corrupts quest identity; filtered scans can miss quests | V06–V12 traces, collapsed-header tests and actual source |
| WF-005 | Can ordinary addons receive a supported death or kill-credit feed? | Determines whether direct kill recording is possible | V20 tests of the actual permitted interface; denied/secure-only paths count as unavailable |
| WF-006 | Which identity, location, and spellcast values are secret, and in what contexts? | Prevents invalid serialization and false coverage assumptions | V04/V19/V21 with readable-field results per tested context |
| WF-007 | Does WF expose `GetLootSourceInfo` or a supported replacement, and what exactly does it return? | Determines whether item-to-creature attribution can be direct | V13–V16 one-source/multi-source tuples, quantity checks, permission/readability results |
| WF-008 | Which receipt signals identify the local player reliably in each loot mode? | Visible slots and slot clearing do not prove receipt | V14/V16/V18 across solo/group, full-bag and non-loot acquisition cases |
| WF-009 | What are the WF profession, recipe, gathering, and new-system APIs? | Retail crafting assumptions may be wrong | V22–V24 with source-backed signatures and context-specific outputs |
| WF-010 | Are map coordinates available in all intended areas, floors, and transitions? | Missing/stale coordinates can create false guide markers | V04/V05 in outdoor, indoor, transport and instance contexts |
| WF-011 | Are GUID shapes and content-ID namespaces stable enough for parsing and cross-build aggregation? | Avoids merging different entities or products | Sanitized non-player samples, documented parser checks and cross-build comparisons |
| WF-012 | What are WF's save/reload failure boundaries and practical data-size limits? | Defines durable recording claims and capacity defaults | V02/V03/V26 plus measured file sizes and timings |
| WF-013 | Which automatic, repeatable, shared, account-related, or staged quests change ordinary lifecycle semantics? | Prevents false abandonment, completion or prerequisite conclusions | V07–V12 cases with named quest IDs and context |
| WF-014 | What retention defaults, export format, and external import workflow should ship? | These are product choices, not API facts | Measured prototype behavior and an explicit follow-up design decision |
| WF-015 | Which installed archive/table formats and schemas can external tools read correctly? | Determines immediate catalog acquisition before login | Hashed client inventory, matched build/layout definitions, representative decoding and structural validation; see the [acquisition checklist](../05-acquisition/launch-checklist.md) |
| WF-016 | Which packaged abilities, talent systems, maps, items, and new systems are actually enabled in WF? | A definition can be shared, unused, hidden, or future content | Catalog provenance plus named runtime/gameplay contexts; preserve unobserved availability instead of claiming global support |

## Work that can proceed before these are closed

The reference vocabulary, evidence model, import boundary, missing-data semantics, and domain capture responsibilities can guide implementation now. Build-specific payload decoders and capability promises must wait for their corresponding evidence.

The first implementation should resolve WF-001 through WF-004 and persistence basics before expanding collectors. Investigate WF-005 and WF-007 early because they determine how directly we can answer “what did this monster drop?” and “did this player kill it?”

## Updating an answer

Attach a test result using the [validation template](wf-test-plan.md), state the exact build and tested contexts, and update the related API chapter. Preserve a partial answer as partial. A new patch can reopen a question; prior verified results remain valid only for their recorded scope.
