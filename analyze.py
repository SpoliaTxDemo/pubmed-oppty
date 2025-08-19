"""Wrapper around the OpenAI Python SDK to analyze PubMed abstracts.

This module provides a simple function for sending a batch of abstracts to
an OpenAI Chat completion endpoint. It trims the input based on the
model's approximate context window and constructs a prompt suitable for
identifying biotech opportunities in the literature.
"""

import os
import openai
import requests
import certifi
from openai import OpenAI
from openai.types.chat import ChatCompletion

openai.api_key = os.environ.get("OPENAI_API_KEY")

def analyze_abstracts(text_blob: str, model: str = "gpt-4o-mini") -> str:
    system_message = """
You are a biotech venture analyst. You evaluate biomedical research abstracts for their potential as pipeline expansion or startup (NewCo) opportunities.

For each abstract, assess:
1. **Disease Area or Target** — What is the condition or biological target?
2. **Therapeutic Modality** — Is it gene therapy, small molecule, biologic, etc.?
3. **Novelty** — What makes the approach unique or differentiated?
4. **Development Stage** — Preclinical, Phase I/II/III?
5. **Commercial Potential** — Unmet need, market size, competitive landscape
6. **Opportunity Fit** — Is this viable for pipeline expansion or a NewCo? Why or why not? Set a high bar.

Structure your answer in a clear bullet-point format for each abstract. Prioritize concise, decision-useful insight.
"""

    user_message = f"""Analyze the following abstracts using the framework above:\n\n{text_blob}"""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]

    try:
        client = OpenAI(api_key=openai.api_key)
        response: ChatCompletion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.4,
            max_tokens=2048,
        )
        return response.choices[0].message.content

    except openai.APIConnectionError as e:
        # Try fallback using requests
        try:
            headers = {
                "Authorization": f"Bearer {openai.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 2048
            }
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
                verify=certifi.where()
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

        except Exception as fallback_error:
            return f"[OpenAI fallback error] {type(fallback_error).__name__}: {fallback_error}"

    except Exception as e:
        return f"[OpenAI error] {type(e).__name__}: {e}"
