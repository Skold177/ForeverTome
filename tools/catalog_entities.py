"""Build content catalogs from validated ForeverTome observations."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re


BUCKETS = {
    "item": "items", "quest": "quests", "npc": "npcs", "spell": "spells",
    "talent": "talents", "recipe": "recipes", "map": "maps",
    "profession": "professions", "currency": "currencies", "object": "objects",
}
ITEM_FIELDS = frozenset({
    "item_id", "itemID", "link", "item_link", "hyperlink", "requested_link", "name",
    "quality", "item_level", "minimum_level", "item_type", "subtype", "stack_size",
    "equip_location", "icon_id", "icon_path", "texture", "sell_price_copper", "class_id",
    "subclass_id", "bind_type", "expansion_id", "set_id", "crafting_reagent", "description",
    "quantity", "quantity_min", "quantity_max", "price", "stackCount", "numAvailable",
    "isPurchasable", "isUsable", "hasExtendedCost", "usable", "context_flags", "links",
    "stats", "stat_labels", "stats_status", "stats_link", "stats_context", "stats_method",
    "tooltip_lines", "tooltip_status", "tooltip_link", "tooltip_context", "tooltip_method",
    "effect_spell_id", "use_spell_id", "equip_spell_id", "item_spell_id", "item_spell_name",
    "item_spell_status", "item_spell_method", "gems",
})
SPELL_FIELDS = frozenset({
    "spell_id", "spellID", "name", "iconID", "originalIconID", "castTime", "minRange",
    "maxRange", "resolved_spell_id", "description", "subtext", "is_passive", "base_spell_id",
    "override_spell_id", "values_context", "base_cooldown_status", "base_cooldown_ms",
    "current_state", "subName", "isPassive", "isOffSpec", "levelLearned", "is_low_rank",
    "is_flyout_member", "item_type", "is_known", "skillLineIndex", "bank", "spec_id",
    "tooltip_lines", "tooltip_status", "tooltip_context", "tooltip_method",
    "cast_time_status", "reported_cast_time_ms",
})
QUEST_FIELDS = frozenset({
    "quest_id", "questID", "title", "level", "questLevel", "suggestedGroup", "frequency",
    "isTask", "isBounty", "isStory", "isHidden", "isAutoComplete", "questClassification",
    "campaignID", "description", "objective_text", "text", "phase", "quest_start_item_id",
    "rewards", "choices", "required_items", "required_money", "reward_money", "reward_xp",
    "isTrivial", "repeatable", "isLegendary", "isIgnored", "isImportant", "isMeta", "questInfoID",
})


def _digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _identifier(value):
    return type(value) is int and value > 0


def _rows(value):
    if isinstance(value, list):
        return [(index, row) for index, row in enumerate(value) if isinstance(row, dict)]
    return []


def _fields(source, names):
    return {key: value for key, value in source.items() if key in names}


def _item_id(link):
    if not isinstance(link, str):
        return None
    match = re.search(r"(?:^|\|H)item:([1-9][0-9]{0,9})(?=[:|]|$)", link)
    if match:
        return int(match.group(1))
    return None


class CatalogBuilder:
    def __init__(self):
        self._entities = {}
        self._context  = None
        self._source   = None
        self._kind     = None
        self._session  = None
        self._refs     = []
        self._seen     = set()

    def _entity(self, kind, native_id, role, path):
        if not _identifier(native_id) and not isinstance(native_id, str):
            return None
        key       = f"{self._context}:{kind}:{native_id}"
        reference = (key, role, path)
        if reference not in self._seen:
            self._refs.append({"key": key, "role": role, "path": path})
            self._seen.add(reference)
        if key not in self._entities:
            self._entities[key] = {
                "key": key, "contextId": self._context, "kind": kind,
                "nativeId": native_id, "display": {}, "details": {}, "sourceIds": set(),
                "facts": {}, "_display_rank": (0, 0, 0, 0, 0),
            }
            if kind == "item":
                self._entities[key]["variants"] = {}
        entity = self._entities[key]
        entity["sourceIds"].add(self._source)
        return entity

    def _fact(self, entity, path, data, fact_type=None):
        if entity is None or not data:
            return
        fact_type = fact_type or self._kind
        identity  = _digest({"type": fact_type, "path": path, "data": data})
        facts     = entity["facts"]
        if identity not in facts:
            facts[identity] = {
                "id": f"{entity['key']}:fact:{identity}", "type": fact_type,
                "path": path, "data": copy.deepcopy(data), "sourceIds": set(),
            }
        facts[identity]["sourceIds"].add(self._source)

    def _display(self, entity, data, priority=10, details=None):
        if entity is None:
            return
        display = {}
        aliases = {
            "name": ("name", "title", "overrideName", "titleText", "displayName", "professionName", "map_name"),
            "description": ("description", "overrideDescription"),
            "iconId": ("icon_id", "iconID", "overrideIcon", "icon", "texture"),
            "iconPath": ("icon_path",),
            "link": ("link", "hyperlink", "item_link"),
            "observedLabel": ("observed_label",),
        }
        for target, candidates in aliases.items():
            for field in candidates:
                value = data.get(field)
                if (target == "iconId" and _identifier(value)) or (
                    target != "iconId" and isinstance(value, str) and value
                ):
                    display[target] = value
                    break
        fields        = {}
        stats_ready   = 0
        tooltip_ready = 0
        if entity["kind"] == "item" and self._kind == "item.metadata":
            fields = {
                "quality": "quality", "item_level": "itemLevel", "minimum_level": "minimumLevel",
                "item_type": "itemType", "subtype": "subtype", "stack_size": "stackSize",
                "equip_location": "equipLocation", "sell_price_copper": "sellPriceCopper",
                "class_id": "classId", "subclass_id": "subclassId", "bind_type": "bindType",
                "expansion_id": "expansionId", "set_id": "setId", "crafting_reagent": "craftingReagent",
                "requested_link": "requestedLink", "stats": "stats", "stat_labels": "statLabels",
                "stats_status": "statsStatus", "stats_link": "statsLink", "stats_context": "statsContext",
                "stats_method": "statsMethod", "tooltip_lines": "tooltipLines", "tooltip_status": "tooltipStatus",
                "tooltip_link": "tooltipLink", "tooltip_context": "tooltipContext", "tooltip_method": "tooltipMethod",
            }
            if isinstance(data.get("stats"), dict):
                stats_ready = 2 if data.get("stats_status") == "available" else int(bool(data["stats"]))
        elif entity["kind"] == "spell":
            fields = {
                "castTime": "castTimeMs", "minRange": "minRange", "maxRange": "maxRange",
                "subtext": "subtext", "is_passive": "isPassive", "isPassive": "isPassive",
                "current_state": "currentState", "values_context": "valuesContext",
                "resolved_spell_id": "resolvedSpellId", "base_spell_id": "baseSpellId",
                "override_spell_id": "overrideSpellId", "base_cooldown_ms": "baseCooldownMs",
                "base_cooldown_status": "baseCooldownStatus", "tooltip_lines": "tooltipLines",
                "tooltip_status": "tooltipStatus", "tooltip_context": "tooltipContext",
                "tooltip_method": "tooltipMethod",
                "cast_time_status": "castTimeStatus", "reported_cast_time_ms": "reportedCastTimeMs",
            }
        for original, target in fields.items():
            if original in data:
                value = data[original]
                if original == "castTime" and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                    display["castTimeStatus"] = "invalid_result"
                    continue
                display[target] = copy.deepcopy(value)
        if isinstance(data.get("tooltip_lines"), list):
            tooltip_ready = 2 if data.get("tooltip_status") == "available" else int(bool(data["tooltip_lines"]))
        rank = (priority, int("name" in display), stats_ready, tooltip_ready, len(display))
        if data and rank > entity["_display_rank"]:
            entity["display"]         = display
            entity["details"]         = copy.deepcopy(data if details is None else details)
            entity["displaySourceId"] = self._source
            entity["_display_rank"]   = rank

    def _variant(self, entity, link):
        if entity is None or not isinstance(link, str) or not link:
            return
        if _item_id(link) != entity["nativeId"]:
            return
        identity = _digest(link)
        variants = entity["variants"]
        if identity not in variants:
            variants[identity] = {
                "key": f"{entity['key']}:variant:{identity}",
                "link": link, "sourceIds": set(),
            }
        variants[identity]["sourceIds"].add(self._source)

    def _item(self, row, path, role, identifier_fields=("item_id", "itemID")):
        identity = None
        field    = None
        for candidate in identifier_fields:
            if _identifier(row.get(candidate)):
                identity = row[candidate]
                field    = candidate
                break
        if identity is None:
            for candidate in ("link", "item_link", "hyperlink", "requested_link"):
                identity = _item_id(row.get(candidate))
                if identity:
                    field = candidate
                    break
        if identity is None:
            return None
        entity = self._entity("item", identity, role, f"{path}.{field}")
        data   = _fields(row, ITEM_FIELDS)
        self._fact(entity, path, data)
        self._display(entity, row, 100 if self._kind == "item.metadata" else 10)
        for field in ("link", "item_link", "hyperlink", "requested_link"):
            self._variant(entity, row.get(field))
        links = row.get("links")
        if isinstance(links, list):
            for link in links:
                self._variant(entity, link)
        return entity

    def _spell(self, row, path, role, field="spell_id"):
        identity = row.get(field)
        if not _identifier(identity):
            return None
        entity = self._entity("spell", identity, role, f"{path}.{field}")
        data   = _fields(row, SPELL_FIELDS)
        if data:
            self._fact(entity, path, data)
            self._display(entity, data, 100 if self._kind == "spell.metadata" else 10, details=row)
        return entity

    def _quest(self, row, path, role, field="quest_id"):
        identity = row.get(field)
        if not _identifier(identity):
            return None
        entity   = self._entity("quest", identity, role, f"{path}.{field}")
        metadata = row.get("metadata")
        if isinstance(metadata, dict):
            self._fact(entity, f"{path}.metadata", metadata)
            self._display(entity, metadata, 80)
        data = _fields(row, QUEST_FIELDS)
        self._fact(entity, path, data)
        self._display(entity, data, 100 if self._kind == "quest.metadata" else 30, details=row)
        return entity

    def _unit(self, row, path, role):
        if not isinstance(row, dict):
            return
        entity   = None
        identity = row.get("creature_id")
        if _identifier(identity):
            entity = self._entity("npc", identity, role, f"{path}.creature_id")
            data   = {key: value for key, value in row.items() if key != "entity_position"}
            self._fact(entity, path, data, "unit.descriptor")
            self._display(entity, data, 20, details=row)
        guid = row.get("source_guid", row.get("guid"))
        if entity is None and isinstance(guid, str):
            match = re.fullmatch(r"GameObject-[0-9]+-[0-9]+-[0-9]+-[0-9]+-([1-9][0-9]{0,9})-[0-9A-Fa-f]+", guid)
            if match and int(match.group(1)) <= 2147483647:
                guid_field = "source_guid" if "source_guid" in row else "guid"
                entity = self._entity("object", int(match.group(1)), role, f"{path}.{guid_field}")
                self._fact(entity, path, row, "object.descriptor")
                self._display(entity, row, 20)
        position = row.get("entity_position")
        if entity is not None and isinstance(position, dict):
            self._fact(entity, path, {"entity_position": position}, "unit.position")
        if isinstance(position, dict) and _identifier(position.get("map_id")):
            self._entity("map", f"map:{position['map_id']}", "entity_position_map", f"{path}.entity_position.map_id")
        return entity

    def _loot(self, data, item):
        if self._kind not in {"loot.visible", "item.received"}:
            return
        if not any(field in data for field in ("sources", "source_candidates", "loot_session_id")):
            return
        provenance = _fields(data, {
            "item_id", "link", "quantity", "loot_session_id", "slot", "revision",
            "loot_slot", "loot_revision", "loot_match_status", "source_status",
            "source_quantity_matches", "source_method", "source_mapping_status", "sources", "source_candidates",
        })
        self._fact(item, "data", provenance, "loot.provenance")
        mapped      = data.get("source_status") == "mapped" and data.get("source_quantity_matches") is not False
        source_role = "loot_source" if mapped and data.get("source_mapping_status") == "validated" else "loot_candidate"
        for field, role in (("sources", source_role), ("source_candidates", "loot_candidate")):
            for index, row in _rows(data.get(field)):
                entity = self._unit(row, f"data.{field}[{index}]", role)
                self._fact(entity, "data", provenance, "loot.provenance")

    def _currency(self, row, path, role, field="currency_id", namespace=None):
        identity = row.get(field)
        if not _identifier(identity):
            return
        native_id = f"{namespace}:{identity}" if namespace else identity
        entity    = self._entity("currency", native_id, role, f"{path}.{field}")
        data      = _fields(row, {field, "name", "currency_name", "quantity", "link", "icon_id", "icon_path"})
        self._fact(entity, path, data)
        self._display(entity, data)

    def _map(self, location):
        if not isinstance(location, dict) or not _identifier(location.get("ui_map_id")):
            return
        entity = self._entity("map", f"ui_map:{location['ui_map_id']}", "observer_map", "location.ui_map_id")
        data   = _fields(location, {"ui_map_id", "map_name", "parent_map_id"})
        self._fact(entity, "location", data, "map.descriptor")
        self._display(entity, data)
        if _identifier(location.get("parent_map_id")):
            self._entity("map", f"ui_map:{location['parent_map_id']}", "parent_map", "location.parent_map_id")

    def _talent_ref(self, namespace, identity, role, path):
        if _identifier(identity):
            native_id = f"config:{self._session}:{identity}" if namespace == "config" else f"{namespace}:{identity}"
            return self._entity("talent", native_id, role, path)
        return None

    def _talent(self, data):
        namespace = data.get("entity_type")
        if self._kind == "talent.metadata" and isinstance(namespace, str) and namespace in {
            "config", "tree", "node", "entry", "definition", "condition", "group", "subtree"
        }:
            entity = self._talent_ref(namespace, data.get("entity_id"), "metadata", "data.entity_id")
            self._fact(entity, "data", data)
            info = data.get("info")
            if isinstance(info, dict):
                self._display(entity, info, 100, details=data)
                self._talent_info(info, "data.info")
        if self._kind == "talent.rank":
            entity = self._talent_ref("entry", data.get("entry_id"), "rank_description", "data.entry_id")
            self._fact(entity, "data", data)
            self._display(entity, data, 20)
        for field, namespace in (("tree_id", "tree"), ("config_id", "config")):
            self._talent_ref(namespace, data.get(field), namespace, f"data.{field}")
        tree_ids = data.get("tree_ids")
        if isinstance(tree_ids, list):
            for index, identity in enumerate(tree_ids):
                self._talent_ref("tree", identity, "tree", f"data.tree_ids[{index}]")
        for index, row in _rows(data.get("nodes")):
            path   = f"data.nodes[{index}]"
            entity = self._talent_ref("node", row.get("node_id"), "build_node", f"{path}.node_id")
            self._fact(entity, path, row)
            self._display(entity, row, 20)
            self._talent_ref("tree", row.get("tree_id"), "tree", f"{path}.tree_id")
            active = row.get("active_entry")
            if isinstance(active, dict):
                self._talent_ref("entry", active.get("entryID"), "active_entry", f"{path}.active_entry.entryID")
            committed = row.get("committed_entry_ids")
            if isinstance(committed, list):
                for entry_index, identity in enumerate(committed):
                    self._talent_ref("entry", identity, "committed_entry", f"{path}.committed_entry_ids[{entry_index}]")

    def _talent_info(self, info, path):
        fields = {
            "definitionID": "definition", "subTreeID": "subtree", "rootNodeID": "node",
            "cascadeRepurchaseEntryID": "entry", "treeID": "tree",
        }
        for field, namespace in fields.items():
            self._talent_ref(namespace, info.get(field), namespace, f"{path}.{field}")
        arrays = {
            "treeIDs": "tree", "nodeIDs": "node", "entryIDs": "entry",
            "entryIDsWithCommittedRanks": "entry", "groupIDs": "group", "conditionIDs": "condition",
            "subTreeSelectionNodeIDs": "node",
        }
        for field, namespace in arrays.items():
            values = info.get(field)
            if isinstance(values, list):
                for index, identity in enumerate(values):
                    self._talent_ref(namespace, identity, namespace, f"{path}.{field}[{index}]")
        for field in ("spellID", "overriddenSpellID"):
            identity = info.get(field)
            if _identifier(identity):
                self._entity("spell", identity, "talent_spell", f"{path}.{field}")
        self._quest(info, path, "condition_quest", "questID")
        self._currency(info, path, "trait_currency", "traitCurrencyID", "trait")
        for field in ("activeEntry", "nextEntry"):
            value = info.get(field)
            if isinstance(value, dict):
                self._talent_ref("entry", value.get("entryID"), field, f"{path}.{field}.entryID")
        for index, edge in _rows(info.get("visibleEdges")):
            self._talent_ref("node", edge.get("targetNode"), "edge_target", f"{path}.visibleEdges[{index}].targetNode")
        for index, gate in _rows(info.get("gates")):
            self._talent_ref("node", gate.get("topLeftNodeID"), "gate_node", f"{path}.gates[{index}].topLeftNodeID")
            self._talent_ref("condition", gate.get("conditionID"), "gate_condition", f"{path}.gates[{index}].conditionID")
        for index, row in _rows(info.get("entry_rank_increases")):
            self._talent_ref("entry", row.get("entry_id"), "rank_increase", f"{path}.entry_rank_increases[{index}].entry_id")
        for index, row in _rows(info.get("currencies")):
            self._currency(row, f"{path}.currencies[{index}]", "trait_currency", "traitCurrencyID", "trait")
        for index, row in _rows(info.get("costs")):
            self._currency(row, f"{path}.costs[{index}]", "trait_cost", "ID", "trait")

    def _spellbook(self, data):
        for index, row in _rows(data.get("entries")):
            path = f"data.entries[{index}]"
            self._spell(row, path, "spellbook_entry", "spellID")
            if row.get("item_type") in ("Spell", "FutureSpell") and _identifier(row.get("actionID")):
                self._entity("spell", row["actionID"], "spellbook_action", f"{path}.actionID")
            for child_index, child in _rows(row.get("flyout_slots")):
                child_path = f"{path}.flyout_slots[{child_index}]"
                self._spell(child, child_path, "flyout_spell")
                if _identifier(child.get("override_spell_id")):
                    self._entity("spell", child["override_spell_id"], "flyout_override", f"{child_path}.override_spell_id")
        for field, role in (("added_spell_ids", "added_spell"), ("removed_spell_ids", "removed_spell")):
            values = data.get(field)
            if isinstance(values, list):
                for index, identity in enumerate(values):
                    if _identifier(identity):
                        self._entity("spell", identity, role, f"data.{field}[{index}]")

    def _recipe(self, data):
        field    = "recipe_id" if _identifier(data.get("recipe_id")) else "recipeID"
        identity = data.get(field)
        if _identifier(identity):
            entity = self._entity("recipe", identity, "recipe", f"data.{field}")
            self._fact(entity, "data", data)
            self._display(entity, data, 100 if self._kind == "recipe.metadata" else 10)
        if _identifier(data.get("base_recipe_id")):
            self._entity("recipe", data["base_recipe_id"], "base_recipe", "data.base_recipe_id")
        for field, role in (("previous_recipe_id", "previous_recipe"), ("next_recipe_id", "next_recipe"),
                            ("previousRecipeID", "previous_recipe"), ("nextRecipeID", "next_recipe")):
            if _identifier(data.get(field)):
                self._entity("recipe", data[field], role, f"data.{field}")
        if _identifier(data.get("profession_id")):
            self._entity("profession", data["profession_id"], "profession", "data.profession_id")
        if _identifier(data.get("output_item_id")):
            self._entity("item", data["output_item_id"], "recipe_output", "data.output_item_id")
        if isinstance(data.get("quality_item_ids"), list):
            for index, identity in enumerate(data["quality_item_ids"]):
                if _identifier(identity):
                    self._entity("item", identity, "recipe_quality_output", f"data.quality_item_ids[{index}]")
        if isinstance(data.get("recipe_ids"), list):
            for index, identity in enumerate(data["recipe_ids"]):
                if _identifier(identity):
                    self._entity("recipe", identity, "scanned_recipe", f"data.recipe_ids[{index}]")
        for index, slot in _rows(data.get("reagent_slots")):
            for reagent_index, row in _rows(slot.get("reagents")):
                path = f"data.reagent_slots[{index}].reagents[{reagent_index}]"
                self._item(row, path, "recipe_reagent")
                self._currency(row, path, "recipe_reagent", "currencyID")
            for quantity_index, variable in _rows(slot.get("variable_quantities")):
                row = variable.get("reagent")
                if isinstance(row, dict):
                    path = f"data.reagent_slots[{index}].variable_quantities[{quantity_index}].reagent"
                    self._item(row, path, "recipe_reagent")
                    self._currency(row, path, "recipe_reagent", "currencyID")

    def add(self, context_id: str, observation: dict) -> list[dict]:
        self._context = context_id
        self._source  = observation["observation_id"]
        self._kind    = observation["kind"]
        self._session = observation["session_id"]
        self._refs    = []
        self._seen    = set()
        data          = observation.get("data", {})
        self._map(observation.get("location"))
        if not isinstance(data, dict):
            return self._refs
        if self._kind == "unit.sighting":
            self._unit(data, "data", "observed_npc")
        for field, role in (
            ("npc", "observed_npc"), ("dialogue_npc", "historical_npc"),
            ("target", "spell_target"), ("target_candidate", "loot_candidate"),
            ("mouseover_candidate", "loot_candidate"),
        ):
            if self._kind == "gathering.attempt" and field == "target_candidate":
                role = "gathering_target_candidate"
            unit = self._unit(data.get(field), f"data.{field}", role)
            if field == "npc" and self._kind == "interaction.snapshot" and isinstance(data.get("service"), str):
                self._fact(unit, "data", {"service": data["service"], "scope": data.get("scope")}, "npc.service")
        item = self._item(data, "data", "item")
        if item is not None and self._kind == "item.metadata":
            for field in ("effect_spell_id", "use_spell_id", "equip_spell_id", "item_spell_id"):
                if _identifier(data.get(field)):
                    spell = self._entity("spell", data[field], field, f"data.{field}")
                    info  = {"spell_id": data[field]}
                    if field == "item_spell_id" and isinstance(data.get("item_spell_name"), str):
                        info["name"] = data["item_spell_name"]
                    self._fact(spell, f"data.{field}", info, "item.spell")
                    self._display(spell, info)
            for index, gem in _rows(data.get("gems")):
                self._item(gem, f"data.gems[{index}]", "socketed_gem")
        self._loot(data, item)
        self._quest(data, "data", "quest")
        self._spell(data, "data", "spell")
        self._currency(data, "data", "currency")
        if self._kind == "merchant.offer":
            self._spell(data, "data", "vendor_spell", "spellID")
            self._currency(data, "data", "vendor_currency", "currencyID")
        for field, role in (
            ("resolved_spell_id", "resolved_spell"), ("base_spell_id", "base_spell"),
            ("override_spell_id", "override_spell"),
        ):
            if _identifier(data.get(field)):
                self._entity("spell", data[field], role, f"data.{field}")
        if _identifier(data.get("quest_start_item_id")):
            self._entity("item", data["quest_start_item_id"], "quest_start_item", "data.quest_start_item_id")
        for field, role in (
            ("rewards", "reward"), ("choices", "reward_choice"),
            ("required_items", "required_item"), ("items", "inventory_item"),
            ("costs", "vendor_cost"),
        ):
            for index, row in _rows(data.get(field)):
                path = f"data.{field}[{index}]"
                self._item(row, path, role)
                self._currency(row, path, role, "currency_id")
                self._currency(row, path, role, "currencyID")
        for field, role in (("available_quests", "offered_quest"), ("active_quests", "active_quest")):
            for index, row in _rows(data.get(field)):
                self._quest(row, f"data.{field}[{index}]", role, "questID")
        for index, row in _rows(data.get("options")):
            if _identifier(row.get("spellID")):
                self._entity("spell", row["spellID"], "gossip_option_spell", f"data.options[{index}].spellID")
        if self._kind.startswith("spellbook."):
            self._spellbook(data)
        if self._kind.startswith("talent."):
            self._talent(data)
        if self._kind.startswith("recipe."):
            self._recipe(data)
        if self._kind == "profession.snapshot":
            for field, role in (("professionID", "profession"), ("parentProfessionID", "parent_profession")):
                if _identifier(data.get(field)):
                    entity = self._entity("profession", data[field], role, f"data.{field}")
                    if field == "professionID":
                        self._fact(entity, "data", data)
                        self._display(entity, data, 80)
        return self._refs

    def finish(self) -> dict[str, list[dict]]:
        result = {bucket: [] for kind, bucket in BUCKETS.items() if kind != "object"}
        for key in sorted(self._entities):
            source = self._entities[key]
            entity = {field: copy.deepcopy(value) for field, value in source.items()
                      if field not in {"facts", "variants", "sourceIds", "_display_rank"}}
            entity["sourceIds"] = sorted(source["sourceIds"])
            entity["facts"]     = []
            for fact_id in sorted(source["facts"]):
                fact              = copy.deepcopy(source["facts"][fact_id])
                fact["sourceIds"] = sorted(fact["sourceIds"])
                entity["facts"].append(fact)
            if "variants" in source:
                entity["variants"] = []
                for variant_id in sorted(source["variants"]):
                    variant              = copy.deepcopy(source["variants"][variant_id])
                    variant["sourceIds"] = sorted(variant["sourceIds"])
                    entity["variants"].append(variant)
            result.setdefault(BUCKETS[entity["kind"]], []).append(entity)
        return result
