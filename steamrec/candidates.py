from __future__ import annotations


# MVP seed pool. This is deliberately structured data, not AI-generated output.
# Future work: replace/extend with a maintained "recent multiplayer app property"
# ingestion job as described in the product spec.
MAIN_CANDIDATES: dict[int, list[str]] = {
    1086940: ["TGA 2023 winner", "because it is acclaimed co-op"],
    1966720: ["recent hit", "because it is social co-op"],
    553850: ["recent hit", "because it is co-op action"],
    1326470: ["recent hit", "because it is survival co-op"],
    252490: ["because it is multiplayer survival"],
    346110: ["because it is multiplayer survival"],
    892970: ["because it is survival co-op"],
    648800: ["because it is survival co-op"],
    1245620: ["TGA 2022 winner", "because it supports co-op"],
    2073850: ["recent hit", "because it is team shooter"],
    1172470: ["because it is competitive multiplayer"],
    578080: ["because it is competitive multiplayer"],
    359550: ["because it is tactical multiplayer"],
    730: ["because it is competitive multiplayer"],
    413150: ["because it is cozy co-op"],
    105600: ["because it is sandbox co-op"],
    1281930: ["because it is platform fighter"],
    1818750: ["because it is platform fighter"],
    244850: ["because it is engineering sandbox"],
    394360: ["because it is multiplayer strategy"],
    289070: ["because it is multiplayer strategy"],
    306130: ["because it is online RPG"],
    582010: ["because it is co-op hunting"],
    1446780: ["because it is co-op hunting"],
    1282100: ["because it is co-op shooter"],
    1172620: ["because it is pirate co-op"],
    1203220: ["because it is melee battle royale"],
    1938090: ["because it is competitive shooter"],
    548430: ["because it is co-op shooter"],
    677620: ["because it is chaotic co-op"],
    312520: ["because it is survival co-op"],
    322330: ["because it is survival co-op"],
    4000: ["because it is sandbox multiplayer"],
    304930: ["because it is survival multiplayer"],
    1144200: ["because it is tactical co-op"],
    632360: ["because it is roguelike co-op"],
    858820: ["because it is party co-op"],
    774801: ["because it is co-op action roguelike"],
    2399830: ["recent hit", "because it is survival co-op"],
}


FRESH_CANDIDATES: dict[int, list[str]] = {
    1260320: ["fresh track", "because it is upcoming co-op"],
    2300320: ["fresh track", "because it is upcoming multiplayer"],
    1903340: ["fresh track", "because it is co-op sequel"],
}

