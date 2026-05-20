"""
scripts/generate_dataset.py

Prompt D — Offline Dataset Generator
Model: Gemini 2.5 Pro (runs ONCE during development)

Two modes:
  1. convert  — Converts existing ipl_players.csv → players.json (boolean → float)
  2. expand   — Uses Gemini Pro to generate attributes for additional IPL players
  3. full     — Both: convert CSV + expand to target player count

Output: backend/data/players.json
  [{"player_id": "...", "name": "...", "attributes": {attr: float, ...}, ...}, ...]

Usage:
  python -m backend.scripts.generate_dataset --mode convert
  python -m backend.scripts.generate_dataset --mode expand --target 200
  python -m backend.scripts.generate_dataset --mode full --target 200
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path

from backend.llm import LLMClient
from dotenv import load_dotenv

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.player import ATTRIBUTE_NAMES, Player

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent
CSV_PATH = BASE_DIR / "data" / "ipl_players.csv"
OUTPUT_PATH = BASE_DIR / "data" / "players.json"

# ─────────────────────────────────────────────────────────────────────────────
# CSV column → ATTRIBUTE_NAMES mapping
# Maps CSV column names to our canonical float attribute names
# ─────────────────────────────────────────────────────────────────────────────

CSV_TO_ATTR: dict[str, str] = {
    # Identity
    "is_overseas":              "is_overseas",
    # Role
    "is_batsman":               "is_batsman",
    "is_bowler":                "is_bowler",
    "is_allrounder":            "is_allrounder",
    "Column 1":                 "is_wicketkeeper", # Detected in CSV structure
    # Batting
    "top_order_batter":         "is_opener",
    "is_finisher":              "is_finisher",
    "right_handed_batter":      "bats_right",
    "left_handed_batter":       "bats_left",
    "is_aggressive_batter":     "is_aggressive_batter",
    # Bowling
    "fast_bowler":              "bowls_fast",
    "spinner":                  "bowls_spin",
    "swing_bowler":             "bowls_medium",
    "death_bowler":             "is_death_bowler",
    "express_pace":             "is_powerplay_bowler",
    # Teams
    "played_for_csk":           "played_csk",
    "played_for_mi":            "played_mi",
    "played_for_rcb":           "played_rcb",
    "played_for_kkr":           "played_kkr",
    "played_for_dc":            "played_dc",
    "played_for_srh":           "played_srh",
    "played_for_rr":            "played_rr",
    "played_for_pbks":          "played_pbks",
    "played_for_gt":            "played_gt",
    "played_for_lsg":           "played_lsg",
    # Achievement
    "has_captained_ipl":        "is_captain",
    "won_orange_cap":           "has_orange_cap",
    "won_purple_cap":           "has_purple_cap",
    "ipl_legend":               "is_international_star",
    # Semantic
    "ipl_veteran_150_matches":  "is_consistent_performer",
    "is_veteran_35plus":        "is_early_era",
    "is_young_under_25":        "is_recent_era",
    "all_format_player":        "is_match_winner",
    "has_30_ipl_fifties":       "is_famous_for_sixes",  # best available proxy
    "multiple_ipl_centuries":   "won_ipl_title",         # proxy for elite batsman
}

# Attributes not directly in CSV — will be estimated or set to defaults
DEFAULTS: dict[str, float] = {
    "is_indian":            0.7,   # majority are Indian
    "is_wicketkeeper":      0.05,  # rare role
    "is_anchor":            0.3,
    "is_aggressive_batter": 0.5,
    "is_economy_bowler":    0.4,
    "is_mid_era":           0.5,
    "is_death_specialist":  0.3,
}


def bool_to_float(value: str) -> float:
    """Convert CSV boolean string to float."""
    v = value.strip().upper()
    if v in ("TRUE", "1", "YES"):
        return 1.0
    elif v in ("FALSE", "0", "NO"):
        return 0.0
    else:
        return 0.5  # unknown → neutral


def slugify(name: str) -> str:
    return name.lower().strip().replace(" ", "-").replace("'", "").replace(".", "")


# ─────────────────────────────────────────────────────────────────────────────
# Mode 1: Convert CSV → players.json
# ─────────────────────────────────────────────────────────────────────────────

def convert_csv_to_players() -> list[dict]:
    """Convert the existing CSV dataset to our float attribute format."""
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    players = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Try 'name' or 'player_name'
            name = (row.get("name") or row.get("player_name", "")).strip()
            if not name:
                continue

            # Nationality/Identity
            nationality = (row.get("nationality") or row.get("country", "India")).strip()
            is_overseas = 0.0 if nationality.lower() in ("india", "ind") else 1.0

            # Build attribute dict — start with defaults
            attrs: dict[str, float] = {attr: 0.0 for attr in ATTRIBUTE_NAMES}
            attrs.update(DEFAULTS)

            # 1. First try direct mapping (if CSV columns match ATTRIBUTE_NAMES exactly)
            for attr in ATTRIBUTE_NAMES:
                if attr in row:
                    try:
                        attrs[attr] = float(row[attr])
                    except ValueError:
                        attrs[attr] = bool_to_float(row[attr])

            # 2. Then apply legacy mapping (overrides direct if present)
            for csv_col, attr_name in CSV_TO_ATTR.items():
                if csv_col in row and attr_name in ATTRIBUTE_NAMES:
                    attrs[attr_name] = bool_to_float(row[csv_col])

            # Force identity consistency
            attrs["is_overseas"] = is_overseas
            attrs["is_indian"] = 1.0 - is_overseas

            # Derive mid_era as complement
            attrs["is_mid_era"] = round(
                1.0 - max(attrs["is_early_era"], attrs["is_recent_era"]) * 0.6, 2
            )
            attrs["is_mid_era"] = max(0.0, min(1.0, attrs["is_mid_era"]))

            # Validate and build Player
            try:
                player = Player(
                    player_id=slugify(name),
                    name=name,
                    attributes=attrs,
                    nationality=nationality,
                )
                players.append(player.to_dict())
                logger.info("Converted: %s", name)
            except ValueError as e:
                logger.warning("Skipping %s: %s", name, e)

    logger.info("Converted %d players from CSV.", len(players))
    return players


# ─────────────────────────────────────────────────────────────────────────────
# Mode 2: Gemini Pro expansion
# ─────────────────────────────────────────────────────────────────────────────

EXPANSION_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "nationality": {"type": "string"},
            "attributes": {
                "type": "object",
                "properties": {attr: {"type": "number"} for attr in ATTRIBUTE_NAMES},
                "required": ATTRIBUTE_NAMES,
            },
        },
        "required": ["name", "nationality", "attributes"],
    },
}

EXPANSION_SYSTEM_PROMPT = f"""You are an expert IPL cricket analyst building a player knowledge base.

For each IPL player provided, generate a JSON object with 40 float attributes (0.0 to 1.0).
These are probabilistic scores, NOT binary — use the full 0.0–1.0 range.

Attribute meanings:
- 0.0 = definitely does NOT have this trait
- 0.5 = uncertain / somewhat
- 1.0 = definitively HAS this trait

Use nuanced values. For example:
- A pure batsman who occasionally bowls might have is_bowler=0.1
- A player known for sixes but also takes singles: is_famous_for_sixes=0.75
- An Indian who spent 2 years overseas might have is_recent_era=0.9

The 40 attributes are: {json.dumps(ATTRIBUTE_NAMES)}

Return a JSON array — one object per player. Be accurate based on real IPL history.
"""

# Additional IPL players to generate beyond the CSV
ADDITIONAL_PLAYERS = [
    "Sachin Tendulkar", "Adam Gilchrist", "Sourav Ganguly", "Rahul Dravid",
    "VVS Laxman", "Anil Kumble", "Zaheer Khan", "Harbhajan Singh",
    "Yuvraj Singh", "Suresh Raina", "Gautam Gambhir", "Virender Sehwag",
    "Murali Vijay", "Ambati Rayudu", "Robin Uthappa", "Dinesh Karthik",
    "Wriddhiman Saha", "Ajinkya Rahane", "Ravichandran Ashwin", "Pragyan Ojha",
    "Bhuvneshwar Kumar", "Umesh Yadav", "Ishant Sharma", "Mohammed Siraj",
    "Shivam Dube", "Krunal Pandya", "Axar Patel", "Washington Sundar",
    "Ruturaj Gaikwad", "Devdutt Padikkal", "Prithvi Shaw", "Yashasvi Jaiswal",
    "Tilak Varma", "Rinku Singh", "Sanju Samson", "Nicholas Pooran",
    "Glenn Maxwell", "Steve Smith", "David Miller", "Jonny Bairstow",
    "Ben Stokes", "Sam Curran", "Liam Livingstone", "Jos Buttler",
    "Eoin Morgan", "Jason Roy", "Alex Hales", "Tom Curran",
    "Rashid Khan", "Mohammad Nabi", "Narine Sunil", "Andre Russell",
    "Dwayne Bravo", "Chris Gayle", "Marlon Samuels", "Kieron Pollard",
    "Brendon McCullum", "Kane Williamson", "Trent Boult", "Tim Southee",
    "Mitchell Starc", "Pat Cummins", "Josh Hazlewood", "Nathan Coulter-Nile",
    "Faf du Plessis", "AB de Villiers", "Quinton de Kock", "David Miller",
    "Imran Tahir", "Chris Morris", "Marco Jansen", "Anrich Nortje",
    "Lasith Malinga", "Thisara Perera", "Angelo Mathews", "Kusal Perera",
    "Hashim Amla", "Morne Morkel", "Dale Steyn", "Kagiso Rabada",
    "Shakib Al Hasan", "Mustafizur Rahman", "Tamim Iqbal", "Mahmudullah",
]


def expand_with_llm(
    existing_names: set[str],
    target_total: int,
    client: LLMClient,
    batch_size: int = 5,
) -> list[dict]:
    """Use an LLM to generate attributes for additional players."""
    # Model name is handled by client or can be overridden here
    model_name = os.getenv("LLM_MODEL") or "gpt-4o-mini"

    # Filter to players not already in CSV
    to_generate = [p for p in ADDITIONAL_PLAYERS if p not in existing_names]
    needed = max(0, target_total - len(existing_names))
    to_generate = to_generate[:needed]

    if not to_generate:
        logger.info("No additional players needed.")
        return []

    logger.info("Generating attributes for %d additional players...", len(to_generate))
    generated = []

    # Process in batches to stay within token limits
    i = 0
    while i < len(to_generate):
        batch = to_generate[i: i + batch_size]
        logger.info("Batch %d/%d: %s", i // batch_size + 1,
                    (len(to_generate) + batch_size - 1) // batch_size,
                    ", ".join(batch))

        prompt = (
            f"Generate attribute profiles for these {len(batch)} IPL players:\n"
            + "\n".join(f"- {name}" for name in batch)
        )

        try:
            batch_data = client.generate_json(
                system_prompt=EXPANSION_SYSTEM_PROMPT,
                user_prompt=prompt,
                model=model_name,
                response_schema=EXPANSION_SCHEMA,
                temperature=0.3,
                max_tokens=4096
            )

            for player_data in batch_data:
                name = player_data.get("name", "").strip()
                nationality = player_data.get("nationality", "India")
                raw_attrs = player_data.get("attributes", {})

                # Clamp all values to [0.0, 1.0]
                attrs = {
                    attr: max(0.0, min(1.0, float(raw_attrs.get(attr, 0.5))))
                    for attr in ATTRIBUTE_NAMES
                }

                try:
                    player = Player(
                        player_id=slugify(name),
                        name=name,
                        attributes=attrs,
                        nationality=nationality,
                    )
                    generated.append(player.to_dict())
                    logger.info("  ✅ Generated: %s", name)
                except ValueError as e:
                    logger.warning("  ⚠️  Skipping %s: %s", name, e)

            # Successfully processed batch
            i += batch_size
            
            # Wait between batches to stay within free tier limits
            # 60s per RPM for Gemini 1.5 Pro free tier
            logger.info("  ⏳ Waiting 10s for next batch...")
            time.sleep(10)

        except Exception as exc:
            if "429" in str(exc) or "quota" in str(exc).lower():
                logger.warning("  ⚠️  Rate limit hit! Waiting 65s before retry...")
                time.sleep(65)
                # i is NOT incremented, so it will retry the same batch
                continue
            
            logger.error("Batch failed: %s", exc)
            time.sleep(5)
            i += batch_size  # skip failing batch to avoid infinite loop
            continue

    logger.info("Generated %d additional players.", len(generated))
    return generated


# ─────────────────────────────────────────────────────────────────────────────
# Save + load helpers
# ─────────────────────────────────────────────────────────────────────────────

def save_players(players: list[dict], path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)
    logger.info("Saved %d players to %s", len(players), path)


def load_players(path: Path = OUTPUT_PATH) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="IPL Akinator Dataset Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["convert", "expand", "full"],
        default="convert",
        help="convert: CSV→JSON only | expand: Gemini only | full: both",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=100,
        help="Target total number of players (used in expand/full modes)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(OUTPUT_PATH),
        help="Output JSON file path",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    client = LLMClient()
    all_players: list[dict] = []

    # ── Convert mode ──────────────────────────────────────────────
    if args.mode in ("convert", "full"):
        logger.info("Converting CSV → JSON...")
        csv_players = convert_csv_to_players()
        all_players.extend(csv_players)
        logger.info("CSV conversion done: %d players", len(csv_players))

    # ── Expand mode ───────────────────────────────────────────────
    if args.mode in ("expand", "full"):
        existing_names = {p["name"] for p in all_players}
        logger.info("Expanding dataset to %d players with LLM...", args.target)
        extra = expand_with_llm(
            existing_names=existing_names,
            target_total=args.target,
            client=client,
        )
        all_players.extend(extra)

    # ── Deduplicate by player_id ──────────────────────────────────
    seen: set[str] = set()
    deduped = []
    for p in all_players:
        pid = p.get("player_id", "")
        if pid not in seen:
            seen.add(pid)
            deduped.append(p)

    logger.info("Final dataset: %d unique players", len(deduped))
    save_players(deduped, output_path)
    logger.info("✅ Done! Output at: %s", output_path)


if __name__ == "__main__":
    main()
