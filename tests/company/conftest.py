"""Fixtures for the company and finance tests (Volumes 3 and 17)."""

from __future__ import annotations

import pytest

from apex_horizon.engine.values import Calendar, set_calendar


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12))
    yield
    set_calendar(None)
