"""Developer commands that grant and remove unlocks (V15.18)."""

from __future__ import annotations

from .base import _dependent_chain, _prerequisite_chain, _resolve_unlock, no


class UnlockCommands:
    """``unlocks`` and ``unlock``, mixed into :class:`DeveloperCommands`."""

    # -- unlocks -----------------------------------------------------------
    def _unlocks(self, *args: str) -> str:
        if args:
            return no("Invalid syntax. Use 'unlocks' on its own.")
        tree = self.context.unlocks
        if tree is None:
            return no("No game is running.")
        owned = [unlock for unlock in tree.all if tree.has(unlock.key)]
        if not owned:
            return "Nothing is unlocked."
        lines = [f"Unlocked ({len(owned)} of {len(tree.all)}):"]
        width = max(len(unlock.key) for unlock in owned)
        lines += [f"  {unlock.key.ljust(width)}   {unlock.name}" for unlock in owned]
        return "\n".join(lines)

    def _unlock(self, *args: str) -> str:
        tree = self.context.unlocks
        if tree is None:
            return no("No game is running.")
        if not args or args[0].lower() not in ("add", "remove"):
            return no("Invalid syntax. Use 'help unlocks' for the exact syntax.")
        action, name = args[0].lower(), " ".join(args[1:])
        if not name:
            return no(f"Invalid syntax. Use 'unlock {action} {{unlock_name}}'.")
        if action == "add" and name.lower() == "all":
            for unlock in tree.all:
                if unlock.implemented:
                    tree.unlock(unlock.key)
            self._apply_effects()
            self.changed()
            return f"Granted every unlock ({len(tree.unlocked)} of {len(tree.all)})."

        key = _resolve_unlock(tree, name)
        if key is None:
            return no(f"Unknown unlock: {name}")
        return self._unlock_add(tree, key) if action == "add" \
            else self._unlock_remove(tree, key)

    def _unlock_add(self, tree, key: str) -> str:
        unlock = tree.by_key[key]
        if tree.has(key):
            return no(f"{unlock.name} is already unlocked.")
        if not unlock.implemented:
            return no(
                f"{unlock.name} arrives with the system it opens, in a later "
                "version of the game."
            )
        # V6.9 makes progression sequential, so granting a deep unlock without
        # what it requires would leave the tree in a state the game never
        # produces. Grant the chain instead, and say so.
        needed = _prerequisite_chain(tree, key)
        for requirement in needed:
            tree.unlock(requirement)
        tree.unlock(key)
        self._apply_effects()
        self.changed()
        if not needed:
            return f"Unlocked {unlock.name}."
        also = ", ".join(tree.by_key[requirement].name for requirement in needed)
        return f"Unlocked {unlock.name}, and what it required: {also}."

    def _unlock_remove(self, tree, key: str) -> str:
        unlock = tree.by_key[key]
        if unlock.owned_at_start:
            return no(
                f"{unlock.name} is granted to every player at the start (V6.4) "
                "and cannot be removed."
            )
        if not tree.has(key):
            return no(f"{unlock.name} is not unlocked.")
        # Removing a prerequisite would strand everything built on top of it, so
        # those come out too rather than leaving an impossible tree behind.
        dependents = _dependent_chain(tree, key)
        for dependent in dependents:
            tree.unlocked.discard(dependent)
        tree.unlocked.discard(key)
        self._apply_effects()
        self.changed()
        if not dependents:
            return f"Removed {unlock.name}."
        also = ", ".join(tree.by_key[dependent].name for dependent in dependents)
        return f"Removed {unlock.name}, and what depended on it: {also}."

    def _apply_effects(self) -> None:
        """Push the tree's consequences back into the systems it configures."""
        effects = getattr(self.app, "effects", None)
        if effects is None:
            from ...engine.unlocks import UnlockEffects

            effects = UnlockEffects(self.context.unlocks)
        effects.apply(self.context)
