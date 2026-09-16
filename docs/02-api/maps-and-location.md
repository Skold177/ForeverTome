# Recording maps and locations

[Documentation index](../README.md)

**Status:** R reference APIs; WF availability, coordinate behavior, and coverage unverified. Sources: [R-MAP](../reference/sources.md#r-map), [R-UNIT](../reference/sources.md#r-unit).

## Always say whose position was measured

The player position at a loot or quest event is an **observer location**. It can be near the relevant creature, NPC, node, or objective, but does not establish its exact position. R explicitly limits `C_Map.GetBestMapForUnit` and `C_Map.GetPlayerMapPosition` to the player and party members; these are not arbitrary NPC-position queries.

Store `subject = player` and `method = C_Map.GetPlayerMapPosition` with the sample. If a future supported API supplies an actual entity position, use a separate subject and method instead of silently replacing the observer position.

## Reference APIs

| R function | Declared result | Important limitation |
| --- | --- | --- |
| `C_Map.GetBestMapForUnit(unitToken)` | Nullable `uiMapID` | Player/party scope; no map is a valid missing-data outcome |
| `C_Map.GetPlayerMapPosition(uiMapID, unitToken)` | Nullable `Vector2DMixin` position | Requires a map ID; location can be unavailable |
| `C_Map.GetMapInfo(uiMapID)` | `UiMapDetails`, or no result | Contains map ID/name/type/parent/flags, not entity coordinates |
| `C_Map.GetWorldPosFromMapPos(uiMapID, mapPosition)` | `continentID, worldPosition`, or no result | A coordinate conversion; does not locate a creature |
| `UnitPosition(unit)` | `positionX, positionY, positionZ, mapID` | Declaration alone does not establish arbitrary-unit or instance coverage |
| `GetInstanceInfo()` | Instance name/type/difficulty and other fields | Instance identity and UI map identity are different concepts |

The R `GetInstanceInfo` sequence is `name, instanceType, difficultyID, difficultyName, maxPlayers, dynamicDifficulty, isDynamic, instanceID, instanceGroupSize, lfgDungeonID, hasWorldTier`. Keep only validated fields needed by the recorder; never treat `instanceID` as a unique copy of an instance or as a UI map ID without explicit evidence.

## Coordinate conventions

The established `C_Map` player-position convention is a normalized map pair: display `x * 100`, `y * 100` as map percentages while storing the original fractions. Verify orientation, bounds, floors, and transitions on WF before using that convention in exported coordinates.

Store a coordinate-system label such as `ui_map_normalized`, the map ID, and the subject. `(0.45, 0.62)` without those fields is not a complete location.

Keep native `UnitPosition` coordinates and converted world positions in separately labeled fields with their returned map/continent identity. Do not multiply native coordinates by 100, swap axes by analogy, or calculate cross-map distances without a validated transform.

Map names, zone names, and subzone names are readable labels, not stable IDs. The R map structure provides `name` and `parentMapID`. Zone-text getters, if used, must be validated on WF and saved with locale.

## Proposed sampling procedure

1. Record the observation's time immediately.
2. Read the best player map using the validated adapter.
3. Read the player position for that map and validate readability before extraction.
4. Copy scalar coordinates, map identity, context, method, and sample time.
5. If the map/context changes during capture, retain an unavailable/transition result or resample with a later timestamp.

Do not save a `Vector2DMixin` object itself. Copy its permitted numeric coordinates into plain data. A reference extraction uses `position:GetXY()`, but must not be called on an inaccessible object.

Refresh map labels on `PLAYER_ENTERING_WORLD` and zone-change notifications. Read the current position for important observations rather than reusing a minutes-old zone sample. If sampling is deferred, record the delay and sampling time explicitly.

## Missing and ambiguous locations

| Situation | Representation |
| --- | --- |
| No best map | Location unavailable, `reason = no_map` |
| Position not returned | Retain known map context, `reason = no_position` |
| Restricted value | Exclude the value, `reason = restricted` |
| Loading screen or transition | Invalidate previous context, `reason = transition` |
| Stale last-known sample | Keep separately with its original time and `stale = true` |
| Suspected invalid coordinates | Preserve a validation reason; do not coerce to a plausible location |

Never use `(0, 0)` to mean unknown. Conversely, do not automatically discard every zero component: a map boundary can be a real coordinate. Determine any API sentinel behavior experimentally.

Dungeon floors, interiors, transports, phasing, and instance transitions need explicit tests. Two players at the same map pair can see different world state. Preserve observed context without inventing an unavailable shard or phase identifier.

## What the database may infer later

Repeated observer samples can suggest a quest area, creature habitat, or approximate node location. Keep sample count, spread, build, and method with that estimate. Do not present a single player-position sample as a precise spawn marker or derive a respawn timer from one interval between sightings.
