# CLAUDE.md

## Project goal
Discord bot that accepts `!image <prompt>`, sends it to a local Gemma LLM via Ollama to improve the prompt, then calls a remote ComfyUI API to generate an image and returns it to Discord. Later: `!music` command via ACE-Step.

## Infrastructure
- Bot + Gemma (Ollama): local Windows machine
- ComfyUI: offsite machine with RTX 5090, reachable via public IP — auth not yet implemented, required before going live

## Folder structure
```
discord-ai-bot/
├── .env
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── main.py
└── src/
    ├── __init__.py
    ├── bot.py
    ├── llm.py
    └── comfyui.py
```

## Working style
- Small, controlled steps only
- Explain what you're about to do before doing it
- Ask for confirmation before major changes
- No Docker, no database, no unnecessary frameworks
- Python only
- No comments unless the WHY is non-obvious
- Update CLAUDE.md at the end of each step to reflect current progress

## Progress
### Completed — Step 1
- Folder skeleton created
- Python venv at `.venv/`, dependencies installed (`discord.py`, `requests`, `python-dotenv`)
- `.gitignore`, `.env.example`, `README.md`, `requirements.txt` written
- Git initialised, first commit `49f5702` (`chore: initial project skeleton`)

### Completed — Step 2
- `src/bot.py`: Discord client with `!image` command (static reply), `on_ready` log
- `main.py`: loads `.env`, validates `DISCORD_TOKEN`, starts bot
- Bot tested successfully — comes online and responds to `!image` in Discord

### Completed — Step 3
- `src/llm.py`: `improve_prompt()` calls Ollama `/api/chat` (cloud model requires chat endpoint, not `/api/generate`)
- `bot.py`: calls `improve_prompt()` in executor, shows "Improving..." then edits to improved prompt
- `main.py`: `load_dotenv()` moved before imports so env vars are available at module load time
- Tested successfully end to end with `gpt-oss:120b-cloud`

### Completed — Natural language interface + chat
- Replaced `!image` command with `on_message` listener triggered by messages starting with `lucy`
- `"lucy ... image of ..."` → image generation pipeline
- `"lucy ..."` (anything else) → general chat via Ollama, Lucy persona
- `llm.py` refactored: shared `_ollama_chat()` helper, `improve_prompt()` and `chat()` as public functions

### Completed — Step 4
- `workflows/txt2img.json` copied into project (JuggernautXL, 1024×1536, 20 steps)
- `src/comfyui.py`: injects improved prompt into node 2, randomises seed, POSTs to `/prompt`, polls `/history/{id}`, fetches image from `/view`
- `src/bot.py`: full pipeline — improve prompt → generate image → send as Discord file attachment
- ComfyUI running at `194.93.48.43:8188` (set in `.env`, gitignored)
- Fixed Windows encoding issue on workflow JSON (utf-8 explicit open)
- Full pipeline tested and working end to end

### Completed — Admin web UI + per-guild config
- `src/config.py`: per-guild config stored in `config.json` under `{"guilds": {"id": {...}}}`, defaults applied for any missing keys
- `src/state.py`: shared runtime state — guilds and channels lists populated by bot, read by Flask
- `src/web.py`: Flask admin UI on `localhost:5000` — guild dropdown, settings per server, channel checkboxes
- `src/bot.py`: `on_guild_join` / `on_guild_remove` refresh state live — no restart needed when joining a new server
- `main.py`: Flask runs in a daemon thread alongside the bot
- `config.json` gitignored; `config.example.json` committed as template
- All settings (prefix, model, system prompt, image size/steps/CFG, allowed channels) are per-guild and hot-reload on every message

### Completed — Step 5a: img2img workflow
- `workflows/img2img.json`: built from scratch — same checkpoint/sampler as txt2img, swaps `EmptyLatentImage` for `LoadImage` → `VAEEncode`, denoise 0.75
- `src/comfyui.py`: extracted `_poll_for_image()` helper; added `generate_image_from_image()` — uploads attachment to ComfyUI `/upload/image`, injects filename + improved prompt, polls for result
- `src/bot.py`: detects image attachments on any `lucy` message; if attachment present → img2img pipeline, otherwise falls back to txt2img as before

### Completed — Step 5b: Qwen inpainting with auto-mask
- `workflows/qwen_inpaint.json`: Qwen Image Edit workflow with GroundingDINO + SAM auto-masking replacing manual clipspace mask
- `src/llm.py`: `get_inpaint_params()` returns JSON with `mask_subject` (e.g. "hair") and direct edit instruction for Qwen
- `src/comfyui.py`: `generate_image_qwen_inpaint()` uploads image, injects mask_subject into GroundingDinoSAMSegment, injects edit prompt into TextEncodeQwenImageEditPlus
- `src/bot.py`: image attachment → Qwen inpaint pipeline; no attachment → txt2img as before
- Models used: Qwen-Image-Edit fp8, Qwen2.5-VL 7B fp8 CLIP, Lightning LoRA, GroundingDINO SwinT, SAM ViT-H

### Completed — Step 6: SeedVR2 upscaling
- `workflows/upscale.json`: converted from node-graph format to ComfyUI API format — SeedVR2 DiT + VAE pipeline, upscales to 2048px
- `src/comfyui.py`: `generate_image_upscale()` uploads image, injects filename into LoadImage node 571, randomises seed in node 185
- `src/bot.py`: `lucy upscale` + image attachment → upscale pipeline (checked before inpaint branch)
- Models required on ComfyUI: `seedvr2_ema_7b_sharp_fp16.safetensors`, `ema_vae_fp16.safetensors`
- Standalone only (not auto-applied after generation — resources too limited)

### Completed — Step 7: FLUX.1 support + NSFW keyword routing
- `workflows/flux_schnell.json`: FLUX.1 Schnell workflow (4 steps, no guidance)
- `workflows/flux_dev.json`: FLUX.1 Dev workflow (20 steps, FluxGuidance node)
- `src/config.py`: added `txt2img_model`, `flux_steps`, `flux_guidance`, `nsfw_image_model` defaults
- `src/comfyui.py`: `generate_image()` routes to juggernaut/flux_schnell/flux_dev based on per-guild config
- `src/llm.py`: `improve_prompt()` accepts `nsfw` flag — uses uncensored model + explicit system prompt when true
- `src/bot.py`: detects "nsfw" keyword in message, passes flag to `improve_prompt()`
- `src/web.py`: model selector in Image Generation tab (Juggernaut/Schnell/Dev with conditional fields); NSFW model field in Language Model tab; Discord OAuth2 login added
- Models: `flux1-dev.safetensors`, `flux1-schnell.safetensors`, `ae.safetensors`, `clip_l.safetensors`, `t5xxl_fp16.safetensors` on ComfyUI machine; `dolphin-mistral` via Ollama for NSFW prompts

## Next — Step 8
Options: LoRA support, outpainting, additional edit types. Ask user what to tackle next.

## Deferred
- ComfyUI auth (open IP `194.93.48.43:8188`, no auth yet — fine for dev, needed before going public)
- ACE-Step music generation (`lucy give me music of ...`)
- Discord OAuth login for admin web UI (currently localhost only, no auth)
