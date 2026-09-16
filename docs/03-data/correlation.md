# Correlating observations without inventing facts

[Documentation index](../README.md)

**Status:** proposed data-analysis rules. This chapter defines what ForeverTome's eventual database may infer, not additional powers of the addon API.

## Preserve evidence before forming relationships

The addon should capture small truthful records. More expensive joins, deduplication across uploads, and guide generation can happen outside the game. Each derived relationship must retain its source observation IDs, algorithm/rule version, and unresolved alternatives.

| Relationship | Stronger evidence | Weaker evidence that must stay labeled |
| --- | --- | --- |
| Creature -> item | Validated explicit loot-source mapping | Last target, nearest sighting, recent death |
| Item -> local receipt | Validated recipient/result record | Slot vanished; bag gained a matching item |
| Action -> quest objective | Explicit supported objective-action identity, if available | Close timing between an action and snapshot delta |
| NPC -> quest offer | Readable interacting NPC plus offered quest in the same interaction | Selected target near a quest dialogue |
| Quest A -> quest B prerequisite | Explicit prerequisite data with verified meaning or controlled repeated tests | B offered after turning in A |
| Creature/node -> position | Supported position of that entity | Player-position samples while nearby |

A time window can select candidates. It cannot manufacture identity, kill credit, loot eligibility, or prerequisite semantics.

## Example: a monster, an objective, and an item

Suppose a player targets a creature, the quest counter advances, and a loot window appears. A recorder can safely say:

1. This entity was sighted at the observer's sampled location.
2. This objective changed between two snapshots.
3. This item was visible in a loot session.
4. An explicit source mapping existed, or the source was unknown.

It cannot automatically collapse all four into “the player killed this monster here, which advanced the quest and dropped this item.” A group member could supply credit; the player could loot another corpse; the actual creature position can differ from the player's position.

The [synthetic example](../examples/README.md) demonstrates retaining the useful records while leaving these relationships unresolved.

## Correlation contexts

**Proposed design:** maintain bounded contexts rather than one global “last action.”

| Context | Key | End/expiry |
| --- | --- | --- |
| Quest run | Session/local run ID plus quest ID | Turn-in, known abandonment, or unknown-end marker |
| Objective layout | Quest run plus layout revision | Layout change or lost baseline |
| Loot interaction | Local loot-session ID | `LOOT_CLOSED`, transition, or recovery timeout |
| NPC interaction | Local interaction ID | Interaction ends/changes, identity changes, or world transition |
| Unit sighting cache | Readable entity ID plus current token association | Token replaced/removed or a short validated timeout |
| Pending metadata | Product/build plus content ID | Success, failure policy, or bounded expiry |

Time windows and capacity limits are configuration/design parameters to determine from tests, not known API constants. Record their versions when they affect derived relationships.

## Deduplication at three levels

1. **Notification duplication:** repeated signals may refresh one snapshot. Deduplicate within the known interaction/layout, not globally by item ID or timestamp.
2. **Observation duplication:** stable observation IDs allow the importer to process the same export repeatedly without inserting duplicate rows.
3. **Gameplay duplication across observers:** multiple players may witness the same event, but the observations are distinct evidence. Merge them into an inferred shared event only with sufficient identity/context.

Two equal loot slots can represent different creatures. Two equal quest snapshots can be repeated reads. A repeatable quest can be accepted twice. A corpse can be reopened. These require domain-specific rules.

If two uploads have the same observation ID but different content, quarantine/report the conflict; do not choose the latest silently. Include record content checksums in the external import/export design if needed, using only permitted exported data.

## State gaps and delayed information

A reload, disconnect, capacity overflow, restricted interval, or unavailable snapshot breaks continuous coverage. Establish a new baseline afterward. Do not subtract an old quest snapshot from a new run or estimate activity during a visibility gap without marking the interval unknown.

An item name arriving later enriches an earlier item observation. It does not move the item acquisition to the later location. Similarly, a quest completion flag seen at login is historical state, not a turn-in observed at login.

## Derived guide quality

Before publishing a guide step, assess whether the evidence supports:

- The right WF build and content IDs.
- The objective/quest run and relevant character eligibility.
- A location with known subject and coordinate system.
- Distinct required steps versus one player's optional route.
- Alternative explanations, recording gaps, and repeat observations.

Keep observed sequences available to reviewers even when a derived guide changes. A confidence label must have a defined rule and supporting evidence; avoid arbitrary percentages that imply measurement precision we do not have.
