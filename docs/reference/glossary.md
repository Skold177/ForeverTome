# Glossary

[Documentation index](../README.md)

| Term | Meaning in this handbook |
| --- | --- |
| Adapter | ForeverTome code that translates one verified client API/payload into the recorder's internal form |
| Addon | Lua/XML code loaded inside WoW's supported UI environment |
| API | Functions, events, structures, and objects that the client exposes to UI code |
| Build | An exact client revision; more precise than a product name or expansion label |
| Capability | A tested ability to capture a particular kind of readable information in a stated context |
| CASC | A storage format used by Blizzard clients; a candidate archive type to inspect after WF download |
| Capture | Copying permitted fields while the relevant state is available |
| Collector | A component responsible for observations from one domain, such as quests or loot |
| Content ID | A numeric identifier for a quest, item, creature template, recipe, or other content; scoped to product/build |
| Content snapshot | A preserved set of source artifacts and relevant overlay state with identity, hashes, scope, and capture time |
| Correlation | Relating observations using identifiers, interaction context, time, and explicit evidence |
| Delta | A difference between comparable snapshots |
| DBC / DB2 | Families of structured client database file formats; their rows are definitions, not a complete server database |
| DBD | A table-layout definition used by community parsing tools, matched to a build/layout and sometimes containing provisional meanings |
| Enrichment | Metadata added later while retaining the original observation's identity/time/location |
| Event | A named notification delivered by the client |
| Evidence | The recorded basis for a fact or relationship, including source, build, context, and supporting observations |
| Fixture | Versioned test inputs and starting state that reproduce a named scenario |
| Frame | A UI API object that can receive events and scripts, even when invisible |
| Golden result | Independently reviewed expected output used to detect behavior changes |
| GUID | A client entity identifier; distinct from a reusable token and from a creature template ID |
| Idempotent import | Processing the same observation again without duplicating its database effect |
| Instance | A gameplay context such as a dungeon; a returned instance identifier need not identify a unique running copy |
| Invariant | A behavior or data-integrity rule that must hold across the scenarios within its declared scope |
| Item link | A WoW hyperlink containing item identity/variant information and display markup |
| Locale | The client's language/region code for localized text, such as `enUS` |
| Loot session | One locally tracked loot interaction; not necessarily one creature or one item receipt |
| Namespace | A table prefix such as `C_QuestLog` that groups API functions |
| NPC | Non-player character; its template ID is not the identity of every individual spawned instance |
| Observation | A permitted fact read from the client at a recorded time |
| Observer location | Where the player was when the observation was sampled |
| Objective layout | The ordered objective rows currently exposed for a quest; may change between stages |
| Payload | An event's ordered arguments, excluding the frame and event name passed to `OnEvent` |
| Processing run | One interpretation of a content snapshot using recorded parser, schema, and normalization revisions |
| POI | Point of interest; a UI marker is not necessarily a measured entity location |
| Protected action | An operation limited to authorized secure execution/user interaction |
| Quest run | A particular acceptance-to-end occurrence of a quest, including an unknown-start baseline run |
| Reference | Evidence from the exact source snapshot named in the handbook; not a WF runtime guarantee |
| Replay | Running production code against a controlled sequence of events, API responses, and clock/scheduler steps |
| Restricted API | An interface whose access is limited by the client |
| SavedVariables | Variables declared in a manifest for client-managed persistence between sessions |
| Secret value | Data that can be passed through approved UI paths but may be unreadable to addon computation |
| Session | One uninterrupted recording runtime; reload/reconnect creates an explicit boundary |
| Snapshot | A copy of readable state at a particular sampling time |
| Subevent | A more specific event kind inside a parent feed, such as historical combat-log `UNIT_DIED` |
| Synthetic | Invented test/example data; useful for testing project rules but not evidence of actual WF behavior |
| Taint | Tracking of execution/data originating outside trusted UI code |
| TOC | Table-of-contents manifest declaring addon metadata, persistence, dependencies, and load order |
| UI map ID | Identifier of a map used by the UI; distinct from arbitrary instance/world-coordinate identifiers |
| Unit token | Temporary handle such as `target`, `player`, or `nameplate1` |
| WF | World of Warcraft: Forever, the target game for ForeverTome |
