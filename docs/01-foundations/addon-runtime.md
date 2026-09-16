# How an addon runs

[Documentation index](../README.md)

**Status:** WoW runtime baseline and proposed ForeverTome structure; WF installation and startup unverified.

## The execution model

A WoW addon is code loaded by the game client. Lua implements behavior; XML can describe interface elements, although Lua can create them too. A table-of-contents file, or **TOC**, declares metadata, persistent variables, dependencies, and the files to load.

The game calls Lua handlers when events occur. A **frame** is an API object that can receive events and run scripts; it does not have to display a visible window. An invisible frame is sufficient for a passive recorder. Blizzard's own quest and loot frames illustrate this model. [R-UI](../reference/sources.md#r-ui), [R-EVENT](../reference/sources.md#r-event)

Handlers share the UI's execution time. A slow loop or excessive allocation can interrupt gameplay. Use small handlers, a bounded queue, and deferred work. There is no supported general-purpose worker thread for addon Lua.

WoW embeds its own Lua environment and extensions. Do not assume a desktop Lua interpreter's libraries or a particular modern Lua language version are available. Check language/library requirements on the selected WF build.

## Files and load order

An illustrative future addon directory is:

```text
<actual WF installation>/Interface/AddOns/ForeverTome/
    ForeverTome.toc
    Bootstrap.lua
    Compatibility.lua
    Recorder.lua
```

The actual product directory is unresolved. Do not substitute `_retail_`, `_classic_`, or any invented WF folder without checking the installation.

This is a **template**, not an installable manifest:

```text
## Interface: <interfaceVersion measured on WF>
## Title: ForeverTome
## Notes: Records gameplay observations for later export.
## Version: <addon release version>
## SavedVariables: ForeverTomeDB
Bootstrap.lua
Compatibility.lua
Recorder.lua
```

Files execute in their declared order. Define shared services before code that uses them. A manifest can declare dependencies and load-on-demand behavior; ForeverTome's initial recorder should load at login so it can establish its baseline early. Blizzard manifests demonstrate `Dependencies`, `LoadOnDemand`, and SavedVariables declarations. [R-TOC](../reference/sources.md#r-toc)

Use local variables and an addon-owned namespace to avoid collisions with other addons. WoW commonly passes the addon name and its private table as the top-level chunk's `...`. Treat that as an implementation convention to validate with the bootstrap, not as persistent storage.

## Startup and shutdown

| Stage | Meaning for the recorder |
| --- | --- |
| File execution | Define functions and subscriptions; avoid assuming world state or saved data is ready |
| `ADDON_LOADED` for `ForeverTome` | Initialize/validate the addon's restored SavedVariables; ignore other addons' notifications |
| `PLAYER_LOGIN` | Initialize the normal login session; do not fabricate acceptance events for existing quests |
| `PLAYER_ENTERING_WORLD` | Establish or refresh world context and readable snapshots; also happens beyond initial login |
| `PLAYER_LEAVING_WORLD` | Invalidate transient location and interaction context |
| `PLAYER_LOGOUT` | Perform only small final bookkeeping; do not begin asynchronous metadata requests |

`PLAYER_ENTERING_WORLD` carries initial-login and UI-reload flags in R. Do not treat every occurrence as a new login. A load-on-demand implementation must also handle being loaded after startup events have already happened. [R-LIFECYCLE](../reference/sources.md#r-lifecycle)

SavedVariables are restored by the client for declared variables. The established persistence model saves them at normal logout/UI reload; an in-memory table update is not an immediate disk write. Test both restoration and flush timing on WF. See [persistence and export](../03-data/persistence-and-export.md).

## What the sandbox exposes

The addon can use supported UI APIs, inspect permitted game state, keep Lua tables, and participate in supported UI interactions. It is not a normal desktop application with arbitrary filesystem and network access.

For the proposed recording pipeline, use SavedVariables or a user-copied export. Do not design around addon-side HTTP uploads, sockets, arbitrary file writes, launching another executable, or reading a server database. In-game addon messaging is not internet access or durable storage. This is the architectural boundary assumed here; any newly documented WF facility would need separate review and validation.

The public Blizzard web APIs are a separate service. Their existence does not make them callable from addon Lua, and this research establishes no WF database coverage through those services.

## Proposed runtime responsibilities

| Component | Responsibility |
| --- | --- |
| Compatibility adapter | Build-specific signatures, event availability, permission and readability checks |
| Domain collectors | Copy small observations while the relevant state exists |
| Recorder | Validate fields, assign identity and ordering, enforce limits |
| Metadata queue | Resolve missing item/quest details without blocking capture |
| Persistence layer | Maintain plain saved data and schema migrations |
| Export interface | Give the user a reviewable export and clear save instructions |

These are responsibilities, not implemented modules or a commitment to a library/framework. The first PR contains documentation only.
