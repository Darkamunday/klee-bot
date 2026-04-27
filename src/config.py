import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

DEFAULTS = {
    "prefix": "klee",
    "ollama_model": "gpt-oss:120b-cloud",
    "chat_system_prompt": (
        "You are Klee, a friendly and helpful AI assistant in a Discord server. "
        "Keep responses concise and conversational."
    ),
    "txt2img_model": "flux2_klein",
    "image_width": 1024,
    "image_height": 1024,
    "image_steps": 20,
    "image_cfg": 6.0,
    "flux_steps": 20,
    "flux_guidance": 3.5,
    "inpaint_threshold": 0.05,
    "inpaint_expand": 15,
    "inpaint_blur_radius": 2,
    "upscale_resolution": 2048,
    "upscale_color_correction": "lab",
    "flux2_t2i_steps": 4,
    "flux2_t2i_cfg": 1,
    "flux2_i2i_steps": 4,
    "flux2_i2i_cfg": 1,
    "inpaint_model": "gpt-oss:120b-cloud",
    "nsfw_image_model": "dolphin-mistral",
    "vision_model": "gemma3:12b",
    "allowed_channels": [],
}


def _load_all() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {"guilds": {}}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save_all(data: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load(guild_id: int) -> dict:
    data = _load_all()
    guild_cfg = data.get("guilds", {}).get(str(guild_id), {})
    result = DEFAULTS.copy()
    result.update(guild_cfg)
    return result


def save(guild_id: int, cfg: dict) -> None:
    data = _load_all()
    data.setdefault("guilds", {})[str(guild_id)] = cfg
    _save_all(data)
