# Test harness strategy

[Documentation index](../README.md)

**Status: proposed engineering contract.** This repository currently contains documentation, not a runnable addon, test harness, or enforced CI workflow. No mechanic is declared working by this document. The WF client is still unavailable for testing at the time of planning. Reviewed on 2026-09-16.

ForeverTome will be developed around **replayable behavior tests of the production recording code**. Every supported mechanic must have evidence describing what it records, regression fixtures that protect that behavior, and tests showing that later work cannot corrupt already accepted data.

## The contract we are protecting

Given a specified client profile, readable API results, initial saved state, and event schedule, the recorder must produce the expected observations and diagnostics. Existing observations must retain their identity, values, evidence, time, location, and order through subsequent capture, enrichment, save/load, export, and compatible upgrades.

This is a scoped guarantee about our implementation. It cannot guarantee that the client delivers every event or saves memory before a crash. Missing information and lost coverage must remain explicit.

## Read the design

| Page | What it defines |
| --- | --- |
| [Harness design](harness-design.md) | Production-code boundaries, Lua execution, strict fake APIs, clock/scheduler control, and test layers |
| [Fixtures and replay](fixtures-and-replay.md) | Input traces, independently reviewed expected outputs, fixture provenance, and reproducible failures |
| [Recording invariants](recording-invariants.md) | The rules that protect event meaning, record ownership, deduplication, and immutable history |
| [Persistence and recovery](persistence-and-recovery.md) | Save/load boundaries, export/import, migrations, truncation, and data-loss tests |
| [PR workflow and rollout](pr-workflow.md) | Test-first implementation, regression gates, intentional changes, and what to build first |
| [Regression matrix](regression-matrix.json) | Stable scenario IDs, protected invariants, required suites, and links to WF validation cases |

The [observation model](../03-data/observation-model.md) remains the data contract. The [WF test plan](../04-validation/wf-test-plan.md) remains the runtime verification procedure. Tests must enforce these meanings, not silently replace them with whatever the implementation happens to emit.

## Three kinds of confidence

| Evidence | What passing establishes | What it does not establish |
| --- | --- | --- |
| Synthetic contract/replay tests | Our production code handles the specified inputs and failures correctly | That WF emits those inputs or permits those APIs |
| Sanitized replay of a real client session | Our code handles the observed product/build/context without the protected regression | That another product, context, or later build behaves the same way |
| Named in-client validation | The tested addon actually behaves correctly on that product/build/context | Exhaustive coverage, cross-product compatibility, or permanent compatibility |

Store these separately. A synthetic suite cannot promote an API to `wf_verified`. A manual success without a regression fixture does not establish ongoing PR protection.

Retail can supply initial real-client tests while WF is unavailable. Use a shared recording core with a separate Retail adapter, retain product/build identity on every capture, and keep Retail observations out of the WF content database. Follow the [Retail development milestone](pr-workflow.md#retail-development-before-wf).

## What qualifies as a protected mechanic

Before calling a mechanic supported, its implementation PR must supply:

1. A named behavior contract and supported client/context scope.
2. At least one representative success replay and meaningful failure/edge cases.
3. Exact output assertions, including forbidden or absent records where relevant.
4. Record-integrity tests through storage and export, not just the handler's return value.
5. A fixture/test mapping in the mechanic registry and an enabled CI suite that runs it.
6. WF runtime evidence before claiming that build's compatibility.

“Protected offline” and “verified on WF” are separate statuses. The initial implementation can establish the former while the client is unavailable.

## Acceptance bar for future changes

No silent event loss, no silent rewriting of history, no guessed causal links, and no green result produced by missing tests. An intentional behavior change must update a written contract and its reviewed expected results. A data-format change must include compatibility/migration evidence and preserve recoverable prior data.

The harness itself must demonstrate that it detects representative broken implementations, including a removed deep copy, a swapped event argument, and an in-place metadata update. A test suite that still passes those errors is not yet protecting the mechanic.

## Initial implementation order

Build record ownership and storage tests first, then event replay and collectors, then persistence/export compatibility, and finally real-client fixture capture. The [rollout](pr-workflow.md#implementation-milestones) defines concrete exit criteria for each stage. This documentation change does not install test tooling, create workflows, change repository branch rules, or implement an addon.
