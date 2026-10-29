import asyncio
import json
import os
import re
import time

from dotenv import load_dotenv
from groq import RateLimitError
from langchain.chat_models import init_chat_model
from deepeval.models import DeepEvalBaseLLM

load_dotenv(override=True)

MAX_ATTEMPTS = 8
RETRY_WAIT_S = 30   # wait after a 429 (Groq's window is per minute)
PACING_S = 12       # pause after each successful call so TPM can recover

_locks = {}         # one asyncio.Lock per event loop


def _get_lock():
    loop = asyncio.get_running_loop()
    if loop not in _locks:
        _locks[loop] = asyncio.Lock()
    return _locks[loop]


def _parse(text: str, schema):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    data = json.loads(match.group(0) if match else text)
    return schema(**data)


def _log_size(prompt: str):
    # rough estimate: ~4 characters per token
    print(f"[judge prompt] {len(prompt)} chars (~{len(prompt) // 4} tokens)")
    with open("judge_prompt_debug.txt", "w", encoding="utf-8") as f:
        f.write(prompt)


class GroqJudge(DeepEvalBaseLLM):
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("grok_api_key")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set in .env")
        self.llm = init_chat_model(
            os.getenv("JUDGE_MODEL", "openai/gpt-oss-120b"),
            model_provider="groq",
            api_key=api_key,
            temperature=0,
            max_retries=0,  # was 6: let 429s reach our retry loop instead of the client's hidden sleep
        )

    def load_model(self):
        return self.llm

    def _prompt(self, prompt: str, schema) -> str:
        if schema is None:
            return prompt
        return (
            f"{prompt}\n\nReturn ONLY a valid JSON object matching this schema, "
            f"with no extra text or markdown:\n{json.dumps(schema.model_json_schema())}"
        )

    def generate(self, prompt: str, schema=None):
        full = self._prompt(prompt, schema)
        _log_size(full)
        for _ in range(MAX_ATTEMPTS):
            try:
                text = self.llm.invoke(full).content
                time.sleep(PACING_S)
                break
            except RateLimitError:
                time.sleep(RETRY_WAIT_S)
        else:
            raise RuntimeError("Groq rate limit: retries exhausted")
        return _parse(text, schema) if schema else text

    async def a_generate(self, prompt: str, schema=None):
        full = self._prompt(prompt, schema)
        _log_size(full)
        async with _get_lock():  # one judge call at a time
            for _ in range(MAX_ATTEMPTS):
                try:
                    text = (await self.llm.ainvoke(full)).content
                    await asyncio.sleep(PACING_S)
                    break
                except RateLimitError:
                    await asyncio.sleep(RETRY_WAIT_S)
            else:
                raise RuntimeError("Groq rate limit: retries exhausted")
        return _parse(text, schema) if schema else text

    def get_model_name(self):
        return f"groq-{os.getenv('JUDGE_MODEL', 'openai/gpt-oss-120b')}"


eval_model = GroqJudge()