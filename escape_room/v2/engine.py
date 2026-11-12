"""Deterministic escape-room engine.

Python owns every rule: object visibility, inventory, prerequisites, lock codes
and win detection. The LLM never receives the codes and cannot change the state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from escape_room.v2.config import build_alias_index, load_config, match_alias
from escape_room.v2.state import new_state


@dataclass
class ActionResult:
    ok: bool
    facts: str
    state_changed: bool = False


class GameEngine:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or load_config()
        self.object_index = build_alias_index(self.config["objects"])
        self.item_index = build_alias_index(self.config["items"])
        self.state = self.reset()

    def reset(self) -> dict[str, Any]:
        self.state = new_state()
        flags: set[str] = set()
        for lock in self.config["locks"].values():
            flags.add(lock["opens_flag"])
        for obj in self.config["objects"].values():
            if obj.get("requires_flag"):
                flags.add(obj["requires_flag"])
        for item in self.config["items"].values():
            if item.get("requires_flag"):
                flags.add(item["requires_flag"])
        for targets in self.config["uses"].values():
            for use in targets.values():
                if use.get("sets_flag"):
                    flags.add(use["sets_flag"])
                if use.get("requires_flag_not"):
                    flags.add(use["requires_flag_not"])
        self.state["flags"] = {flag: False for flag in sorted(flags)}
        return self.state

    def _object(self, name: Any) -> str | None:
        return match_alias(name, self.object_index)

    def _item(self, name: Any) -> str | None:
        return match_alias(name, self.item_index)

    def _result(self, ok: bool, facts: str, changed: bool = False) -> ActionResult:
        return ActionResult(ok=ok, facts=facts, state_changed=changed)

    def _visible(self, flag: str | None) -> bool:
        return not flag or bool(self.state["flags"].get(flag))

    def _label(self, item: str) -> str:
        return self.config["items"][item].get("label", item.replace("_", " "))

    def _object_description(self, key: str) -> str:
        details = self.config["objects"][key]
        flags = self.state["flags"]
        if key == "drawer":
            if flags.get("drawer_open"):
                text = details["description_open"]
                if "brass_key" not in self.state["taken"]:
                    text += " " + details.get("open_with_item", "")
                else:
                    text += " " + details.get("open_empty", "")
            else:
                text = details["description_locked"]
        elif key == "panel" and "paper" in self.state["taken"]:
            text = details.get("empty_description", details["description"])
        elif key == "door" and flags.get("door_unlocked") and details.get("description_open"):
            text = details["description_open"]
        else:
            text = details["description"]
        for flag, appendix in details.get("flag_appendix", {}).items():
            if flags.get(flag):
                text = f"{text} {appendix}"
        return re.sub(r"\s+", " ", text).strip()

    def examine(self, target: Any) -> ActionResult:
        key = self._object(target)
        if key is None:
            item = self._item(target)
            if item is not None:
                return self.examine_item(item)
            return self._result(False, f"There is no '{target}' in this room.")

        details = self.config["objects"][key]
        required_examined = details.get("requires_examined")
        if required_examined and required_examined not in self.state["examined"]:
            return self._result(
                False,
                details.get("missing_message", "You cannot see that yet."),
            )
        required_flag = details.get("requires_flag")
        if not self._visible(required_flag):
            return self._result(
                False,
                details.get("missing_message", "You cannot see that yet."),
            )

        text = self._object_description(key)
        changed = key not in self.state["examined"]
        if changed:
            self.state["examined"].append(key)
        return self._result(True, text, changed)

    def examine_item(self, item: str) -> ActionResult:
        details = self.config["items"][item]
        if not self._visible(details.get("requires_flag")):
            return self._result(False, details.get("missing_message", "You cannot see that."))
        return self._result(True, details.get("examine_message", details.get("label", item)))

    def take(self, name: Any) -> ActionResult:
        item = self._item(name)
        if item is None:
            return self._result(False, f"There is no '{name}' that can be taken.")
        if item in self.state["inventory"]:
            return self._result(False, f"You already have the {self._label(item)}.")
        details = self.config["items"][item]
        if not self._visible(details.get("requires_flag")):
            return self._result(
                False,
                details.get("missing_message", "You cannot reach that yet."),
            )
        self.state["inventory"].append(item)
        if item not in self.state["taken"]:
            self.state["taken"].append(item)
        return self._result(True, details.get("take_message", f"You take the {self._label(item)}."), True)

    def use(self, name: Any, target: Any) -> ActionResult:
        item = self._item(name)
        if item is None or item not in self.state["inventory"]:
            label = self._label(item) if item else str(name)
            return self._result(False, f"You do not have the {label} in your inventory.")
        target_key = self._object(target)
        if target_key is None:
            return self._result(False, f"Using the {self._label(item)} on '{target}' does nothing.")
        use_rule = self.config["uses"].get(item, {}).get(target_key)
        if not use_rule:
            return self._result(
                False, f"Using the {self._label(item)} on the {target_key} does nothing."
            )
        blocked_by = use_rule.get("requires_flag_not")
        if blocked_by and self.state["flags"].get(blocked_by):
            return self._result(False, use_rule.get("already_message", "That is already done."))
        self.state["flags"][use_rule["sets_flag"]] = True
        return self._result(True, use_rule["success_message"], True)

    def enter_code(self, target: Any, code: Any) -> ActionResult:
        target_key = self._object(target)
        lock = self.config["locks"].get(target_key) if target_key else None
        if not lock:
            return self._result(False, "There is nothing with a code lock there.")
        if self.state["flags"].get(lock["opens_flag"]):
            return self._result(False, lock.get("already_open_message", "That is already open."))
        required_examined = lock.get("requires_examined")
        if required_examined and required_examined not in self.state["examined"]:
            return self._result(False, lock.get("no_clue_message", "You have no clue for that code."))
        required_item = lock.get("requires_item")
        if required_item and required_item not in self.state["inventory"]:
            return self._result(False, lock.get("no_clue_message", "You have no clue for that code."))

        digits = re.sub(r"\D", "", str(code or ""))
        if len(digits) != 4:
            return self._result(False, "A four-digit code is required.")
        if digits != lock["code"]:
            return self._result(False, lock.get("wrong_message", "Wrong code."))

        self.state["flags"][lock["opens_flag"]] = True
        if lock.get("wins"):
            self.state["escaped"] = True
        return self._result(True, lock["success_message"], True)

    def inventory(self) -> ActionResult:
        if not self.state["inventory"]:
            return self._result(True, "You are carrying nothing.")
        labels = [self._label(item) for item in self.state["inventory"]]
        return self._result(True, "You are carrying: " + ", ".join(labels) + ".")

    def hint(self) -> ActionResult:
        flags = self.state["flags"]
        if self.state["escaped"]:
            return self._result(True, "You have already escaped. Press Restart to play again.")
        if "bookshelf" not in self.state["examined"]:
            return self._result(True, "Start with the bookshelf. Four books are arranged oddly.")
        if "books" not in self.state["examined"]:
            return self._result(True, "Look closer at the four unusual books.")
        if not flags.get("drawer_open"):
            return self._result(
                True,
                "The desk letter mentions the order of the rainbow. The numbers in the four books "
                "may form the drawer code.",
            )
        if "brass_key" not in self.state["inventory"]:
            return self._result(True, "Take the brass key from the open drawer.")
        if not flags.get("panel_open"):
            return self._result(True, "Try the brass key on the painting's tiny keyhole.")
        if "paper" not in self.state["inventory"]:
            return self._result(True, "Take the paper from the hidden panel.")
        return self._result(True, "Read the paper and enter its four-digit code on the door keypad.")

    def status(self) -> dict[str, Any]:
        flags = self.state["flags"]
        return {
            "inventory": [self._label(item) for item in self.state["inventory"]],
            "drawer": "open" if flags.get("drawer_open") else "locked",
            "panel": "open" if flags.get("panel_open") else "hidden",
            "door": "open" if flags.get("door_unlocked") else "locked",
            "escaped": self.state["escaped"],
            "turns": self.state["turns"],
        }

    def apply(self, intent: dict[str, Any] | None) -> ActionResult:
        if self.state["escaped"]:
            return self._result(False, "The game is already over. You have escaped.")
        intent = intent if isinstance(intent, dict) else {}
        action = str(intent.get("action", "unknown")).strip().lower()
        target = intent.get("target")
        item = intent.get("item")
        self.state["turns"] += 1

        if action == "examine":
            result = self.examine(target if target is not None else item)
        elif action == "take":
            result = self.take(item if item is not None else target)
        elif action == "use":
            result = self.use(item, target)
        elif action == "enter_code":
            result = self.enter_code(target, intent.get("code"))
        elif action == "inventory":
            result = self.inventory()
        elif action == "hint":
            result = self.hint()
        elif action == "unknown":
            result = self._result(
                False, "That action is not possible or was not understood. No game state changed."
            )
        else:
            result = self._result(
                False, "That action is not possible or was not understood. No game state changed."
            )

        self.state["log"].append(
            {
                "turn": self.state["turns"],
                "action": action,
                "target": target,
                "item": item,
                "ok": result.ok,
            }
        )
        return result
