# PR workflow and harness rollout

[Documentation index](../README.md) · [Testing strategy](README.md)

**Status: proposed process.** The commands, registry, workflow, and required check described here do not exist yet. Implement them in the milestones below before describing the repository as protected by automated regression tests.

## Develop against a behavior contract

For each new recording mechanic:

1. Define its inputs, supported profiles, expected observations, missing-data behavior, and events it must not infer. Reference the relevant [recording invariants](recording-invariants.md).
2. Write a small synthetic replay and independent expected results. Include at least one meaningful adverse case, such as unavailable metadata, a repeated notification, or an interrupted interaction.
3. Run the test and demonstrate that it fails for the intended missing behavior. A syntax error or absent dependency does not demonstrate a useful regression test.
4. Implement the production path, then pass that replay and the applicable existing suites.
5. Assert the stored and exported observations, including the unchanged prefix of older history. A correct immediate return value is insufficient.
6. Register the mechanic's tests and scope. Add named WF runtime evidence separately when available.

A bug fix starts with a minimized reproduction that fails on the unfixed code. Preserve that fixture after the fix. Refactoring keeps existing behavior fixtures; add cases when the refactor exposes an uncovered boundary.

## Track what is actually protected

The [regression matrix](regression-matrix.json) is the initial backlog. Every entry is currently `planned`, with no implemented fixture paths. It must not be counted as a passing test suite.

The future `tests/mechanics.json` registry will map each admitted mechanic to:

| Field | Required meaning |
| --- | --- |
| Mechanic ID and contract | Stable name, behavior-document link, applicable invariant/scenario IDs |
| Scope | Exact adapter/profile IDs, collector contexts, and schema versions |
| Offline status | Planned or protected; protection requires discovered, executed tests |
| Test mapping | Required suites, test IDs, input fixtures, expected outputs, and meaningful negative cases |
| Runtime evidence | Separate unverified/verified status scoped to product/build/context, date, and evidence links; Retail results cannot verify WF |
| Compatibility policy | Supported historical data versions and intentional scope retirements |

CI validates the mapping in both directions: protected mechanics cannot have missing tests, and named test IDs must resolve. A changed registry cannot quietly remove an existing mechanic or profile from enforcement; removal needs an explicit compatibility decision in the PR. Keep prior evidence under its original build.

Do not create one registry row for every individual assertion. Use meaningful behaviors such as quest objective progress, loot visibility, record ownership, and saved-data migration. Keep regression scenario IDs stable when files move.

## Planned local interface

The harness implementation should provide one documented entry point with consistent exit codes and machine-readable results. The proposed interface is:

```text
python tools/test.py --suite required
python tools/test.py --fixture <fixture-id>
python tools/test.py --suite adversarial --seed <integer>
```

**These are interface proposals, not runnable commands in this documentation contribution.** The implementation PR must replace them with its actual supported commands and setup instructions, including pinned interpreter/tool versions. `required` must resolve to the admitted suite/profile matrix and fail if a required test cannot run. A focused fixture run helps diagnosis but does not replace the full PR check.

Report test IDs, discovered/executed/passed/failed/skipped counts, active profiles, tool versions, seed, and addon revision. Return a nonzero exit code for assertion failures, runner errors, missing fixtures, invalid expectations, or unexpected skips. Upload compact diagnostic reports and minimized synthetic failure traces; do not attach private client logs.

## Required CI behavior

Use GitHub Actions for the proposed automated gate, with a stable aggregate check name such as `ForeverTome / regression`. Configure that check as required only after the workflow exists and successfully demonstrates both passing and failing runs. No branch protection or workflow is configured by this documentation.

| Suite | PR requirement once admitted | What blocks a merge |
| --- | --- | --- |
| `contracts` | Every PR | Invalid record types/identity, aliasing, changed committed history, or violated evidence rules |
| `replay` | Every PR, all supported offline profiles | Unexpected output, missing output, forbidden inference, incorrect payload decoding, or unsatisfied API expectations |
| `persistence` | Every PR | Lost/changed fields, broken restore/export, migration data loss, or importer incompatibility once the importer exists |
| `adversarial` | Every PR with a bounded fixed seed set | Duplicate/loss bugs, invalid schedule handling, capacity failures, or required fault checks not detected |
| `package` | Every PR | Manifest/load-order errors, undeclared runtime dependencies, or test/development code in the release artifact |
| `client` | Separate recorded WF validation when applicable | Failed or absent required build evidence blocks a new WF compatibility claim; it is not an offline CI success |

Before a milestone admits a suite, label it pending implementation. Once admitted, do not turn its failure into an allowed failure merely to merge. Keep all previously admitted suites enabled as later milestones land.

Run on pull requests and pushes to the main development branch. If a merge queue is introduced, add its `merge_group` trigger. Test the resulting integration revision and retain the reported commit SHA. Required GitHub checks apply to the latest revision; merge queue events need explicit workflow coverage. [TEST-GITHUB-CHECKS](../reference/sources.md#test-github-checks)

The aggregate gate must run even when a prerequisite fails, then explicitly require `success` from each required suite/profile and validate the result manifest's test mapping and counts. It must fail for failed, canceled, missing, or skipped required work. GitHub can treat skipped/neutral checks as satisfying a requirement, while path-filtered workflows can leave a required check pending; do not rely on either behavior to enforce testing. Keep the required workflow active for documentation changes too. [TEST-GITHUB-CHECKS](../reference/sources.md#test-github-checks)

Pin tool and dependency revisions, record the Lua interpreter version, and run without a WF installation, live network API, credentials, or real player data. Use a Linux runner for the primary deterministic suite and a Windows package/load check to cover the contributor/client file layout. If a host-specific behavior appears, add a focused test on that host. Workflow triggers and filters belong in the checked-in workflow and must be reviewed with the runner changes. [TEST-GITHUB-WORKFLOWS](../reference/sources.md#test-github-workflows)

Use scheduled runs for longer seeded histories and larger performance samples. Promote any reproducible failure to a small fixed PR regression. Do not defer the only test of record immutability, data preservation, or a supported collector to a scheduled job.

## Prove that the harness detects damage

Include controlled broken variants as harness self-checks, each isolated from the shipping artifact. The ordinary version must pass; the expected assertion must fail when its variant is enabled. A crash or setup failure does not count as detecting the intended defect.

| Deliberate defect | Required detection |
| --- | --- |
| Replace the nested capture copy with a shared reference | A prior or queued snapshot changes after its input table is reused |
| Decode the wrong `QUEST_ACCEPTED` argument | The emitted quest ID differs from the profile-specific expected ID |
| Update an earlier record during metadata resolution | The saved history prefix changes instead of receiving an enrichment |
| Drop one field during serialization | Independent expected data differs from restored/exported data |
| Disable a required suite or return success without executing it | The aggregate gate rejects missing execution/results |

The first four are examples of mutation testing: deliberately changing code to check whether tests notice. Start with these focused defects, not an arbitrary repository-wide mutation percentage. Also test the runner's exit-code propagation and unexpected-error reporting. Never commit an enabled broken variant into the addon package.

## Intentional changes to behavior or data

Expected output files are reviewed specifications. CI must not regenerate them as a way to pass a failing PR. A developer may generate a candidate diff locally, but must explain every semantic change and retain the previous regression's purpose.

A behavior change states what a user previously recorded, what will now be recorded, and why. A data-format change additionally names the old/new schema versions, compatibility policy, migration fixtures, interrupted-upgrade behavior, and importer impact. Test older supported files against the new implementation. Preserve recovery for unknown newer versions.

Keep unrelated golden-file churn out of the change. Do not normalize away event order, IDs, timestamps, coordinates, missing reasons, or evidence to hide differences. Removing an assertion requires explaining why the asserted behavior is no longer part of the contract.

## Review checklist

- The affected mechanic, profiles, schemas, and invariant IDs are named.
- New behavior has reviewed expected observations and meaningful absence/error assertions.
- A bug fix includes its failing reproduction and the reason it failed before the fix.
- Existing records remain unchanged through later events, enrichment, restore, and export.
- Migration or compatibility changes have explicit old-data tests and recoverable failure behavior.
- Required tests actually ran; no fixture disappearance, unexplained skip, or automatic expected-output update is hidden by a green check.
- Real-client claims link to named WF evidence; offline-only results retain that label.

Line coverage can highlight unexercised code once measured. It is supplementary: an executed append function can still retain an aliased table, omit a field, or misclassify a quest event. Prefer complete assertion coverage of the named contracts and critical failure boundaries over a blanket percentage target.

## Retail development before WF

Use a playable Retail client as the initial real-client development environment when available. Build the shared recorder, immutable storage, export, and harness independently of client-specific API decoding. Keep a Retail adapter and its measured profile separate from the eventual WF adapter. Identify the installed build rather than assuming it matches the handbook's source snapshot.

The first real-session acceptance test is: install/load the addon, establish a quest baseline or acceptance, advance an objective, observe loot, turn in the quest, save/reload, and independently inspect the retained records. Capture the permitted event/API inputs needed to make that session reproducible, sanitize them, and add a replay fixture. Verify recording status, error reporting, and capacity behavior alongside the data.

Retail captures and compatibility results remain scoped to Retail. They do not populate the WF content catalog or prove WF event arguments, profession/talent systems, combat permissions, or save behavior. When WF arrives, identify its actual build, inspect the differences, implement its adapter, and execute the applicable [WF cases](../04-validation/wf-test-plan.md). Unsupported collectors remain disabled with a recorded reason.

This milestone requires an implemented addon and harness; the current documentation does not include either. A downloaded client can support file/API inspection, while gameplay and native persistence checks require a logged-in session controlled by the tester.

## Implementation milestones

| Stage | Deliverable | Exit criterion |
| --- | --- | --- |
| 1. Record contract and runner | Production record validation/copy/append boundary, pinned Lua runner, independent assertions, initial mechanic registry | Nested aliasing, immutable prefix, unsupported values, identity, and runner failure cases pass; controlled copy/runner defects are detected; admit `contracts` and gate integrity checks |
| 2. Deterministic event replay | Strict fake host, profiles, controlled clocks/scheduler, first quest and loot collectors | Success, duplicate, missing-data, changed-layout, and wrong-payload cases exercise production paths; repeat runs are identical; admit `replay` and bounded `adversarial` suites |
| 3. Saved data and export | Restore boundary, schema contract, exporter, representative old-version fixtures when a version transition exists | Independent expected data survives supported round trips; interrupted/future migrations preserve input; save-vs-crash limits are explicit; admit `persistence` |
| 4. Package and first WF verification | Real manifest/bootstrap, release packaging, sanitized trace capture, measured client profile | Package checks pass; applicable V-cases have recorded results on the named WF build; admit `package` and only the demonstrated WF capabilities |
| 5. External import and expanding coverage | Importer contract tests when implemented, broader collectors, seeded long runs | Retry/conflict/partial-batch behavior verified; each new mechanic satisfies the same admission criteria; preserved failures become permanent regressions |

Stages describe dependency order, not permission to ship an untested data path. In-memory tests may precede a persistent addon, but persistence tests must accompany the first storage/export implementation. A first real-client addon requires both storage and package checks. An importer cannot be called compatible until its own tests execute. Extend the harness in the same PR as each new boundary.
