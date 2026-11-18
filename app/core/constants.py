"""Zero-dependency constants shared across lightweight API serialization and ML scoring."""

CANONICAL_AESTHETIC_TAGS = {
    "eyes_closed",
    "face_blurry",
    "tilted_horizon",
    "edge_subject",
    "eyes_open_sharp",
    "level_horizon",
    "rule_of_thirds",
}

TAG_PRIORITY_ORDER = [
    # Warnings first (highest impact first)
    "eyes_closed",
    "face_blurry",
    "tilted_horizon",
    "edge_subject",
    # Positive highlights
    "eyes_open_sharp",
    "level_horizon",
    "rule_of_thirds",
]
