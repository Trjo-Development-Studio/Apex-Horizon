"""Developer commands that move money (V15.18)."""

from __future__ import annotations

from ...engine.values import Money
from .base import INVALID, _parse_amount, no


class MoneyCommands:
    """``money`` and its subcommands, mixed into :class:`DeveloperCommands`."""

    # -- money -------------------------------------------------------------
    def _money(self, *args: str) -> str:
        if not args:
            return no("Invalid syntax. Use 'help money' for the exact syntax.")
        target = args[0].lower()
        if target == "player":
            return self._money_player(args[1:])
        if target == "company":
            return self._money_company(args[1:])
        return no(f"Unknown target: {args[0]}. Use 'money player' or 'money company'.")

    def _money_player(self, args: tuple[str, ...]) -> str:
        player = self.context.player
        if player is None:
            return no("No game is running.")
        if not args:
            return f"Personal cash: {player.cash.format()}."
        action, amount, problem = self._money_arguments(args, "player")
        if amount is None:
            return problem or no(INVALID)
        before = player.cash
        if action == "set":
            player.cash = amount
        elif action == "add":
            player.cash = before + amount
        else:
            player.cash = before - amount
        self.changed()
        return (
            f"Personal cash: {player.cash.format()} "
            f"(was {before.format()})."
        )

    def _money_company(self, args: tuple[str, ...]) -> str:
        company = self.context.company
        if company is None:
            return no("No company currently exists.")
        finances = company.finances
        if not args:
            return f"{company.name} cash: {finances.cash.format()}."
        action, amount, problem = self._money_arguments(args, "company")
        if amount is None:
            return problem or no(INVALID)
        before = finances.cash
        if action == "set":
            amount = amount - before
            action = "add" if not amount.is_negative else "remove"
            amount = amount if not amount.is_negative else Money(-amount.amount)
        if amount.is_zero:
            return f"{company.name} cash is already {before.format()}."

        # Company money moves through the company's own books, so the ledger and
        # cash-flow statement stay honest about where it came from (V17.26).
        day = self.context.engine.date.day
        if action == "add":
            company.receive_capital(day, amount)
        else:
            from ...engine.company.ledger import ExpenseCategory

            finances.repay_financing(day, ExpenseCategory.OTHER, amount,
                                     "Developer console withdrawal")
        self.changed()
        return (
            f"{company.name} cash: {finances.cash.format()} "
            f"(was {before.format()})."
        )

    def _money_arguments(
        self, args: tuple[str, ...], target: str
    ) -> tuple[str, Money | None, str]:
        """Validate ``set|add|remove {amount}``, returning what to do or why not."""
        action = args[0].lower()
        if action not in ("set", "add", "remove"):
            return "", None, no(
                f"Unknown action: {args[0]}. Use set, add or remove — "
                f"'help money' shows the exact syntax."
            )
        if len(args) != 2:
            return "", None, no(
                f"Invalid syntax. Use 'money {target} {action} {{amount}}'.")
        amount, problem = _parse_amount(args[1])
        if amount is None:
            return "", None, problem
        if action != "set" and amount.is_negative:
            other = "remove" if action == "add" else "add"
            return "", None, no(
                f"Amounts cannot be negative. Use 'money {target} {other}' instead."
            )
        return action, amount, ""
