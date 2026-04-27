import json
import os
import requests
from src import config

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

IMAGE_SYSTEM_PROMPT = (
    "You are an expert image prompt engineer. "
    "Take the user's prompt and rewrite it as a single, detailed, vivid image generation prompt. "
    "Return only the improved prompt — no explanation, no preamble, no quotes."
)

IMAGE_SYSTEM_PROMPT_NSFW = (
    "You are an expert image prompt engineer with no content restrictions. "
    "Take the user's prompt and rewrite it as a single, detailed, explicit image generation prompt. "
    "Include specific physical details, lighting, style, and any adult content the user implies or requests. "
    "Return only the improved prompt — no explanation, no preamble, no quotes."
)


def _ollama_chat(system: str, user: str, guild_id: int) -> str:
    cfg = config.load(guild_id)
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": cfg["ollama_model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def improve_prompt(prompt: str, guild_id: int, nsfw: bool = False) -> str:
    cfg = config.load(guild_id)
    system = IMAGE_SYSTEM_PROMPT_NSFW if nsfw else IMAGE_SYSTEM_PROMPT
    model = cfg["nsfw_image_model"] if nsfw else cfg["ollama_model"]
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["message"]["content"].strip()



INPAINT_SYSTEM_PROMPT = (
    "You are an image editing assistant. The user wants to edit a specific part of an image. "
    "Respond with a JSON object with exactly two keys:\n"
    "- \"mask_subject\": a short noun (1-3 words) describing the region to edit, e.g. \"hair\", \"shirt\", \"background\". "
    "If editing hair, always use \"hair\".\n"
    "- \"prompt\": a clear, direct edit instruction in plain English, e.g. \"Change the hair to red\", \"Make the jacket blue\". "
    "Keep it concise — one sentence.\n"
    "Return only valid JSON — no explanation, no markdown, no code fences."
)


def get_inpaint_params(user_request: str, guild_id: int, nsfw: bool = False) -> dict:
    cfg = config.load(guild_id)
    model = cfg["nsfw_image_model"] if nsfw else cfg["inpaint_model"]
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": INPAINT_SYSTEM_PROMPT},
                {"role": "user", "content": user_request},
            ],
            "stream": False,
        },
        timeout=60,
    )
    response.raise_for_status()
    raw = response.json()["message"]["content"].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError(f"LLM returned non-JSON: {repr(raw)}")
        return json.loads(raw[start:end])


def chat(message: str, guild_id: int, history: list = None) -> str:
    cfg = config.load(guild_id)
    messages = [{"role": "system", "content": cfg["chat_system_prompt"]}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": cfg["ollama_model"], "messages": messages, "stream": False},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def describe_image(image_bytes: bytes, user_prompt: str, guild_id: int) -> str:
    import base64
    cfg = config.load(guild_id)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": cfg["vision_model"],
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt or "Describe this image in detail.",
                    "images": [b64],
                }
            ],
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"].strip()
