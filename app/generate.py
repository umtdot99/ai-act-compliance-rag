import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

MODEL = "claude-opus-5"
MAX_TOKENS = 3500

client = Anthropic()

with open("SYSTEM_PROMPT.md",  "r", encoding="utf-8") as f:
    system_prompt = f.read()

def answer(q, context):

    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": context + " " + q}],
    )

    for block in message.content:
        if block.type == "text":
            return block.text

    return ""