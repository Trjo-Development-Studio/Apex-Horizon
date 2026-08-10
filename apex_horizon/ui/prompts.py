"""The modal dialogs shown before an irreversible action.

Split out of :mod:`.app` (2026-08-10) to keep that file within the size the
project works to. A mixin rather than free functions, so every prompt still
reads ``self.popups`` and ``self.context`` exactly as it did when it was one
of GameApp's own methods — the split is about file size, not about changing
how a confirmation behaves.

They all share one shape: build a popup, hand it to the manager, and let the
action the player chooses call back into the system that owns the decision.
Nothing here decides anything itself (V15.5).
"""

from __future__ import annotations

import pygame

from .popups import Popup, PopupAction, PromptPopup


class AppPrompts:
    """The confirmation and prompt dialogs, mixed into :class:`GameApp`."""

    def _prompt_dismiss(self, roster, employee) -> None:
        popup = Popup(
            title=f"Dismiss {employee.name}?",
            message="They will leave the company immediately. This cannot be undone.",
            actions=[PopupAction("cancel", "Cancel"),
                     PopupAction("dismiss", "Dismiss", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice != "dismiss":
                return
            ok, message = roster.fire(employee)
            self.notifications.push(message, pygame.time.get_ticks(), emphasis=not ok)
            if ok:
                self.saves.mark_changed()
                self.navigate("company:employees")

        self.popups.open(popup, on_choice)

    def _prompt_found_company(self) -> None:
        """Ask the player to name their company (V3.3).

        Founding is refused here rather than at the button so the player is told
        *why* — needing the Create Company unlock (V6.2) reads as progression,
        while a dead button reads as a broken screen (V14.26).
        """
        player = self.context.player
        allowed, reason = player.can_found_company()
        if not allowed:
            self.notifications.push(reason, pygame.time.get_ticks(), emphasis=True)
            return
        popup = PromptPopup(
            title="Found your company",
            message=(
                f"Founding costs {player.founding_cost.format(decimals=0)}, which becomes "
                "your company's opening capital. Choose a name."
            ),
            placeholder="Company name",
            actions=[PopupAction("cancel", "Cancel"), PopupAction("found", "Found", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice != "found":
                return
            name = popup.text.strip()
            company, message = player.found_company(name, self.context.engine.date.day)
            self.notifications.push(message, pygame.time.get_ticks(), emphasis=company is not None)
            if company is not None:
                company.attach_market(self.context.market, self.context.allocator)
                company.register(self.context.engine)
                # A new company starts at whatever level the tree already grants.
                self.effects.apply(self.context)
                self._observe_company(company)
                # Founding is a major decision, so the moment before it is kept
                # (V16.6) and the game is marked as having unsaved changes.
                self.saves.mark_changed()

        self.popups.open(popup, on_choice)

    def _prompt_trade(self, action: str, company_id: str) -> None:
        """Buy or sell shares with the player's own money (V1.19, V3.4)."""
        portfolio = self.context.portfolio
        record = self.context.world.company_by_id(company_id)
        listing = self.context.market.listing_for(company_id)
        if portfolio is None or record is None or listing is None:
            return

        buying = action == "buy"
        if buying:
            limit = portfolio.max_affordable(company_id)
            message = (
                f"{record.name} trades at {listing.price.format()}. "
                f"You can afford {limit:,} shares."
            )
        else:
            limit = portfolio.shares_of(company_id)
            message = (
                f"{record.name} trades at {listing.price.format()}. "
                f"You hold {limit:,} shares."
            )
        popup = PromptPopup(
            title=f"{'Buy' if buying else 'Sell'} {record.name}",
            message=message,
            placeholder="Number of shares",
            actions=[
                PopupAction("cancel", "Cancel"),
                PopupAction(action, "Buy" if buying else "Sell", primary=True),
            ],
        )

        def on_choice(choice: str) -> None:
            if choice != action:
                return
            try:
                shares = int(popup.text.strip().replace(",", ""))
            except ValueError:
                self.notifications.push("Enter a number of shares.",
                                        pygame.time.get_ticks(), emphasis=True)
                return
            day = self.context.engine.date.day
            ok, result = (portfolio.buy(company_id, shares, day) if buying
                          else portfolio.sell(company_id, shares, day))
            self.notifications.push(result, pygame.time.get_ticks(), emphasis=not ok)
            if ok:
                self.saves.mark_changed()

        self.popups.open(popup, on_choice)

    def _prompt_acquire(self, company_id: str) -> None:
        """Buy a company outright, in company cash (V12.4, V12.22).

        Acquiring is permanent and paid for in full, so it is exactly the kind
        of irreversible decision V16.6 wants the moment before kept for.
        """
        company = self.context.company
        book = getattr(company, "subsidiaries", None)
        record = self.context.world.company_by_id(company_id)
        if book is None or record is None:
            return
        allowed, reason = book.can_acquire(company_id)
        if not allowed:
            self.notifications.push(reason, pygame.time.get_ticks(), emphasis=True)
            return

        price = book.price_of(company_id)
        popup = Popup(
            title=f"Acquire {record.name}",
            message=(
                f"{record.name} would cost {price.format(decimals=0)}, paid in full "
                f"from company cash. It becomes a subsidiary, keeps operating in "
                f"{record.industry.value}, and stops trading on the market.\n\n"
                "This cannot be undone."
            ),
            actions=[
                PopupAction("cancel", "Cancel"),
                PopupAction("acquire", "Acquire", primary=True),
            ],
        )

        def on_choice(choice: str) -> None:
            if choice != "acquire":
                return
            self.saves.autosave_before(f"acquiring {record.name}")
            subsidiary, message = book.acquire(company_id, self.context.engine.date.day)
            self.notifications.push(message, pygame.time.get_ticks(),
                                    emphasis=subsidiary is not None)
            if subsidiary is not None:
                self.saves.mark_changed()
                self.navigate("company:subsidiaries")

        self.popups.open(popup, on_choice)

    def _prompt_open_fund(self) -> None:
        """Name and open an investment fund (V11.6)."""
        company = self.context.company
        book = getattr(company, "funds", None)
        if book is None:
            return
        allowed, reason = book.can_create()
        if not allowed:
            self.notifications.push(reason, pygame.time.get_ticks(), emphasis=True)
            return

        popup = PromptPopup(
            title="Open an investment fund",
            message=(
                "A fund invests money entrusted by outside investors. That money "
                "is theirs, not yours — your company earns a fee for managing it "
                "well. Choose a name."
            ),
            placeholder="Fund name",
            actions=[PopupAction("cancel", "Cancel"),
                     PopupAction("open", "Open", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice != "open":
                return
            fund, message = book.create(popup.text.strip(), self.context.engine.date.day)
            self.notifications.push(message, pygame.time.get_ticks(),
                                    emphasis=fund is not None)
            if fund is not None:
                fund.register(self.context.engine)
                self.saves.mark_changed()

        self.popups.open(popup, on_choice)

    def _prompt_automation_criteria(self, roster) -> None:
        """Set the minimum skill Automated Recruitment hires to (V5.26).

        The player's own bar, not a hidden one — automation hires exactly
        who this number says and no one else.
        """
        popup = PromptPopup(
            title="Automated Recruitment criteria",
            message="Hire any candidate whose overall skill is at least:",
            placeholder="Minimum skill",
            text=str(roster.auto_recruit_minimum_skill),
            max_length=4,
            actions=[PopupAction("cancel", "Cancel"),
                     PopupAction("set", "Set", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice != "set":
                return
            try:
                minimum_skill = int(popup.text.strip())
            except ValueError:
                self.notifications.push("Enter a whole number.", pygame.time.get_ticks(),
                                        emphasis=True)
                return
            ok, message = roster.set_automation(
                roster.auto_recruit_enabled, minimum_skill, self.context.engine.date.day,
            )
            self.notifications.push(message, pygame.time.get_ticks(), emphasis=not ok)
            if ok:
                self.saves.mark_changed()

        self.popups.open(popup, on_choice)

    def _prompt_unlock(self, key: str) -> None:
        """Buy an unlock with personal cash (V6.2)."""
        player = self.context.player
        tree = self.context.unlocks
        if tree is None:
            return
        unlock = tree.by_key.get(key)
        if unlock is None:
            return
        allowed, reason = tree.can_purchase(key, player.cash)
        if not allowed:
            self.notifications.push(reason, pygame.time.get_ticks(), emphasis=True)
            return

        cost = tree.cost_of(key)
        popup = Popup(
            title=f"Unlock {unlock.name}",
            message=f"{unlock.description}\n\nThis costs {cost.format(decimals=0)}.",
            actions=[
                PopupAction("cancel", "Cancel"),
                PopupAction("unlock", "Unlock", primary=True),
            ],
        )

        def on_choice(choice: str) -> None:
            if choice != "unlock":
                return
            # Re-check: time keeps running while a popup is open only for the
            # simulation the player paused, so cash may have changed.
            allowed, reason = tree.can_purchase(key, player.cash)
            if not allowed:
                self.notifications.push(reason, pygame.time.get_ticks(), emphasis=True)
                return
            player.cash = player.cash - tree.cost_of(key)
            tree.unlock(key)
            self.effects.apply(self.context)
            self.notifications.push(f"{unlock.name} unlocked.",
                                    pygame.time.get_ticks(), emphasis=True)
            self.saves.mark_changed()

        self.popups.open(popup, on_choice)

    def _prompt_load(self, slot: str) -> None:
        """Confirm before replacing the running game with a saved one."""
        info = self.saves.store.info(slot)
        popup = Popup(
            title=f"Load {info.label}?",
            message=f"{info.describe()} This will replace your current game.",
            actions=[PopupAction("cancel", "Cancel"),
                     PopupAction("load", "Load", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice != "load":
                return
            outcome = self.saves.load_from_slot(slot)
            if outcome.ok:
                self._rebind_after_load()
                self.notifications.push(f"Loaded {info.label}.", pygame.time.get_ticks())
            elif outcome.needs_confirmation:
                # V16.14: repair did not succeed, so the player is asked whether
                # to attempt the load anyway rather than simply refused.
                self._prompt_damaged_load(slot, outcome.describe())
            else:
                self.notifications.push(
                    f"Could not load: {outcome.describe()}",
                    pygame.time.get_ticks(), emphasis=True,
                )

        self.popups.open(popup, on_choice)

    def _prompt_damaged_load(self, slot: str, problem: str) -> None:
        popup = Popup(
            title="This save is damaged",
            message=f"{problem} Would you like to try loading it anyway?",
            actions=[PopupAction("cancel", "Cancel"),
                     PopupAction("try", "Try anyway", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice != "try":
                return
            outcome = self.saves.load_from_slot(slot, allow_damaged=True)
            if outcome.ok:
                self._rebind_after_load()
            self.notifications.push(
                outcome.describe() if outcome.ok else f"Could not load: {outcome.describe()}",
                pygame.time.get_ticks(), emphasis=not outcome.ok,
            )

        self.popups.open(popup, on_choice)

    def _prompt_exit(self) -> None:
        """The Save & Exit workflow of V16.4.

        Selecting it pauses the simulation, attempts the save, and only leaves
        if that succeeds; a failed save returns the player to the running game
        with an error so another attempt can be made, rather than losing the
        session.
        """
        slot = self.saves.slot
        where = self.saves.store.info(slot).label if slot else "its save slot"
        popup = Popup(
            title="Save & Exit",
            message=f"Your game will be saved to {where} before leaving.",
            actions=[PopupAction("stay", "Keep playing"),
                     PopupAction("exit", "Save & Exit", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice != "exit":
                return
            result = self.saves.save()
            if result.ok:
                self._return_to_menu(f"Saved to {where}.")
            else:
                self.popups.open(Popup(
                    title="Saving failed",
                    message=f"{result.message} Your game has not been closed.",
                    actions=[PopupAction("ok", "Continue playing", primary=True)],
                ))

        self.popups.open(popup, on_choice)

    def _prompt_new_game_name(self, slot: str) -> None:
        """Name the save before the world exists (V16.16)."""
        label = self.saves.store.info(slot).label
        popup = PromptPopup(
            title=f"New game in {label}",
            message=(
                "Give this game a name. It is how you will recognise it in the "
                "menu, and it stays with this slot."
            ),
            placeholder="Save name",
            actions=[PopupAction("cancel", "Cancel"),
                     PopupAction("create", "Create Game", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice == "create" and popup.text.strip():
                self._start_new_game(slot, popup.text.strip())

        self.popups.open(popup, on_choice)
