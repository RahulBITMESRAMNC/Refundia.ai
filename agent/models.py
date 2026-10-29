import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()

model_name = os.getenv("AGENT_MODEL")
if not model_name:
    raise RuntimeError("AGENT_MODEL is not set in .env")

api_key = os.getenv("GROQ_API_KEY") or os.getenv("grok_api_key")
if not api_key:
    raise RuntimeError("GROQ_API_KEY is not set in .env")

model = init_chat_model(
    model=model_name,
    model_provider="groq",
    api_key=api_key,
)