"""Curated word pools for world generation.

Design Bible V32.2 explains why Apex Horizon uses curated databases rather than a
random letter generator: randomness alone produces unpredictability, not
believability. These pools are the raw material from which every name in the
Alternative Earth (V24) is assembled, and every entry is intended to satisfy the
General Naming Rules of V32.5 — readable at a glance, pronounceable, memorable,
professional in tone, international in flavour, and free of joke names, real
brands, and meaningless letter combinations.

Nothing here is a name on its own. Names are composed by
:mod:`.names` using the industry patterns in :mod:`.industries`, which is what
produces controlled variety (V32.3): a wide enough range that repetition is
never noticeable, from standards narrow enough that every result still belongs
to the same universe.
"""

from __future__ import annotations

# Shared corporate words (V32.8). The first thirteen are the examples given in
# the Design Bible itself; the remainder follow the same register. V32.8 is
# explicit that unrelated companies may share these words — real corporate
# naming echoes itself across industries, and reusing them signals that these
# companies inhabit one shared linguistic world. No word family is ever the
# exclusive property of a single company.
CORPORATE_WORD_FAMILIES: tuple[str, ...] = (
    "Horizon", "Atlas", "Summit", "Meridian", "Skyline", "Keystone", "Evergreen",
    "Harbor", "Crown", "Frontier", "Prime", "Unity", "Pinnacle",
    "Anchor", "Apex", "Ardent", "Aurora", "Beacon", "Bedrock", "Bluepoint",
    "Bridgewater", "Cardinal", "Cascade", "Cedar", "Compass", "Cornerstone",
    "Crestline", "Dominion", "Eastgate", "Ember", "Endeavour", "Equinox",
    "Everline", "Falcon", "Fairmount", "Foundry", "Gateway", "Granite",
    "Greystone", "Guardian", "Halcyon", "Hallmark", "Haven", "Highland",
    "Ironwood", "Jubilee", "Kestrel", "Lantern", "Larkspur", "Legacy",
    "Lighthouse", "Longview", "Mainsail", "Marigold", "Merit", "Milestone",
    "Northgate", "Northwind", "Oakline", "Obelisk", "Onward", "Overland",
    "Palisade", "Paramount", "Pathfinder", "Pilgrim", "Polaris", "Providence",
    "Quarry", "Quill", "Redwood", "Regent", "Ridgeway", "Rivermark",
    "Sable", "Sentinel", "Silverline", "Solstice", "Southbank", "Stonebridge",
    "Sterling", "Stratford", "Tallgrass", "Tempest", "Thornhill", "Tidewater",
    "Trailhead", "Trident", "Vanguard", "Verity", "Vantage", "Wayfarer",
    "Westbrook", "Whitfield", "Wildwood", "Windsor", "Yardley", "Zenith",
)

# Fragments used to build short invented words, mainly for the Technology,
# Gaming and Pharmaceuticals identities where V32.7 calls for modern, compressed
# names. Combined they yield thousands of pronounceable coinages.
INVENTED_PREFIXES: tuple[str, ...] = (
    "Ael", "Alt", "Arc", "Aur", "Ax", "Bry", "Cal", "Cav", "Cel", "Cor",
    "Cy", "Del", "Dyn", "Ely", "Env", "Ep", "Ev", "Fen", "Flu", "Gal",
    "Hel", "Hex", "Ily", "Ink", "Ion", "Jun", "Kel", "Kir", "Lum", "Lyr",
    "Mar", "Mer", "Mod", "Nav", "Nex", "Nim", "Nov", "Ob", "Om", "Or",
    "Pol", "Pyr", "Quan", "Rev", "Rho", "Sav", "Sel", "Sol", "Syn", "Tel",
    "Ter", "Thal", "Tor", "Trin", "Val", "Ver", "Vex", "Vor", "Xan", "Zen",
)

INVENTED_SUFFIXES: tuple[str, ...] = (
    "ara", "aris", "eon", "ex", "ia", "ion", "is", "ix", "on", "ora",
    "os", "ova", "ra", "ris", "sys", "tec", "tis", "va", "yx", "za",
)

# -- People (V33.5, V33.6) ------------------------------------------------
# Personal names for CEOs and employees. V33.5 requires an internationally
# representative range, avoiding overrepresentation of any single naming
# tradition, and V33.6 notes employees and CEOs come from the same population.
GIVEN_NAMES: tuple[str, ...] = (
    "Adaeze", "Adrian", "Agnes", "Ahmed", "Aiko", "Alejandro", "Alice", "Amara",
    "Amelia", "Anders", "Andrea", "Aneta", "Anita", "Anton", "Arjun", "Astrid",
    "Ayana", "Beatriz", "Bilal", "Bo", "Camille", "Carlos", "Catalina", "Cecilia",
    "Chen", "Chidi", "Clara", "Damir", "Daniela", "Dario", "David", "Diego",
    "Dmitri", "Ebba", "Eleni", "Elias", "Elif", "Emeka", "Emil", "Emma",
    "Enrique", "Esther", "Fatima", "Felix", "Femi", "Fiona", "Franco", "Freja",
    "Gabriel", "Georgia", "Giulia", "Grace", "Hana", "Hannah", "Haruki", "Hassan",
    "Helena", "Henrik", "Hugo", "Ibrahim", "Ines", "Ingrid", "Isabel", "Ivan",
    "Jae", "Javier", "Jessica", "Joachim", "Johanna", "Jonas", "Julia", "Kaito",
    "Kamil", "Karin", "Katarina", "Kwame", "Laila", "Lars", "Laura", "Leila",
    "Leon", "Lian", "Lucas", "Lucia", "Magnus", "Maja", "Malik", "Marco",
    "Maria", "Mateo", "Mei", "Mikael", "Milan", "Mina", "Miriam", "Nadia",
    "Naomi", "Nikolai", "Nils", "Nina", "Noor", "Oliver", "Omar", "Oscar",
    "Paulo", "Petra", "Priya", "Rafael", "Rahel", "Ravi", "Rebecca", "Rina",
    "Rosa", "Ruben", "Sanne", "Sara", "Sebastian", "Selin", "Sergei", "Simon",
    "Sofia", "Soren", "Stefan", "Sunil", "Takeshi", "Tariq", "Tessa", "Thabo",
    "Theo", "Tomas", "Valeria", "Victor", "Vera", "Viktor", "Wei", "Wilhelm",
    "Yara", "Yosef", "Yuki", "Zainab", "Zara", "Zoltan",
)

FAMILY_NAMES: tuple[str, ...] = (
    "Abara", "Adeyemi", "Aguilar", "Ahmadi", "Almeida", "Andersen", "Antonov",
    "Arnold", "Bakker", "Baranov", "Bauer", "Beaumont", "Bergstrom", "Bianchi",
    "Blomqvist", "Boateng", "Bouchard", "Brennan", "Cabrera", "Calderon",
    "Carvalho", "Castellanos", "Chan", "Chowdhury", "Conti", "Costa", "Dahl",
    "Dalgaard", "Delacroix", "Demir", "Diallo", "Dubois", "Duarte", "Eriksen",
    "Esposito", "Falk", "Farooq", "Fernandes", "Fischer", "Fontaine", "Forsberg",
    "Gallagher", "Garrido", "Gonzalez", "Grimaldi", "Haddad", "Hakim", "Halvorsen",
    "Hansen", "Hartmann", "Hayashi", "Herrera", "Hoffman", "Ibarra", "Ikeda",
    "Ivanov", "Jansen", "Jimenez", "Kaminski", "Karlsson", "Kato", "Keller",
    "Khalil", "Kimura", "Kobayashi", "Kovac", "Kowalski", "Kristensen", "Kumar",
    "Laurent", "Leclerc", "Lindqvist", "Lombardi", "Lorenzen", "Maartens",
    "Madsen", "Marchetti", "Marino", "Martinez", "Mbeki", "Mendes", "Mikkelsen",
    "Moreau", "Mortensen", "Nakamura", "Navarro", "Nguyen", "Nilsen", "Novak",
    "Nowak", "Obi", "Okafor", "Olsen", "Ortiz", "Ostrowski", "Pahlavi",
    "Pereira", "Petrov", "Pham", "Quintero", "Rahman", "Ramirez", "Rasmussen",
    "Reinhardt", "Ricci", "Rossi", "Ruiz", "Salvatore", "Sandoval", "Santos",
    "Sasaki", "Schneider", "Serrano", "Sharma", "Silva", "Sinclair", "Solberg",
    "Sorensen", "Steiner", "Suzuki", "Takahashi", "Tanaka", "Thorne", "Toure",
    "Vargas", "Vasquez", "Vega", "Verhoeven", "Vidal", "Vogel", "Wagner",
    "Walsh", "Weber", "Whitaker", "Yamamoto", "Yilmaz", "Zambrano", "Zielinski",
)

# -- Places (V33.7) -------------------------------------------------------
# City names are assembled from invented roots and generic geographic suffixes,
# so results feel internationally plausible without copying any real city
# (V32.6: realism without copying reality).
CITY_ROOTS: tuple[str, ...] = (
    "Aber", "Alder", "Ash", "Aven", "Bay", "Bel", "Birch", "Black", "Bridge",
    "Bright", "Brook", "Cald", "Carr", "Cedar", "Clear", "Cliff", "Cold",
    "Corn", "Crest", "Dun", "East", "Elm", "Fair", "Fall", "Fern", "Ford",
    "Glen", "Gold", "Green", "Grey", "Hart", "Haw", "Hazel", "High", "Holm",
    "Iron", "Kirk", "Lake", "Lang", "Lin", "Long", "Marsh", "Mill", "Moor",
    "North", "Oak", "Old", "Pine", "Ridge", "River", "Rock", "Rose", "Silver",
    "South", "Stone", "Storm", "Strand", "Sun", "Thorn", "Vale", "Well",
    "West", "White", "Wild", "Wind", "Wold",
)

CITY_SUFFIXES: tuple[str, ...] = (
    "bury", "burgh", "crest", "dale", "field", "ford", "gate", "haven", "holt",
    "ley", "mere", "mont", "moor", "port", "reach", "ridge", "stead", "ton",
    "vale", "view", "wick", "worth",
)

# -- Institutions ---------------------------------------------------------
# Banks (V33.4) favour the solid, established tone V32.7 assigns to the
# Financial identity — these are institutions the player must trust to borrow
# from.
BANK_SUFFIXES: tuple[str, ...] = (
    "Bank", "Banking Group", "Capital Bank", "Commercial Bank", "Credit Union",
    "Financial", "Merchant Bank", "National Bank", "Savings Bank", "Trust",
    "Trust Bank", "Union Bank",
)

# News agencies (V33.10) follow the Media identity, mixing general outlets with
# specialised financial ones so Company News and Economic News can plausibly
# come from different sources.
NEWS_AGENCY_SUFFIXES: tuple[str, ...] = (
    "Chronicle", "Daily", "Dispatch", "Gazette", "Herald", "Journal", "Ledger",
    "Observer", "Post", "Press", "Register", "Report", "Review", "Times",
    "Tribune", "Wire",
)

NEWS_AGENCY_PREFIXES: tuple[str, ...] = (
    "Business", "Capital", "Commerce", "Enterprise", "Exchange", "Financial",
    "Global", "Market", "Trade", "World",
)

# Universities (V33.8) share the institutional register of banks.
UNIVERSITY_FORMS: tuple[str, ...] = (
    "{place} University",
    "University of {place}",
    "{place} Institute of Technology",
    "{place} Business School",
    "{word} University",
    "{word} Institute",
)

# Organisations (V33.11) cover regulators and industry bodies implied by V24.4.
# The register is formal and institutional, deliberately distinct from corporate
# naming, and no real regulatory body is referenced.
ORGANISATION_SCOPES: tuple[str, ...] = (
    "Central", "Federal", "Global", "International", "National", "Union",
)

ORGANISATION_DOMAINS: tuple[str, ...] = (
    "Banking", "Capital Markets", "Commerce", "Corporate Standards", "Economic",
    "Exchange", "Financial Conduct", "Industry", "Market Integrity", "Securities",
    "Trade",
)

ORGANISATION_BODIES: tuple[str, ...] = (
    "Authority", "Board", "Bureau", "Commission", "Committee", "Council",
    "Institute", "Office", "Register", "Supervisory Board",
)

# Investment funds (V33.9) reuse the corporate word families, since funds are
# financial products rather than standalone companies.
FUND_STRATEGIES: tuple[str, ...] = (
    "Balanced", "Core", "Diversified", "Dynamic", "Equity", "Global", "Growth",
    "Income", "Index", "Opportunities", "Select", "Strategic", "Sustainable",
    "Value",
)

FUND_VEHICLES: tuple[str, ...] = (
    "Capital Fund", "Fund", "Growth Fund", "Investment Fund", "Partners Fund",
    "Portfolio", "Trust",
)
