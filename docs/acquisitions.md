# Acquisitions & Subsidiaries

Covers Design Bible **Volume 12**. Code lives in
`apex_horizon/engine/acquisitions/`, with the pages in
`apex_horizon/ui/pages/subsidiaries.py`.

---

## A subsidiary is an ownership reference

V12.23 asks for subsidiaries to be a *lightweight ownership wrapper* around the
same company data the market already lists, so acquiring a company mainly
changes an ownership reference rather than introducing a second model. The
world's `Company` already carried `owner_id` for exactly this, and that is what
an acquisition sets.

The `Subsidiary` record alongside it holds only what ownership adds: what was
paid, what it is worth now, and what it has paid up to its parent. Everything
else about the business — name, industry, headquarters, chief executive —
remains the one company record it always was.

---

## Buying a company

| Rule | Where |
|---|---|
| Company money only, never personal (V12.4, V1.4) | `finances.invest` on the company |
| Full price in cash, no financing at all (V12.22) | `can_acquire` refuses otherwise |
| Fails gracefully, never a negative balance (V12.21) | Refusal returns a reason |
| Not an expense — cash exchanged for an asset (V17.26) | Never touches profit |
| A later stage of growth (V12.15) | Requires `acquisitions.minimum_company_level` |

**Price** is the market's own valuation of the whole company plus a control
premium, since nobody sells control at the price of a single share. The Design
Bible gives no formula, so the premium is configuration.

**An acquired company is delisted** (project-manager ruling). Owning it outright
leaves nothing to trade, so it leaves the market the same way any company does
(V4.14) rather than through a second mechanism. New listings appear faster to
compensate.

---

## What a subsidiary does

V12.5: it keeps operating in its own industry and never merges into the parent.
Each month it pays its parent a share of what it is worth, and that share follows
its industry's fortunes — a healthy sector pays more, a declining one less, and
its valuation moves with it. That is what makes a poor acquisition genuinely
poor (V12.11) rather than merely smaller.

V12.21 deliberately leaves open what should happen to a subsidiary whose
industry enters a severe, sustained decline, because no mechanic for reselling
or divesting exists in the Design Bible. **So nothing else happens**: income
falls and value falls, and there is no way to sell. This is a known gap, not an
oversight.

Subsidiaries count toward company value through the same asset-provider hook
investments use, so `finances` never needs to know what a subsidiary is (V15.7,
V12.11, V17.12).

---

## AI companies acquire too

V12.14 requires it, and because AI companies are ordinary companies (V26.10)
they use the identical rules — same price, same cash-only requirement, same
company-level gate. A director considers an acquisition on its own cadence and
buys the largest business it can comfortably afford, because an acquisition
should feel significant rather than incidental (V12.3).

By project-manager ruling their acquisitions are gated by company size exactly
as the player's are, so the early market stays open while the player is still
building up.

---

## Two scale problems this exposed

Neither was an acquisitions bug; both were found because acquisitions were the
first system to compare company values against market values.

**Market capitalisations were fifty times too large.** Listed companies were
worth tens of billions while a mature investment company is worth single-digit
millions, so buying one outright could not have happened at any point in any
playthrough, at any level of success. Shares in issue were rescaled so the
cheapest listed companies cost around $10M — reachable by a long-running
company, while the median stays well beyond any single buyer.

**The cash reserve did not survive growth.** The investment system kept back a
flat $2,500, which is meaningful to a company founded with $25,000 and nothing
at all to one worth millions — such a company stayed permanently fully invested
and could never accumulate the cash an acquisition must be paid with. The
reserve is now the larger of that floor and a share of the whole portfolio.

Measuring the share against *cash* rather than the portfolio does not work, and
is worth recording: each investment shrinks the cash the next reserve is
computed from, so the reserve decays toward nothing and the company ends up
fully invested anyway.
