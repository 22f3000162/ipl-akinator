"""
llm/client.py

Unified LLM Client using the OpenAI SDK.
Supports OpenAI, Groq, Together, DeepSeek, and other OpenAI-compatible providers.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class LLMClient:
    """
    A wrapper around the OpenAI SDK to provide a consistent interface
    for different LLM providers and models.
    """

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = provider or os.getenv("LLM_PROVIDER", "openai").lower()
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self.default_model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")

        if not self.api_key:
            raise ValueError(f"API key for provider '{self.provider}' not set. Please set LLM_API_KEY.")

        # Initialize the OpenAI client
        # If base_url is None, it defaults to OpenAI's official API
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        logger.info(
            "LLMClient initialized: provider=%s, model=%s, base_url=%s",
            self.provider, self.default_model, self.base_url or "default"
        )

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """
        Generates a JSON response from the LLM.
        """
        model_to_use = model or self.default_model
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Prepare arguments for chat completion
        kwargs: dict[str, Any] = {
            "model": model_to_use,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Handle JSON mode / Structured Outputs
        # Note: Not all providers support 'response_format' or 'json_schema'
        # For maximum compatibility, we'll use response_format={"type": "json_object"} 
        # and ensure the prompt asks for JSON.
        if response_schema:
             # Some models support strict JSON schema (like GPT-4o)
             # But for a generic client, we'll stick to basic JSON mode if possible
             kwargs["response_format"] = {"type": "json_object"}
             # We should also ensure "json" is in the prompt if using json_object
             if "json" not in user_prompt.lower() and "json" not in system_prompt.lower():
                 user_prompt += "\n\nReturn your response in valid JSON format."
                 kwargs["messages"][1]["content"] = user_prompt

        try:
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if not content:
                raise ValueError("LLM returned an empty response.")

            # Attempt to parse JSON
            # Sometimes models wrap JSON in markdown blocks
            clean_content = content.strip()
            if clean_content.startswith("```json"):
                clean_content = clean_content.split("```json")[1].split("```")[0].strip()
            elif clean_content.startswith("```"):
                clean_content = clean_content.split("```")[1].split("```")[0].strip()

            return json.loads(clean_content)

        except Exception as e:
            logger.error("LLM Error (%s): %s", self.provider, e)
            raise
