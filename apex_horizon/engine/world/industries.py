"""Industries and their naming identities.

Design Bible V32.7 requires every industry in the Market System to develop its
own recognisable naming identity, so that an experienced player can often infer
a company's industry from its name alone, before opening its page. It names the
twenty industries below and requires each to have a documented naming
philosophy maintained consistently as new entries are generated.

The Design Bible states the identity for four of them directly — Technology
favours short, modern, invented words or compressed compounds; Financial favours
solid, established-sounding words projecting trust and permanence; Healthcare
favours clarity and reassurance; Entertainment has more licence for personality
and flair. The remaining sixteen identities are documented here for the first
time, written to sit consistently alongside those four and to satisfy the
General Naming Rules of V32.5.

Names are composed from patterns rather than stored whole, which is what gives
the controlled variety described in V32.3: enough range that repetition is never
noticeable, from standards narrow enough that every result still belongs to the
same universe.

Pattern placeholders:
    ``{word}``     a shared corporate word family (V32.8)
    ``{noun}``     an industry noun from this industry's identity
    ``{invented}`` a short invented coinage
    ``{surname}``  a personal family name, for founder-style company names
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Industry(Enum):
    """The twenty industries listed in V32.7."""

    FOOD = "Food"
    TECHNOLOGY = "Technology"
    ENTERTAINMENT = "Entertainment"
    FINANCIAL = "Financial"
    MANAGEMENT = "Management"
    TRANSPORT = "Transport"
    ENERGY = "Energy"
    HEALTHCARE = "Healthcare"
    CONSTRUCTION = "Construction"
    RETAIL = "Retail"
    MANUFACTURING = "Manufacturing"
    TELECOMMUNICATIONS = "Telecommunications"
    AUTOMOTIVE = "Automotive"
    AEROSPACE = "Aerospace"
    MINING = "Mining"
    SHIPPING = "Shipping"
    PHARMACEUTICALS = "Pharmaceuticals"
    GAMING = "Gaming"
    HOSPITALITY = "Hospitality"
    MEDIA = "Media"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class IndustryNaming:
    """One industry's documented naming identity (V32.7)."""

    industry: Industry
    philosophy: str
    nouns: tuple[str, ...]
    patterns: tuple[str, ...]

    @property
    def combinations(self) -> int:
        """Rough count of distinct names this identity can produce."""
        return len(self.nouns) * len(self.patterns)


# Patterns shared by most industries: a corporate word family paired with an
# industry noun, which is the form the Design Bible's own example uses
# ("Meridian Robotics", V35.3), plus founder-style surnames.
#
# The qualifier always precedes the industry noun. Reversing them produces names
# like "Foods Marigold" or "Masonry Onward", which read as generated rather than
# chosen and so fail the "professional in tone" and "natural fit within the
# universe" rules of V32.5.
_STANDARD = ("{word} {noun}", "{word} {noun}", "{word} {noun}", "{surname} {noun}")
_INVENTED = ("{invented}", "{invented} {noun}", "{word} {noun}")
# Partnership names suit professional-services industries, where real firms are
# commonly named after their founders.
_PARTNERSHIP = ("{surname} & {surname} {noun}",)

INDUSTRY_NAMING: dict[Industry, IndustryNaming] = {
    Industry.TECHNOLOGY: IndustryNaming(
        Industry.TECHNOLOGY,
        # Stated directly in V32.7.
        "Short, modern, invented words or compressed compounds, reflecting the "
        "fast-moving tone of the industry.",
        ("Systems", "Robotics", "Labs", "Technologies", "Digital", "Compute",
         "Networks", "Data", "Software", "Analytics", "Devices", "Cloud"),
        (*_INVENTED, "{invented} Systems", "{invented} Labs"),
    ),
    Industry.FINANCIAL: IndustryNaming(
        Industry.FINANCIAL,
        # Stated directly in V32.7.
        "Solid, established-sounding words that project trust and permanence.",
        ("Capital", "Holdings", "Partners", "Financial Group", "Investments",
         "Asset Management", "Securities", "Advisors", "Wealth", "Equity"),
        (*_STANDARD, *_PARTNERSHIP),
    ),
    Industry.HEALTHCARE: IndustryNaming(
        Industry.HEALTHCARE,
        # Stated directly in V32.7.
        "Clarity and reassurance; names should read as competent and calm.",
        ("Health", "Healthcare", "Medical", "Care Group", "Clinics",
         "Health Systems", "Diagnostics", "Wellness", "Medical Group"),
        _STANDARD,
    ),
    Industry.ENTERTAINMENT: IndustryNaming(
        Industry.ENTERTAINMENT,
        # Stated directly in V32.7.
        "More licence for personality and flair than any other identity, while "
        "staying professional rather than comedic.",
        ("Entertainment", "Studios", "Pictures", "Productions", "Live",
         "Stage", "Spotlight", "Theatrical", "Arts"),
        (*_STANDARD, "{invented} Studios"),
    ),
    Industry.FOOD: IndustryNaming(
        Industry.FOOD,
        "Warm, wholesome and grounded; names should suggest provenance and "
        "quality rather than novelty.",
        ("Foods", "Farms", "Provisions", "Kitchens", "Harvest", "Orchards",
         "Grocers", "Fine Foods", "Bakeries", "Produce"),
        _STANDARD,
    ),
    Industry.MANAGEMENT: IndustryNaming(
        Industry.MANAGEMENT,
        "Measured and professional, echoing the Financial identity's trust "
        "without its explicit money vocabulary.",
        ("Group", "Consulting", "Advisory", "Management", "Partners",
         "Associates", "Strategies", "Solutions", "Enterprises"),
        (*_STANDARD, *_PARTNERSHIP),
    ),
    Industry.TRANSPORT: IndustryNaming(
        Industry.TRANSPORT,
        "Movement and reliability; names should sound punctual and far-reaching.",
        ("Transport", "Logistics", "Freight", "Haulage", "Express",
         "Distribution", "Rail", "Transit", "Carriers"),
        _STANDARD,
    ),
    Industry.ENERGY: IndustryNaming(
        Industry.ENERGY,
        "Scale and permanence, drawing on natural and elemental imagery.",
        ("Energy", "Power", "Utilities", "Renewables", "Grid", "Petroleum",
         "Solar", "Wind Power", "Hydro", "Resources"),
        _STANDARD,
    ),
    Industry.CONSTRUCTION: IndustryNaming(
        Industry.CONSTRUCTION,
        "Solidity and craft; heavy, dependable words suit this identity.",
        ("Construction", "Builders", "Contracting", "Structures", "Civil Works",
         "Developments", "Engineering", "Masonry", "Infrastructure"),
        _STANDARD,
    ),
    Industry.RETAIL: IndustryNaming(
        Industry.RETAIL,
        "Approachable and everyday, without becoming casual or jokey.",
        ("Retail", "Stores", "Markets", "Trading", "Outfitters", "Emporium",
         "Merchants", "Goods", "Supply Co"),
        _STANDARD,
    ),
    Industry.MANUFACTURING: IndustryNaming(
        Industry.MANUFACTURING,
        "Industrial and precise; names should sound like they make real things.",
        ("Manufacturing", "Industries", "Works", "Fabrication", "Components",
         "Machinery", "Foundries", "Products", "Assembly"),
        _STANDARD,
    ),
    Industry.TELECOMMUNICATIONS: IndustryNaming(
        Industry.TELECOMMUNICATIONS,
        "Connection and reach, sharing some of Technology's modernity but with "
        "steadier, more infrastructural words.",
        ("Telecom", "Communications", "Networks", "Connect", "Mobile",
         "Broadband", "Signal", "Wireless", "Telecommunications"),
        (*_STANDARD, "{invented} Telecom"),
    ),
    Industry.AUTOMOTIVE: IndustryNaming(
        Industry.AUTOMOTIVE,
        "Engineering confidence and motion; often founder-style surnames, as "
        "the real industry's heritage suggests.",
        ("Motors", "Automotive", "Vehicles", "Motor Works", "Drive Systems",
         "Autoworks", "Engines", "Mobility"),
        ("{surname} {noun}", "{word} {noun}", "{surname} {noun}", "{surname} {noun}"),
    ),
    Industry.AEROSPACE: IndustryNaming(
        Industry.AEROSPACE,
        "Precision and ambition, reaching upward; celestial and navigational "
        "words fit naturally.",
        ("Aerospace", "Aviation", "Aeronautics", "Air Systems", "Orbital",
         "Flight Systems", "Avionics", "Space Systems"),
        _STANDARD,
    ),
    Industry.MINING: IndustryNaming(
        Industry.MINING,
        "Weight and extraction; hard, mineral, geological words.",
        ("Mining", "Minerals", "Resources", "Ore", "Extraction", "Quarries",
         "Metals", "Geological", "Mining Group"),
        _STANDARD,
    ),
    Industry.SHIPPING: IndustryNaming(
        Industry.SHIPPING,
        "Maritime and long-haul; harbours, tides and navigation.",
        ("Shipping", "Maritime", "Lines", "Marine", "Seaways", "Cargo",
         "Port Services", "Shipping Lines"),
        _STANDARD,
    ),
    Industry.PHARMACEUTICALS: IndustryNaming(
        Industry.PHARMACEUTICALS,
        "Clinical and precise, blending Healthcare's reassurance with "
        "Technology's coined vocabulary.",
        ("Pharmaceuticals", "Therapeutics", "Biosciences", "Labs", "Pharma",
         "Bio", "Research Labs", "Medicines"),
        (*_INVENTED, "{invented} Therapeutics", "{word} Pharmaceuticals"),
    ),
    Industry.GAMING: IndustryNaming(
        Industry.GAMING,
        "Energetic and modern, close to Technology but with more play in it, "
        "while staying professional.",
        ("Games", "Interactive", "Studios", "Play", "Entertainment",
         "Game Works", "Digital Games"),
        (*_INVENTED, "{invented} Interactive", "{word} Games"),
    ),
    Industry.HOSPITALITY: IndustryNaming(
        Industry.HOSPITALITY,
        "Welcome and comfort; warm, place-like words that suggest somewhere to "
        "stay.",
        ("Hotels", "Hospitality", "Resorts", "Inns", "Lodging", "Suites",
         "Hotel Group", "Retreats"),
        _STANDARD,
    ),
    Industry.MEDIA: IndustryNaming(
        Industry.MEDIA,
        "Authority and reach; publishing and broadcast vocabulary that reads as "
        "credible, since news carries the world's voice (V33.10).",
        ("Media", "Broadcasting", "Publishing", "News Group", "Communications",
         "Networks", "Press", "Media Group"),
        _STANDARD,
    ),
}


def naming_for(industry: Industry) -> IndustryNaming:
    """The documented naming identity for ``industry``."""
    return INDUSTRY_NAMING[industry]


ALL_INDUSTRIES: tuple[Industry, ...] = tuple(Industry)
