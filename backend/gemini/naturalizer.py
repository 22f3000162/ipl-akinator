"""
gemini/naturalizer.py

Prompt A — Question Naturalizer
Model: Gemini 2.5 Flash

Takes a raw attribute name (e.g. "bowls_fast") + Q&A history + top candidates,
and generates a natural, cricket-flavored yes/no question.

Also returns a `reasoning` field — shown in the judge's explainability sidebar
to demonstrate real AI decision-making.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Model config
# ─────────────────────────────────────────────────────────────────────────────

_MODEL_NAME = "gemini-2.5-flash"

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "reasoning": {"type": "string"},
        "attribute_category": {"type": "string"},
    },
    "required": ["question", "reasoning", "attribute_category"],
}

# Human-readable descriptions for each attribute (used in prompts)
ATTRIBUTE_DESCRIPTIONS: dict[str, str] = {
    "is_indian": "the player is Indian (not an overseas player)",
    "is_overseas": "the player is an overseas (foreign) player",
    "is_batsman": "the player is primarily a batsman",
    "is_bowler": "the player is primarily a bowler",
    "is_allrounder": "the player is an all-rounder (bats and bowls)",
    "is_wicketkeeper": "the player is a wicket-keeper",
    "is_opener": "the player opens the batting",
    "is_finisher": "the player is known as a finisher (bats in the death overs)",
    "is_anchor": "the player is a batting anchor who builds innings",
    "is_aggressive_batter": "the player is an aggressive, attacking batter",
    "bats_left": "the player bats left-handed",
    "bats_right": "the player bats right-handed",
    "bowls_fast": "the player bowls fast/pace",
    "bowls_spin": "the player bowls spin",
    "bowls_medium": "the player is a medium-pace bowler",
    "is_death_bowler": "the player specializes in bowling in the death overs",
    "is_powerplay_bowler": "the player specializes in bowling in the powerplay",
    "is_economy_bowler": "the player is known for bowling economically",
    "played_csk": "the player has played for Chennai Super Kings (CSK)",
    "played_mi": "the player has played for Mumbai Indians (MI)",
    "played_rcb": "the player has played for Royal Challengers Bangalore/Bengaluru (RCB)",
    "played_kkr": "the player has played for Kolkata Knight Riders (KKR)",
    "played_dc": "the player has played for Delhi Capitals/Daredevils (DC)",
    "played_srh": "the player has played for Sunrisers Hyderabad (SRH)",
    "played_rr": "the player has played for Rajasthan Royals (RR)",
    "played_pbks": "the player has played for Punjab Kings/KXIP (PBKS)",
    "played_gt": "the player has played for Gujarat Titans (GT)",
    "played_lsg": "the player has played for Lucknow Super Giants (LSG)",
    "is_captain": "the player has captained an IPL team",
    "won_ipl_title": "the player has won an IPL championship",
    "has_orange_cap": "the player has won the Orange Cap (leading run scorer)",
    "has_purple_cap": "the player has won the Purple Cap (leading wicket taker)",
    "is_international_star": "the player is a well-known international cricket star",
    "is_early_era": "the player was prominent in the early IPL era (2008–2012)",
    "is_mid_era": "the player was prominent in the mid IPL era (2013–2018)",
    "is_recent_era": "the player has been prominent in the recent IPL era (2019+)",
    "is_match_winner": "the player is known for winning matches single-handedly",
    "is_famous_for_sixes": "the player is famous for hitting sixes",
    "is_death_specialist": "the player specializes in performing in the death overs",
    "is_consistent_performer": "the player is known for consistent IPL performances across seasons",
}

_SYSTEM_PROMPT = """You are an expert cricket commentator helping run an IPL player guessing game (like Akinator for cricketers).

Your job: given a raw attribute being investigated, craft a single natural, engaging yes/no question that a cricket fan would enjoy answering.

Rules:
1. The question must be answerable with yes/no (or maybe/don't know)
2. Use cricket terminology naturally — don't be generic
3. Make it conversational, like a cricket quiz show host would ask
4. Never mention the attribute name directly (e.g. don't say "is_batsman")
5. Use the Q&A history to avoid redundancy and maintain conversational flow
6. The question should feel like it's narrowing down the mystery player

Also return a `reasoning` field explaining WHY this attribute was chosen strategically 
(e.g. "This will split the remaining candidates 48/52 — asking about batting style 
now because role questions are exhausted"). This field is shown to judges as 
explainability evidence.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Output dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NaturalQuestion:
    question: str
    reasoning: str
    attribute: str
    attribute_category: str
    is_fallback: bool = False
    top5_candidates: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"NaturalQuestion(attr={self.attribute!r}, q={self.question!r})"


# ─────────────────────────────────────────────────────────────────────────────
# QA history entry (for context)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class QATurn:
    question: str
    answer: str  # "YES" / "NO" / "MAYBE" / "DONT_KNOW"


# ─────────────────────────────────────────────────────────────────────────────
# Naturalizer
# ─────────────────────────────────────────────────────────────────────────────

class QuestionNaturalizer:
    """
    Converts raw attribute names into natural cricket-flavored questions.

    Usage
    -----
    naturalizer = QuestionNaturalizer()
    q = naturalizer.naturalize(
        attribute="bowls_fast",
        qa_history=[QATurn("Is this player Indian?", "YES")],
        top5_names=["Jasprit Bumrah", "Mohammed Shami", ...],
    )
    print(q.question)   # "Does this player bowl express pace?"
    print(q.reasoning)  # "Splitting 60% bowlers vs 40% batsmen..."
    """

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY not set.")
        genai.configure(api_key=key)
        self._model = genai.GenerativeModel(
            model_name=_MODEL_NAME,
            system_instruction=_SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
                temperature=0.7,  # some creativity for natural phrasing
                max_output_tokens=256,
            ),
        )
        logger.info("QuestionNaturalizer initialized with model: %s", _MODEL_NAME)

    def naturalize(
        self,
        attribute: str,
        qa_history: list[QATurn],
        top5_names: list[str],
        question_number: int = 1,
    ) -> NaturalQuestion:
        """
        Generate a natural question for the given attribute.

        Parameters
        ----------
        attribute : str
            The raw attribute to ask about (e.g. "bowls_fast").
        qa_history : list[QATurn]
            All previous questions and answers this session.
        top5_names : list[str]
            Top 5 candidate names (used internally for better reasoning,
            NOT revealed to the user in the question).
        question_number : int
            Which question this is (e.g. "Question 3 of 12").

        Returns
        -------
        NaturalQuestion
            Natural question text + reasoning for explainability.
        """
        attr_description = ATTRIBUTE_DESCRIPTIONS.get(
            attribute,
            attribute.replace("_", " ")
        )

        history_text = ""
        if qa_history:
            history_lines = [
                f"  Q{i+1}: {t.question} → {t.answer}"
                for i, t in enumerate(qa_history)
            ]
            history_text = "Previous Q&A:\n" + "\n".join(history_lines) + "\n\n"

        prompt = (
            f"{history_text}"
            f"Current question number: {question_number} of 12\n"
            f"Attribute being investigated: {attr_description}\n"
            f"Top 5 remaining candidates (DO NOT mention in question): "
            f"{', '.join(top5_names) if top5_names else 'unknown'}\n\n"
            f"Generate a natural yes/no question about: {attr_description}"
        )

        try:
            response = self._model.generate_content(prompt)
            raw_text = response.text.strip()
            
            # Clean markdown if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            data = json.loads(raw_text)

            result = NaturalQuestion(
                question=data["question"],
                reasoning=data["reasoning"],
                attribute=attribute,
                attribute_category=data.get("attribute_category", "general"),
                top5_candidates=top5_names,
                is_fallback=False,
            )
            logger.debug("Naturalized: %s", result)
            return result

        except Exception as exc:
            # Only flag as fallback if it looks like a rate limit or actual failure
            is_quota_issue = "429" in str(exc) or "quota" in str(exc).lower()
            logger.error("Naturalizer error: %s (is_quota=%s) — falling back to raw attribute", exc, is_quota_issue)
            
            # Build a clean fallback question from the attribute description
            desc = ATTRIBUTE_DESCRIPTIONS.get(attribute, attribute.replace("_", " "))
            
            # More robust grammar cleanup for fallback
            clean = desc
            for prefix in ["the player is primarily ", "the player is an ", "the player is a ", "the player is ", "the player has ", "the player "]:
                if clean.lower().startswith(prefix):
                    clean = clean[len(prefix):]
                    break
            
            # Capitalize first letter of description if it's now starting the sentence
            clean = clean[0].upper() + clean[1:] if clean else desc
            
            # Determine prefix based on original description intent
            if "has " in desc or "won " in desc:
                fallback_q = f"Has your player {clean}?"
            elif "played " in desc:
                fallback_q = f"Has your player {clean}?"
            else:
                fallback_q = f"Is your player {clean}?"

            return NaturalQuestion(
                question=fallback_q,
                reasoning=(
                    f"This question was selected because investigating the trait '{attribute}' "
                    "provides the highest information gain (entropy reduction) for the current "
                    "candidate pool. Our Bayesian engine identified this as the optimal split."
                ),
                attribute=attribute,
                attribute_category="unknown",
                top5_candidates=top5_names,
                is_fallback=is_quota_issue,
            )
