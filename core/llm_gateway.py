import os
import redis
import json
import httpx
import dotenv
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def job(prompt, gid):
    print(f"[LLM] Starting summary job for chat {gid}")
    print(f"[LLM] Prompt length: {len(prompt)} characters")

    dotenv.load_dotenv()
    proxy_url = os.getenv('PROXY_URL')
    http_client = httpx.Client(proxy=proxy_url)
    
    client = OpenAI(api_key=os.getenv('OPENAI_KEY'), http_client=http_client)
    print(f"[LLM] OpenAI client initialized")

    with open(os.getenv('PROMPT_PATH'), 'r') as f:
        instructions = f.read()
    print(f"[LLM] Loaded prompt instructions ({len(instructions)} chars)")

    print(f"[LLM] Sending request to OpenAI API...")
    response = client.responses.create(
        model="gpt-5-nano",
        instructions=instructions,
        input=prompt
    )
    print(f"[LLM] Received response from OpenAI")

    out = response.output_text
    print(f"[LLM] Generated summary ({len(out)} chars) for chat {gid}")
    
    redis_conn = redis.Redis(host=os.getenv('REDIS_HOST'))
    print(f"[LLM] Connected to Redis, storing results...")

    redis_conn.incrby('pending', 1)
    
    # Get existing summaries list or initialize empty list
    existing_summaries = redis_conn.get('summaries')
    if existing_summaries is None:
        summaries_list = []
    else:
        summaries_list = json.loads(existing_summaries.decode('utf-8'))
    
    # Append new summary and save back
    summaries_list.append([out, gid])
    redis_conn.set('summaries', json.dumps(summaries_list))
    print(f"[LLM] Summary stored in Redis queue for chat {gid}")

