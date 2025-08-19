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
    system_message = (
        "You are a biotech venture analyst. Given these abstracts, analyze whether "
        "they represent assets or programs that might be useful for pipeline expansion "
        "or new company formation. Call out specific disease areas, modalities, and any "
        "underlying novelty or unmet need."
    )

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": text_blob},
    ]

    try:
        client = OpenAI(api_key=openai.api_key)
        response: ChatCompletion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.5,
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
                "temperature": 0.5
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
