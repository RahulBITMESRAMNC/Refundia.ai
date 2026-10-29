import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY") or os.getenv("grok_api_key"))

for m in sorted(client.models.list().data, key=lambda m: m.id):
    print(m.id)