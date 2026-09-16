# Maintaining the documentation

[Documentation index](../README.md)

## Documentation contract

This handbook is the first contribution to ForeverTome. Its job is to make addon behavior and recording limits understandable, traceable, and ready for implementation. It is not a generated dump of all WoW APIs or a claim of completed WF compatibility.

Keep one topic per page, short descriptive headings, a link back to the index, exact API spelling, and local relative links. Prefer explanations of meaning and failure cases to unexplained symbol lists. Add glossary entries when introducing terms.

## Evidence rules

- Label source reference, historical candidate, WF runtime verification, and proposed design distinctly.
- Record the research/test date, client build, source revision, and tested contexts.
- Use immutable links to Blizzard-authored declarations and actual UI call sites where available.
- Do not promote a forum user's statement to a Blizzard guarantee because the forum is on Blizzard's domain.
- A product announcement is not an API contract. A function's existence is not permission or a correct signature.
- Document missing data, restricted fields, and unsupported branches as deliberately as successful paths.

## Adding or changing an API entry

1. Find the exact declaration in the matched source. Read namespace, environment, input/output order, types, restrictions, and referenced structures.
2. Inspect relevant built-in UI usage for interaction timing and intended meaning.
3. State what source inspection cannot prove. For an undocumented global, label a call-site or historical observation accordingly.
4. Update the domain page and event catalog if affected. Do not mix payloads from different branches in one unlabeled signature.
5. Add the source to both [sources.md](sources.md) and [source-manifest.json](source-manifest.json).
6. Add a validation case or link a named WF test result before claiming runtime support.
7. Update any affected examples, capability assessment, and open questions.

## When a client patch lands

Record the new build and source commit, compare affected declarations/call sites, and rerun the relevant runtime cases. Retain prior evidence with its original build. A patch that changes secrecy or permissions can invalidate a capture path without renaming it.

Update the review date only after actually reviewing the topic. Avoid unqualified words such as “current,” “always,” and “all” when a statement is only true of one build or scenario.

## Examples and machine-readable material

Examples must identify whether they are executable, illustrative, or synthetic. Never present invented WF IDs, quest text, trace output, or coordinates as real game data. Keep field names/types consistent with the proposed record contract.

The source manifest indexes evidence; it is not a discovered-capability report. The sample JSON demonstrates records; it is not a normative JSON Schema or test fixture proving that an addon runs. If a formal schema is later added, link its version and validation rules from the observation model.

The [acquisition backlog](../05-acquisition/acquisition-backlog.json) describes planned work, not extracted data. Keep its domain IDs, priorities, candidate sources, and output names aligned with the [acquisition catalog](../05-acquisition/catalog.md). Record tooling/schema references under their own repositories and commits. Packaged definitions, decoded records, runtime samples, and gameplay observations have different evidence scopes.

The [regression matrix](../06-testing/regression-matrix.json) is a documentation backlog, not executed tests. Keep scenario IDs stable and validate every invariant, suite, fixture, and WF validation-case reference. Its initial entries are all `planned` with empty fixture paths. When implementation begins, link actual fixtures/results and the mechanic registry without promoting offline success to WF compatibility. Changes to invariants or expected behavior must follow the [PR workflow](../06-testing/pr-workflow.md).

For automated readers, preserve evidence qualifiers and do not infer that every referenced API is callable on WF. Follow explicit build adapters and capability results rather than combining the APIs of multiple clients.

## Review checklist

- All index entries, relative links, and heading anchors resolve.
- Every source-manifest path exists at its pinned revision; web-only sources identify their authority/limits.
- Event payloads match the stated snapshot and distinguish optional/missing fields.
- Quest completion, turn-in, removal, and dialogue closure remain separate.
- Loot visibility, source attribution, receipt, and kill credit remain separate.
- Position samples identify subject, coordinate system, map and sampling time.
- Documentation code blocks do not imply production-ready code or restricted-data workarounds.
- JSON parses; record IDs, references, ordering, sample fields and missing reasons are consistent.
- Regression scenarios reference existing invariant IDs and V-cases; planned cases are not counted as implemented protection.
- Synthetic data is plainly marked, and no personal gameplay data is introduced.
- No runtime success is claimed from documentation-only checks.

Use checks appropriate to a documentation change: link/anchor validation, JSON parsing and semantic consistency, source inspection, and `git diff --check`. A runnable addon and its tests belong to later implementation changes.
