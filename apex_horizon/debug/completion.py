"""Suggestions for the developer console, built from the commands themselves.

Every developer command already declares its exact syntax, one line per usable
form — ``money player add {amount}``, ``time set {year} {month} {week} {day}``
— because the help text is generated from it. That is a complete grammar, so
this module reads it rather than restating it: there is one command table, and
adding a command or changing its syntax updates the suggestions with it. There
is no second parser and no second list of unlock names anywhere here.

The grammar is held as a trie of tokens. Walking it with the words already
typed says exactly what may come next at that position, which is what makes a
suggestion context-aware instead of a search across command names: after
``money`` only ``player`` and ``company`` are offered, and after
``money player add`` nothing is offered but the amount it is waiting for.

Placeholders are shown rather than completed, except where the game itself
knows the answers: ``{unlock_name}`` is completed from the live unlock
catalogue, so an unlock added to or removed from the tree appears or vanishes
here with no change to this file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Units ``time add`` accepts, in the order its own syntax names them.
TIME_UNITS = ("year", "month", "week", "day")

_ALTERNATIVES = re.compile(r"^\{([a-z]+(?:\|[a-z]+)+)\}$")


@dataclass(frozen=True)
class Suggestion:
    """One thing the player could type next."""

    text: str
    #: What it does, where the grammar says so unambiguously.
    hint: str = ""
    #: True for a placeholder such as ``{amount}``: shown so the player knows
    #: what is expected, but never inserted — there is nothing to insert.
    placeholder: bool = False

    @property
    def acceptable(self) -> bool:
        return not self.placeholder


@dataclass
class _Node:
    children: dict[str, _Node] = field(default_factory=dict)
    #: Description of the syntax line that ends here, if one does.
    terminal: str = ""
    #: Descriptions of every line passing through, for a one-line hint.
    passing: list[str] = field(default_factory=list)

    @property
    def hint(self) -> str:
        if self.terminal:
            return self.terminal
        unique = set(self.passing)
        return self.passing[0] if len(unique) == 1 else ""


def _expand(tokens: list[str]) -> list[list[str]]:
    """Turn ``{up|down}`` into separate concrete lines, one per alternative."""
    for index, token in enumerate(tokens):
        match = _ALTERNATIVES.match(token)
        if match:
            return [
                expanded
                for option in match.group(1).split("|")
                for expanded in _expand([*tokens[:index], option, *tokens[index + 1:]])
            ]
    return [tokens]


def is_placeholder(token: str) -> bool:
    return token.startswith("{") and token.endswith("}")


class CommandGrammar:
    """What may be typed next, derived from the command table's own syntax."""

    def __init__(self, commands) -> None:
        self.commands = commands
        self.root = _Node()
        for command in commands.commands.values():
            for line, description in command.syntax:
                for tokens in _expand(line.split()):
                    self._add(tokens, description)

    def _add(self, tokens: list[str], description: str) -> None:
        node = self.root
        for token in tokens:
            node = node.children.setdefault(token, _Node())
            node.passing.append(description)
        node.terminal = description

    # -- walking -----------------------------------------------------------
    def _walk(self, typed: list[str]) -> _Node | None:
        """The node reached by the words already finished, or None if there is
        no such command — in which case nothing should be suggested at all."""
        node = self.root
        for word in typed:
            lowered = word.lower()
            if lowered in node.children:
                node = node.children[lowered]
                continue
            # Not a literal: it can only be a value for a placeholder here.
            values = [child for name, child in node.children.items()
                      if is_placeholder(name)]
            if not values:
                return None
            node = values[0]
        return node

    def _unlock_keys(self) -> list[str]:
        """Every unlock the catalogue currently holds. Never a copy of it."""
        context = getattr(self.commands, "context", None)
        tree = getattr(context, "unlocks", None) if context is not None else None
        if tree is None:
            return []
        return sorted(unlock.key for unlock in tree.all)

    def _values_for(self, token: str, prefix: str, hint: str) -> list[Suggestion]:
        """What a placeholder offers: real answers where the game knows them."""
        if token == "{unlock_name}":
            return [
                Suggestion(key, "Unlock it, with anything it requires." if hint else "")
                for key in self._unlock_keys() if key.startswith(prefix)
            ]
        if token == "{amount}{unit}":
            # 'time add 5year': once a number is typed, the units it can carry
            # are the only sensible completions.
            digits = re.match(r"^(\d+)$", prefix)
            if digits:
                return [Suggestion(f"{digits.group(1)}{unit}", f"Add {digits.group(1)} {unit}s.")
                        for unit in TIME_UNITS]
        return [Suggestion(token, hint, placeholder=True)]

    # -- the interface the console uses ------------------------------------
    def token_span(self, text: str, cursor: int) -> tuple[int, int]:
        """Where the word under the cursor starts and ends.

        Completion replaces this span rather than appending to the line, which
        is what lets a suggestion be accepted with the cursor in the middle of
        a command.
        """
        start = text.rfind(" ", 0, cursor) + 1
        end = cursor
        while end < len(text) and text[end] != " ":
            end += 1
        return start, end

    def suggest(self, text: str, cursor: int | None = None) -> list[Suggestion]:
        """Everything valid at the cursor, narrowed by what is already typed."""
        if cursor is None:
            cursor = len(text)
        cursor = max(0, min(cursor, len(text)))
        start, _ = self.token_span(text, cursor)
        prefix = text[start:cursor].lower()
        typed = text[:start].split()

        node = self._walk(typed)
        if node is None:
            return []

        suggestions: list[Suggestion] = []
        for token, child in node.children.items():
            if is_placeholder(token):
                suggestions.extend(self._values_for(token, prefix, child.hint))
            elif token.startswith(prefix):
                suggestions.append(Suggestion(token, child.hint))
        # Literals first and alphabetical; a placeholder is a note about what is
        # expected, so it belongs at the end rather than among the choices.
        suggestions.sort(key=lambda item: (item.placeholder, item.text))
        return suggestions
