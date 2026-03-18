from __future__ import annotations

import os
import json
from openai import OpenAI


def call_llm_planner(
    prompt: str,
    *,
    system_prompt: str,
    model: str,
    temperature: float = 0.0,
) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Export your API key before using planner_backend='llm'."
        )

    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": system_prompt + "\\n\\nReturn valid JSON only.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=temperature,
        text={
            "format": {
                "type": "json_object"
            }
        },
    )

    return response.output_text