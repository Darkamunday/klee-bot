# discord-ai-bot

A Discord bot (Lucy) that generates and edits images using a local Ollama LLM for prompt refinement and a remote ComfyUI instance for image generation.

## Triggers

All triggers start with `lucy` (configurable per server). In DMs, no prefix is needed.

### Text to image
```
lucy image of <prompt>
lucy i want an image of <prompt>
```
The prompt is automatically improved by the LLM before generation. Uses FLUX.2 Klein by default.

### Image generation flags
| Flag | Effect |
|------|--------|
| `raw` or `exact` | Skip LLM prompt improvement — send your prompt directly |
| `nsfw` | Use uncensored model for prompt improvement |

```
lucy image of a red sports car raw
lucy image of <prompt> nsfw
```
Flags can appear anywhere in the message.

### Inpainting (attach an image)
```
lucy change the hair to blue  [+ image attachment]
lucy make the jacket red      [+ image attachment]
```
Automatically detects and masks the target region using GroundingDINO + SAM, then inpaints with Qwen Image Edit. Add `raw` to skip LLM prompt parsing and pass your instruction directly.

### Restyle / remix (attach an image)
```
lucy restyle this as anime          [+ image attachment]
lucy remix into a cyberpunk scene   [+ image attachment]
lucy variation                      [+ image attachment]
```
Whole-image transformation using FLUX.2 Klein i2i. Add `raw` or `nsfw` as needed.

### Describe / analyse an image (attach an image)
```
lucy describe this                  [+ image attachment]
lucy analyse this                   [+ image attachment]
lucy what is in this image          [+ image attachment]
lucy what's in this                 [+ image attachment]
```
Sends the image to the configured vision model (gemma3:12b by default).

### Upscale (attach an image)
```
lucy upscale  [+ image attachment]
```
Upscales to 2048px using SeedVR2.

### Chat
```
lucy <anything>
```
General conversation using the Lucy persona via Ollama.

### Follow-up on last image
After any image is generated, reference it in a follow-up without re-uploading:
```
lucy change that one to red hair
lucy restyle that image as cyberpunk
lucy describe that photo
lucy upscale that one
```
Trigger phrases: `that image`, `last image`, `that one`, `use that`, `take that`, `that photo`, `that pic`, `the image you`

### Reply chaining
Reply directly to any of Lucy's messages to continue the conversation with full context — no need to re-type the prefix.

---

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com/) running locally with your chosen models pulled
- ComfyUI on a remote machine with the following models:
  - `flux-2-klein-9b-fp8.safetensors` + `qwen_3_8b_fp8mixed.safetensors` + `full_encoder_small_decoder.safetensors` (FLUX.2 Klein)
  - Qwen Image Edit fp8 + Lightning LoRA + Qwen2.5-VL 7B fp8 CLIP (inpainting)
  - `seedvr2_ema_7b_sharp_fp16.safetensors` + `ema_vae_fp16.safetensors` (upscaling)
  - GroundingDINO SwinT + SAM ViT-H (auto-masking)
  - Custom nodes: [comfyui_segment_anything](https://github.com/storyicon/comfyui_segment_anything)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
cp .env.example .env        # then fill in your values
python main.py
```

## Environment variables

See `.env.example` for all required variables.

## Admin UI

A Flask admin panel runs at `http://localhost:5000` — configure per-guild settings:

- **Bot** — trigger prefix
- **Language Model** — Ollama model, inpaint model, vision model, NSFW model, system prompt
- **Image Generation** — model selector (FLUX.2 Klein / Juggernaut XL / FLUX.1), dimensions, steps, CFG
- **Flux2 Restyle** — steps and CFG for the i2i restyle pipeline
- **Inpainting** — GroundingDINO threshold, mask expand, blur radius
- **Upscaling** — output resolution, colour correction mode
- **Channels** — restrict Lucy to specific channels (empty = all channels)

## Planned

- Selectable personalities per guild — pre-built personas choosable via admin UI
- `lucy give me music of <prompt>` — music generation via ACE-Step
- ComfyUI auth (currently open IP, fine for dev)
