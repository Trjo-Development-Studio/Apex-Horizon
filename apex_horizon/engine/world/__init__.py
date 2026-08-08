"""The world database and its generation — Design Bible Volumes 32 to 36.

Volume 32 defines the naming standards, Volume 33 the structure of each database
category, Volume 34 how a save's world is assembled from them, Volume 35 the
content generated during play, and Volume 36 the pipeline tying them together:
the Design Bible defines the rules, and the implementation generates the content
against them.
"""

from .entities import (
    Bank,
    City,
    Company,
    NewsAgency,
    Organisation,
    Person,
    University,
    World,
)
from .generation import WorldGenerator, generate_world
from .industries import ALL_INDUSTRIES, INDUSTRY_NAMING, Industry, IndustryNaming, naming_for
from .names import SCOPE_CITY, SCOPE_ORGANISATION, SCOPE_PERSON, NameGenerator

__all__ = [
    "ALL_INDUSTRIES",
    "INDUSTRY_NAMING",
    "SCOPE_CITY",
    "SCOPE_ORGANISATION",
    "SCOPE_PERSON",
    "Bank",
    "City",
    "Company",
    "Industry",
    "IndustryNaming",
    "NameGenerator",
    "NewsAgency",
    "Organisation",
    "Person",
    "University",
    "World",
    "WorldGenerator",
    "generate_world",
    "naming_for",
]
