# API restrictions and readable data

[Documentation index](../README.md)

**Status:** R reference restrictions; WF contexts unverified. Sources: [R-SECRET](../reference/sources.md#r-secret), [R-COMBAT](../reference/sources.md#r-combat), [R-UNIT](../reference/sources.md#r-unit), [B-COMBAT](../reference/sources.md#b-combat).

## Three different restrictions

| Mechanism | Meaning | ForeverTome response |
| --- | --- | --- |
| Protected action | An action is limited to permitted secure execution/user interaction, often with combat restrictions | Observe supported notifications; do not automate protected gameplay |
| Restricted API/event | A call or registration may be unavailable to an ordinary addon | Disable that capture path and record the capability result |
| Secret value | A value may be usable for approved display while unavailable for addon inspection or computation | Exclude it from recording and export; record only a missing-data reason |

**Taint** tracks execution/data originating outside trusted UI code. Calling a function used by Blizzard does not give ForeverTome Blizzard's privileges. The generated source can contain APIs intended only for secure environments.

Blizzard describes the modern combat changes as limiting computation on combat information while preserving supported presentation. That Retail design is relevant context, not proof of the exact WF rules. [B-COMBAT](../reference/sources.md#b-combat)

## Reading the generated declarations

The source fields below affect how a signature should be interpreted:

| Declaration | Interpretation |
| --- | --- |
| `Namespace` | Prefix required for a namespaced function; global functions lack it |
| `Environment = "SecureOnly"` | Do not present this API as available to ordinary addon code |
| `HasRestrictions = true` | Native permission checks exist; inspect and test their effect |
| `SecretArguments` | Rules for supplying secret inputs; **not** a promise that outputs are readable |
| `SecretWhen...` | Output or payload may be secret under the specified condition |
| `Nilable` / `MayReturnNothing` | Missing data is an expected result to handle |
| `Payload` | Ordered event arguments, not the arguments of `OnEvent` including `self` and event name |

A namespace, table, event name, or flag being present in extracted source is evidence of a declaration. It is not an end-to-end compatibility test.

## Combat is the critical dependency risk

R marks `COMBAT_LOG_EVENT` and `COMBAT_LOG_EVENT_UNFILTERED` as restricted. Its current-event reader is under `C_CombatLogSecure`, whose environment is secure-only. T exposes a differently named reader but also marks restrictions. Consequently, a traditional combat-log death collector is **not an established WF capability**. [R-COMBAT](../reference/sources.md#r-combat), [T-COMBAT](../reference/sources.md#t-combat)

`C_CombatLog.IsCombatLogRestricted()` is a reference status query. A false result by itself is not permission to call secure-only APIs. Do not use a built-in combat-log frame, display text, hooks, saved secret values, or another addon as a path around a restriction.

Without a supported death/credit feed, record readable loot observations, quest deltas, and unit sightings independently. None is a complete replacement for kill attribution.

## Handling possible secret values

R declares `issecretvalue(value)`, `canaccessvalue(value)`, and `canaccesstable(table)`. Unit identity and spellcast data have explicit secrecy-related annotations. The permission helper functions themselves have calling-context rules; verify the supported pattern on WF before adopting it. [R-SECRET](../reference/sources.md#r-secret), [R-UNIT](../reference/sources.md#r-unit)

Proposed recording rules:

1. Check readability before comparisons, string operations, hashing, parsing GUIDs, or indexing with an API value.
2. Reject a secret or inaccessible value at the capture boundary. Do not queue it for later inspection.
3. For permitted tables, copy only known fields and check those fields individually. A table's existence does not prove its contents are readable.
4. Save an ordinary reason such as `restricted`, with the API/capability name where appropriate.
5. If the client cannot support a reliable readability check for a sensitive path, leave that path disabled until validated.

There is deliberately no generic “serialize anything” example. `pcall` contains a Lua error; it does not make secret data readable. Waiting until combat ends does not grant permission to decode values captured earlier.

## Passive collection

ForeverTome's proposed collectors do not need to accept quests, choose rewards, loot items, buy goods, cast spells, or select dialogue options for the player. Those are gameplay actions. Listen to permitted outcomes and read state while the user performs the action.

Blizzard's addon policy requires visible, freely distributed code and restricts behavior that harms gameplay or performance. Consult the original policy for distribution requirements; this handbook is not a substitute for it. [B-POLICY](../reference/sources.md#b-policy)

See [units and combat](../02-api/units-and-combat.md) for what can still be recorded honestly when combat data is unavailable.
