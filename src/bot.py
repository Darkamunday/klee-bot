import asyncio
import re
import discord
from src.llm import improve_prompt, get_inpaint_params, chat, describe_image
from src.comfyui import generate_image, generate_image_qwen_inpaint, generate_image_upscale, generate_image_flux2_i2i
from src import config, state

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

MAX_HISTORY = 10
RECALL_KEYWORDS = ("that image", "last image", "that one", "use that", "take that", "the image you", "that photo", "that pic")


async def _build_history(message, prefix: str) -> list:
    history = []
    msg = message
    for _ in range(MAX_HISTORY):
        if msg.reference is None or msg.reference.resolved is None:
            break
        parent = msg.reference.resolved
        parent_content = parent.content.strip()
        if parent.author == client.user:
            history.insert(0, {"role": "assistant", "content": parent_content})
        else:
            text = parent_content
            if text.lower().startswith(prefix):
                text = text[len(prefix):].strip()
            if text:
                history.insert(0, {"role": "user", "content": text})
        msg = parent
    return history


def _refresh_state():
    state.guilds = [{"id": g.id, "name": g.name} for g in client.guilds]
    state.channels = [
        {"id": ch.id, "name": ch.name, "guild_id": g.id, "guild": g.name}
        for g in client.guilds
        for ch in g.text_channels
    ]


@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    _refresh_state()
    print(f"Connected to {len(state.guilds)} guild(s), {len(state.channels)} text channels")


@client.event
async def on_guild_join(guild):
    print(f"Joined new guild: {guild.name}")
    _refresh_state()


@client.event
async def on_guild_remove(guild):
    print(f"Removed from guild: {guild.name}")
    _refresh_state()


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    is_dm = not message.guild
    guild_id = message.guild.id if not is_dm else 0
    cfg = config.load(guild_id)
    content = message.content.strip()
    prefix = cfg["prefix"].lower()

    if not is_dm:
        allowed = cfg.get("allowed_channels", [])
        if allowed and message.channel.id not in allowed:
            return

    is_reply_to_bot = (
        message.reference is not None
        and message.reference.resolved is not None
        and message.reference.resolved.author == client.user
    )
    if not is_dm and not content.lower().startswith(prefix) and not is_reply_to_bot:
        return

    lower = content.lower()

    image_attachments = [
        a for a in message.attachments
        if (a.content_type and a.content_type.startswith("image/"))
        or a.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
    ]

    if not image_attachments and any(kw in lower for kw in RECALL_KEYWORDS):
        stored = state.last_images.get(message.channel.id)
        if stored:
            class _Recalled:
                filename = stored["filename"]
                content_type = "image/png"
                async def read(self): return stored["bytes"]
            image_attachments = [_Recalled()]

    describe_keywords = ("describe", "analys", "analyze", "what is", "what's in", "whats in")
    is_describe = image_attachments and any(kw in lower for kw in describe_keywords)

    if is_describe:
        attachment = image_attachments[0]
        msg = await message.reply("Analysing image...")
        try:
            attachment_bytes = await attachment.read()
            user_prompt = content[len(prefix):].strip() if content.lower().startswith(prefix) else content.strip()
            async with message.channel.typing():
                description = await asyncio.get_event_loop().run_in_executor(
                    None, describe_image, attachment_bytes, user_prompt, guild_id
                )
            await msg.edit(content=description)
        except Exception as e:
            await msg.edit(content=f"Error: {e}")

    elif any(kw in lower for kw in ("restyle", "remix", "variation")) and image_attachments:
        attachment = image_attachments[0]
        prompt_text = content[len(prefix):].strip() if content.lower().startswith(prefix) else content.strip()
        nsfw = "nsfw" in lower
        raw = bool(re.search(r'\b(raw|exact)\b', lower))
        msg = await message.reply("Restyling...")
        try:
            attachment_bytes = await attachment.read()
            if raw:
                improved = prompt_text
            else:
                improved = await asyncio.get_event_loop().run_in_executor(
                    None, improve_prompt, prompt_text, guild_id, nsfw
                )
            await msg.edit(content=f"Restyling: *{improved}*")
            async with message.channel.typing():
                image_bytes = await asyncio.get_event_loop().run_in_executor(
                    None, generate_image_flux2_i2i, improved, attachment_bytes, attachment.filename, guild_id
                )
            state.last_images[message.channel.id] = {"bytes": image_bytes, "filename": "restyled.png"}
            await message.channel.send(
                content=f"```\n{improved}\n```",
                file=discord.File(fp=__import__("io").BytesIO(image_bytes), filename="restyled.png")
            )
            await msg.delete()
        except Exception as e:
            await msg.edit(content=f"Error: {e}")

    elif "upscale" in lower and image_attachments:
        attachment = image_attachments[0]
        msg = await message.reply("Upscaling...")
        try:
            attachment_bytes = await attachment.read()
            async with message.channel.typing():
                image_bytes = await asyncio.get_event_loop().run_in_executor(
                    None, generate_image_upscale, attachment_bytes, attachment.filename, guild_id
                )
            await message.channel.send(
                file=discord.File(fp=__import__("io").BytesIO(image_bytes), filename="upscaled.png")
            )
            await msg.delete()
        except Exception as e:
            await msg.edit(content=f"Error: {e}")

    elif "image of" in lower or image_attachments or (re.search(r'\bimage\b', lower) and bool(re.search(r'\b(raw|exact)\b', lower))):
        if image_attachments:
            prompt_text = content[len(prefix):].strip()
            if not prompt_text:
                await message.reply("Describe what to do with the image.")
                return
        elif "image of" in lower:
            idx = lower.index("image of") + len("image of")
            prompt_text = content[idx:].strip()
            if not prompt_text:
                await message.reply("What should the image be of?")
                return
        else:
            idx = lower.index("image") + len("image")
            prompt_text = content[idx:].strip()
            if not prompt_text:
                await message.reply("What should the image be of?")
                return

        nsfw = "nsfw" in lower
        raw = bool(re.search(r'\b(raw|exact)\b', lower))
        msg = await message.reply("Improving your prompt..." if not raw else "Generating...")
        try:
            if image_attachments:
                attachment = image_attachments[0]
                attachment_bytes = await attachment.read()
                if raw:
                    mask_subject = "subject"
                    improved = prompt_text
                else:
                    await msg.edit(content="Analysing your image...")
                    params = await asyncio.get_event_loop().run_in_executor(
                        None, get_inpaint_params, prompt_text, guild_id, nsfw
                    )
                    mask_subject = params.get("mask_subject", "subject")
                    improved = params.get("prompt", prompt_text)
                await msg.edit(content=f"Inpainting *{mask_subject}*: *{improved}*")
                async with message.channel.typing():
                    image_bytes = await asyncio.get_event_loop().run_in_executor(
                        None, generate_image_qwen_inpaint, improved, mask_subject, attachment_bytes, attachment.filename, guild_id
                    )
            else:
                if raw:
                    improved = prompt_text
                else:
                    improved = await asyncio.get_event_loop().run_in_executor(
                        None, improve_prompt, prompt_text, guild_id, nsfw
                    )
                await msg.edit(content=f"Generating image for: *{improved}*")
                async with message.channel.typing():
                    image_bytes = await asyncio.get_event_loop().run_in_executor(
                        None, generate_image, improved, guild_id
                    )

            state.last_images[message.channel.id] = {"bytes": image_bytes, "filename": "image.png"}
            await message.channel.send(
                content=f"```\n{improved}\n```",
                file=discord.File(fp=__import__("io").BytesIO(image_bytes), filename="image.png")
            )
            await msg.delete()
        except Exception as e:
            await msg.edit(content=f"Error: {e}")
    else:
        user_message = content[len(prefix):].strip() if content.lower().startswith(prefix) else content.strip()
        history = await _build_history(message, prefix)
        msg = await message.reply("Thinking...")
        try:
            reply = await asyncio.get_event_loop().run_in_executor(
                None, chat, user_message, guild_id, history
            )
            await msg.edit(content=reply)
        except Exception as e:
            await msg.edit(content=f"Error: {e}")
