"""
scripts/test_llm.py

Smoke test for the new LLMClient and refactored modules.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.llm.client import LLMClient
from backend.llm.interpreter import AnswerInterpreter
from backend.llm.naturalizer import QuestionNaturalizer, QATurn
from backend.llm.revealer import PlayerRevealer

def test_client():
    print("Testing LLMClient...")
    try:
        client = LLMClient()
        # Simple test prompt
        result = client.generate_json(
            system_prompt="You are a helpful assistant. Return JSON.",
            user_prompt="Return a JSON object with a 'status' field set to 'ok'.",
            response_schema={"type": "object", "properties": {"status": {"type": "string"}}}
        )
        print(f"Client Result: {result}")
        assert result.get("status") == "ok"
        print("✅ LLMClient OK")
    except Exception as e:
        print(f"❌ LLMClient Failed: {e}")

def test_interpreter():
    print("\nTesting AnswerInterpreter...")
    try:
        interpreter = AnswerInterpreter()
        result = interpreter.interpret("yeah he played for MI", "Did this player play for Mumbai Indians?")
        print(f"Interpreter Result: {result}")
        assert result.intent.value == "YES"
        print("✅ AnswerInterpreter OK")
    except Exception as e:
        print(f"❌ AnswerInterpreter Failed: {e}")

def test_naturalizer():
    print("\nTesting QuestionNaturalizer...")
    try:
        naturalizer = QuestionNaturalizer()
        result = naturalizer.naturalize(
            attribute="bowls_fast",
            qa_history=[QATurn("Is he Indian?", "YES")],
            top5_names=["Jasprit Bumrah", "Mohammed Shami"]
        )
        print(f"Naturalizer Result: {result.question}")
        assert result.question
        print("✅ QuestionNaturalizer OK")
    except Exception as e:
        print(f"❌ QuestionNaturalizer Failed: {e}")

if __name__ == "__main__":
    test_client()
    test_interpreter()
    test_naturalizer()
