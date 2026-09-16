# Fixtures, replay, and expected results

[Testing strategy](README.md)

**Status: proposed fixture protocol.** The existing [worked example](../examples/README.md) is illustrative output, not a sufficient event-input trace or executable test fixture.

## A fixture is a reproducible scenario

Each fixture must contain or reference:

| Component | Required content |
| --- | --- |
| Identity | Stable scenario ID, fixture format version, title and protected invariant IDs |
| Provenance | Synthetic or captured; product and source revision/build; locale; ordinary-addon context; sanitization history |
| Profile | Exact adapter/API profile and its capability assumptions |
| Initial state | Saved-data schema/generation, active session state, known caches/baselines, configuration and limits |
| Inputs | Ordered events, API argument/return plans, object identities and permitted state changes |
| Time | Wall/elapsed clocks, explicit scheduler steps, seed if any |
| Checkpoints | What must hold after capture, queue work, commit, export and restore |
| Expected results | Observations, diagnostics, storage state, permitted pending work and forbidden side effects |

Input fixtures, expected output, and assertions have different roles. Expected output should be derived from the written behavior contract and inspected independently of the recorder that will be tested.

## Fixture kinds and profiles

**Synthetic fixtures** exercise project rules before WF exists: table aliasing, nil values, duplicate notifications, races, invalid input, and persistence failures. Reference R/T payload differences can be tested as explicitly named reference profiles. They are not automatically supported WF adapters.

**Captured fixtures** come from a named product/build and a controlled scenario. Retail captures can exercise the shared recorder before WF is available; retain their Retail profile and do not relabel them as WF evidence. Capture only permitted allowlisted data. Remove personal identifiers through a documented mapping that preserves identity equality, collisions, and relationships relevant to the bug. Never retain secret values or private chat to make a fixture realistic.

A captured event list alone may be insufficient: APIs read later can return different state. Preserve the relevant readable API results and their order/timing, or add clearly labeled synthetic supplementation. A supplemented fixture is mixed evidence, not a perfect original trace.

An absent capture is an unmet runtime-validation requirement, not a reason to invent WF output. CI can still run synthetic coverage without claiming compatibility.

## Trace operations

Use a small declarative language interpreted by the harness. Its proposed operations are:

| Operation | Purpose |
| --- | --- |
| `set_clock` | Initialize or deliberately alter the specified clock |
| `define_object` | Create a named plain table in the fixture arena |
| `mutate_object` | Change a fixture-owned table, including nested values, without automatically copying it |
| `expect_api_call` | Provide an expected call/return plan; use object references to test aliasing |
| `emit_event` | Deliver a named event with an exact argument tuple |
| `run_due` | Execute scheduled work in the recorded stable order |
| `checkpoint` | Assert outputs, historical prefix, pending work and diagnostics |
| `snapshot_saved` | Capture a simulated client save from the real SavedVariables model |
| `restart` | Start a fresh environment using only an identified saved snapshot |
| `export` / `import` | Exercise actual implemented serialization/import boundaries |
| `inject_failure` | Fail a specified boundary exactly once or under an explicit rule |

Do not permit arbitrary scripts in uploaded/captured trace data. Repository-authored tests may be executable Lua, but external fixtures should remain constrained data.

### Preserve tuple arity and nil

Lua argument/return tuples need an explicit count. A proposed fixture encoding is:

```json
{
  "arity": 3,
  "values": [
    {"type": "number", "value": 990001},
    {"type": "nil"},
    {"type": "boolean", "value": false}
  ]
}
```

The fixture decoder must materialize all three positions. Do not rely on Lua's length operator or ordinary array iteration to infer a sparse tuple's length. Object references use an explicit tagged object ID; they must resolve to the same table until the trace specifies a new object.

Fixture nil markers and the export format's JSON null representation are separate concerns. Tests must cover absent keys, nil tuple positions, false, zero, empty strings, empty arrays and empty objects without collapsing them.

## Worked regression: a reused objective table

The numbers and identities below are synthetic. The first implementation should turn this specification into a fixture with full expected records.

| Step | Input/action | Required assertion |
| --- | --- | --- |
| 1 | Initialize a known quest run; define objective table A with progress 0/2 | No acceptance is invented for the preexisting run |
| 2 | Deliver a quest-log update; the scheduled reader receives table A | One baseline snapshot records 0/2 with actual sampling time/location |
| 3 | Let the recorder accept the snapshot; pause before any optional deferred commit stage | The accepted data has no mutable reference to A |
| 4 | Mutate A's nested progress to 1 and its text; move the observer | The accepted snapshot still has its original count, text and position |
| 5 | Complete pending commit work | The stored snapshot matches the accepted value, not current API state |
| 6 | Deliver another update returning that same A object | A second snapshot can observe 1/2 and its new sample context |
| 7 | Compare the snapshots under the declared layout policy | If only count changed, a +1 delta is valid; a changed layout requires a new baseline instead |
| 8 | Export; mutate a consumer's returned copy; simulate save/restart | Earlier records remain structurally equal and the exporter has not changed their order |

Split step 7 into two fixtures: one with only a progress change, and one with a semantic objective-layout change. Expected output must not depend on whatever heuristic the current implementation happens to use.

## Golden results and independent assertions

A **golden result** is a reviewed expected output committed alongside a fixture. For deterministic seeded identity and clocks, compare the complete semantic record: keys, values/types, sequence, references, time, location, missing reasons, and evidence. Also assert exact record counts and forbidden record kinds.

Canonicalize object-key ordering only; preserve array order, objective/effect order, duplicates, null/missing distinctions, string content and numeric meaning. Avoid blanket timestamp removal, rounded coordinates, sorted observation lists, or ignored metadata fields that could conceal a regression. No floating-point tolerance is allowed unless a particular field's contract defines one and has a boundary test.

Use an independent structural comparator on recorder-owned/exported data, not merely a hash made by the serializer under test. Round-trip success alone is insufficient: a broken writer and reader can agree on the same lost field. Combine hand-authored expected records, old saved-version fixtures, structural assertions, and independently parsed serialized output.

Expected files must never be automatically rewritten during CI. A local “regenerate expected output” aid, if later added, produces a candidate diff; it does not bless that diff as correct.

## Generated and transformed scenarios

Add fixed-seed generators for bounded event bursts, nil fields, unsupported values, metadata reorderings and storage failures. Report the seed and retain a minimized failing trace.

Useful transformations have explicit permitted differences:

- Duplicate an invalidation notification: the final comparable state remains the same; diagnostics or sampling timestamps may differ only as specified.
- Duplicate a metadata completion: no second identical enrichment/receipt is invented under the chosen request policy.
- Reorder independent ready metadata responses: the final metadata mapping can agree even when append order/sequence differs. Compare the mapping for this property, not an incorrectly assumed identical event history.
- Add a world transition: stale location/interaction associations must disappear; historical records remain unchanged.
- Export twice without new input: the exported semantic content and stored prefix remain equal.

Never randomly permute causally ordered steps such as acceptance and turn-in and then demand the same history. Test alternate orderings only when the contract permits them; other permutations are malformed-input tests with explicit rejection/recovery expectations.

## Failure reports

A failed replay reports fixture ID/hash, profile, addon revision, schema version, interpreter/dependency versions, seed, trace step/time, API call context, and the smallest meaningful expected/actual diff. Include previous checkpoint state and safe diagnostics. Do not stringify modeled restricted values to construct an error message.

When a real bug appears: sanitize it, reduce it while preserving the failure, write the expected outcome from the contract, demonstrate failure on the old implementation, then fix the code. The minimized fixture becomes a permanent regression rather than a one-time debugging artifact.
