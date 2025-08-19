"""Wrapper around the OpenAI Python SDK to analyze PubMed abstracts.

This module provides a simple function for sending a batch of abstracts to
an OpenAI Chat completion endpoint. It trims the input based on the
model's approximate context window and constructs a prompt suitable for
identifying biotech opportunities in the literature.
"""

import os
import time
import httpx
import requests
import certifi
from openai import OpenAI
from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError

MODEL_CHAR_CAP = {"gpt-4o-mini": 80_000, "gpt-4o": 120_000}
DEFAULT_MODEL = "gpt-4o-mini"

def _build_prompt(abstracts_text: str):
    system = (
        "You are a biotech venture analyst. Given recent PubMed abstracts, "
        "identify potential pipeline expansion and newco opportunities. "
        "Summarize themes, modalities, targets, validation level, differentiation "
        "vs. standard of care, and partnering angles."
    )
    user = (
        "Analyze the following abstracts (focus on novelty, tractability, and commercial potential). "
        "Return: (1) bullet summary of themes; (2) ranked short-list of 3–5 opportunities with rationale.\n\n"
        f"{abstracts_text}"
    )
    return system, user

def analyze_abstracts(abstracts_text: str, model: str = DEFAULT_MODEL) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "[Config error] OPENAI_API_KEY is not set on the web service."

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    cap = MODEL_CHAR_CAP.get(model, MODEL_CHAR_CAP[DEFAULT_MODEL])
    snippet = abstracts_text[:cap]
    system, user = _build_prompt(snippet)

    # Primary: OpenAI SDK via httpx client, HTTP/2 disabled
    http_client = httpx.Client(http2=False, timeout=60.0, verify=certifi.where())
    client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)

    def _sdk_call():
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()

    # Fallback: raw requests (HTTP/1.1)
    def _requests_fallback():
        url = base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        r = requests.post(url, json=payload, headers=headers, timeout=60, verify=certifi.where())
        if r.status_code >= 400:
            return f"[OpenAI HTTP {r.status_code}] {r.text[:500]}"
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()

    # Try SDK once, quick retry for transient network; then fallback to requests
    for attempt in (1, 2):
        try:
            return _sdk_call()
        except (AuthenticationError, RateLimitError, APIError) as e:
            return f"[OpenAI error] {e}"
        except (APIConnectionError, httpx.HTTPError) as e:
            if attempt == 1:
                time.sleep(1.0)
                continue
            # Fallback path
            try:
                return _requests_fallback()
            except requests.RequestException as e2:
                return (f"[Connection error] Unable to reach the OpenAI API at {base_url}. "
                        f"Please verify network connectivity and ensure the base URL is correct. "
                        f"Error details: {e2}")
        except Exception as e:
            return f"[Unexpected error] {e}"
