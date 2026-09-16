# Recording creatures, sightings, and combat outcomes

[Documentation index](../README.md) · [Restrictions](../01-foundations/restrictions.md)

**Status:** R/T source reference; WF combat access unverified. Sources: [R-UNIT](../reference/sources.md#r-unit), [R-COMBAT](../reference/sources.md#r-combat), [T-COMBAT](../reference/sources.md#t-combat).

## Identity starts with a temporary unit token

A unit token such as `player`, `target`, `mouseover`, or `nameplate1` is a handle to a currently addressable entity. It is not a permanent identifier. A token can disappear or be reused as the player changes target or units leave view.

R declares `UnitGUID(unit)` returning a nullable GUID and `UnitName(unit)` returning name/server text. Both have identity-related secrecy annotations. Other useful candidates include `UnitLevel`, `UnitClassification`, `UnitCreatureType`, `UnitIsDead`, and `UnitIsDeadOrGhost`. Check readability per field and do not interpret an unknown level or unavailable GUID as a normal content value.

Capture identity immediately during `PLAYER_TARGET_CHANGED`, `UPDATE_MOUSEOVER_UNIT`, or a validated nameplate event. Clear the cached token association when it is removed or replaced. A nameplate removal means the token stopped being available; it does not mean the creature died.

## Entity instance versus creature type

| Identifier | Meaning | Persistence rule |
| --- | --- | --- |
| Unit token | Temporary access path | Context only; never the database content key |
| GUID | Entity identity as exposed by the client | Preserve only when readable and permitted; validate entity kind |
| Creature/NPC template ID | Content identity shared by multiple instances, if reliably obtainable | Scope to product/build; do not confuse with the full GUID |
| Name | Localized label | Preserve with locale; never use as the sole key |

Some WoW GUID formats encode entity kind and a creature template ID. This research does not establish the WF format. Any parser must be build-specific, validate the kind/shape before extracting fields, and retain `parse_status = unsupported` when unknown. Do not apply a creature parser to player, pet, vehicle, game-object, or item identities indiscriminately.

Names can repeat, change with locale, or be unavailable. New WF content must not be assigned a known Classic creature ID by name matching.

## A sighting is useful without a kill

**Proposed sighting record:** readable entity identity, observed name/type/level, the API/token used, observation time, observer location, and any unavailable-field reasons. This contributes habitat samples, quest-giver sightings, or vendor locations.

The sample establishes where the **player** was when the entity was observed. It is not an exact spawn coordinate. Many observations can support a later estimate, but that estimate must stay separate from the original samples.

## Death, kill credit, and quest credit differ

| Evidence | Valid statement | Invalid leap |
| --- | --- | --- |
| Readable dead-state sighting | “This unit was observed dead.” | “It died at this instant.” |
| Validated death notification | “A death was reported for this entity.” | “Our player killed it.” |
| Validated kill-credit notification | “This actor/group received the reported credit.” | “This player dealt the final blow and received all loot.” |
| Quest counter increased | “This objective advanced between snapshots.” | “The last selected creature caused the increase.” |
| Loot from a creature source | “This item was exposed by that source.” | “Our player killed it here.” |

Group members, pets, shared credit, and out-of-range activity make these distinctions necessary.

## Historical combat-log approach

Traditional collectors subscribed to `COMBAT_LOG_EVENT_UNFILTERED` and read the current combat-log tuple. That tuple commonly carried a timestamp, subevent, source/destination GUIDs and flags, followed by subevent-specific fields. The built-in T combat-log UI handles `UNIT_DIED`, `PARTY_KILL`, and other subevents.

`UNIT_DIED` is a combat-log subevent, not a separate frame event. A death subevent does not inherently supply a killer; a preceding damage event can be incomplete or misleading. `PARTY_KILL` is a distinct credit-related signal whose semantics would need testing.

T contains a compatibility alias from `CombatLogGetCurrentEventInfo` to `C_CombatLog.GetCurrentEventInfo`. **That alias does not establish WF support.** The T reader and events carry restrictions. R uses a secure-only reader under `C_CombatLogSecure` and also marks combat-log events restricted.

Therefore the initial ForeverTome design must not require an unrestricted combat-log feed. Do not register it as an assumed baseline, copy an old tuple parser into production, or advertise complete kill tracking before ordinary-addon WF validation succeeds.

## Behavior when combat capture is unavailable

Keep the supported observation streams operating independently:

- Readable unit sightings remain sightings.
- Quest updates remain quest updates.
- Loot observations retain explicit source mappings when available.
- A readable dead-state observation remains a dead-state observation.
- Capability metadata records that direct death/credit capture was unavailable.

Do not synthesize a `kill` record from these fallbacks. A future external inference can link evidence with a named rule and uncertainty, but the underlying records must remain truthful.

## Validation cases

Test open-world and instanced contexts separately, alive/dead targets, two identical creatures, target changes, nameplate removal without death, player/pet/group kills, a corpse killed by someone else, and secret identity/spellcast values. Record permission failures and stop using that path; testing is not a search for a bypass.
