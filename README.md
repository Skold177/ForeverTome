# ForeverTome

ForeverTome is a planned observation addon for **World of Warcraft: Forever (WF)**. It will record what a player encounters during normal play so those observations can support a database of quests, items, creatures, professions, and guides.

Start with the [documentation index](docs/README.md). This first contribution establishes the API research, recording principles, and client validation plan; it does not contain a runnable addon.

The [client acquisition plan](docs/05-acquisition/README.md) defines what to collect once WF becomes downloadable: abilities, talent trees, maps, items, and other catalogs, followed by gameplay evidence and repeatable build comparisons.

The [test harness strategy](docs/06-testing/README.md) defines how future implementation PRs will protect recording behavior: replay production code against controlled event traces, preserve immutable observations, verify save/export/migration integrity, and require regression checks. It includes 16 recording invariants and 34 planned regression scenarios; the harness is not implemented yet.

The central rule is to preserve what the client actually reveals. A quest counter changing is an observation. Claiming that a particular creature caused that change requires additional evidence.

**Research date: September 16, 2026.** Reference client source has been inspected, but no WF client has been tested for this repository. Every capability must be read with its documented evidence status and build.

See [client compatibility](docs/01-foundations/client-and-evidence.md) before implementing against any example API.
