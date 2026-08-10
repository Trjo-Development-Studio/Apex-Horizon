"""Helpers shared by the Save System tests."""

from __future__ import annotations

from apex_horizon.engine.save import SaveDocument, SaveMetadata, SaveSummary


def sample_document() -> SaveDocument:
    return SaveDocument(
        metadata=SaveMetadata(name="Meridian Capital"),
        summary=SaveSummary(money="1000", net_worth="2500", year=3, month=8, week=2, day=4),
        state={"engine": {}, "world": {}, "market": {}, "economy": {}, "player": {}},
    )
