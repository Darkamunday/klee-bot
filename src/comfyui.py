import copy
import json
import os
import random
import time
import requests
from src import config

COMFYUI_BASE_URL = os.getenv("COMFYUI_BASE_URL", "http://localhost:8188")

_WORKFLOWS_DIR = os.path.join(os.path.dirname(__file__), "..", "workflows")

def _load_workflow(name: str) -> dict:
    with open(os.path.join(_WORKFLOWS_DIR, name), encoding="utf-8") as f:
        return json.load(f)

def _get_workflow(name: str) -> dict:
    return _load_workflow(name)


def _poll_for_image(prompt_id: str) -> bytes:
    for _ in range(120):
        time.sleep(2)
        history = requests.get(f"{COMFYUI_BASE_URL}/history/{prompt_id}", timeout=10)
        history.raise_for_status()
        data = history.json()
        if prompt_id not in data:
            continue
        outputs = data[prompt_id]["outputs"]
        for node_output in outputs.values():
            if "images" in node_output:
                image_info = node_output["images"][0]
                img = requests.get(
                    f"{COMFYUI_BASE_URL}/view",
                    params={"filename": image_info["filename"], "subfolder": image_info["subfolder"], "type": image_info["type"]},
                    timeout=30,
                )
                img.raise_for_status()
                return img.content
    raise TimeoutError("ComfyUI did not return an image within 4 minutes")


def generate_image(prompt: str, guild_id: int) -> bytes:
    cfg = config.load(guild_id)
    model = cfg.get("txt2img_model", "juggernaut")

    if model == "qwen_lora":
        workflow = _get_workflow("qwen_lora_t2i.json")
        workflow["87"]["inputs"]["text"] = prompt
        workflow["91"]["inputs"]["seed"] = random.randint(0, 2**32 - 1)
        workflow["141:138"]["inputs"]["width"] = cfg["image_width"]
        workflow["141:138"]["inputs"]["height"] = cfg["image_height"]
    elif model == "flux2_klein":
        workflow = _get_workflow("flux2_t2i.json")
        workflow["76"]["inputs"]["value"] = prompt
        workflow["77:88"]["inputs"]["value"] = cfg["image_width"]
        workflow["77:89"]["inputs"]["value"] = cfg["image_height"]
        workflow["77:90"]["inputs"]["noise_seed"] = random.randint(0, 2**32 - 1)
        workflow["77:97"]["inputs"]["steps"] = cfg["flux2_t2i_steps"]
        workflow["77:94"]["inputs"]["cfg"] = cfg["flux2_t2i_cfg"]
    elif model in ("flux_schnell", "flux_dev"):
        wf_name = "flux_schnell.json" if model == "flux_schnell" else "flux_dev.json"
        workflow = _get_workflow(wf_name)
        workflow["4"]["inputs"]["text"] = prompt
        workflow["5"]["inputs"]["width"] = cfg["image_width"]
        workflow["5"]["inputs"]["height"] = cfg["image_height"]
        workflow["6"]["inputs"]["noise_seed"] = random.randint(0, 2**32 - 1)
        if model == "flux_dev":
            workflow["8"]["inputs"]["steps"] = cfg["flux_steps"]
            workflow["13"]["inputs"]["guidance"] = cfg["flux_guidance"]
    else:
        workflow = _get_workflow("txt2img.json")
        workflow["2"]["inputs"]["text"] = prompt
        workflow["4"]["inputs"]["width"] = cfg["image_width"]
        workflow["4"]["inputs"]["height"] = cfg["image_height"]
        workflow["5"]["inputs"]["steps"] = cfg["image_steps"]
        workflow["5"]["inputs"]["cfg"] = cfg["image_cfg"]
        workflow["5"]["inputs"]["seed"] = random.randint(0, 2**32 - 1)

    resp = requests.post(f"{COMFYUI_BASE_URL}/prompt", json={"prompt": workflow}, timeout=30)
    resp.raise_for_status()
    return _poll_for_image(resp.json()["prompt_id"])



def generate_image_qwen_inpaint(prompt: str, mask_subject: str, image_bytes: bytes, filename: str, guild_id: int) -> bytes:
    upload = requests.post(
        f"{COMFYUI_BASE_URL}/upload/image",
        files={"image": (filename, image_bytes)},
        timeout=30,
    )
    upload.raise_for_status()
    uploaded_name = upload.json()["name"]

    cfg = config.load(guild_id)
    workflow = _get_workflow("qwen_inpaint.json")
    workflow["101"]["inputs"]["image"] = uploaded_name
    workflow["202"]["inputs"]["prompt"] = mask_subject
    workflow["202"]["inputs"]["threshold"] = cfg["inpaint_threshold"]
    workflow["28"]["inputs"]["expand"] = cfg["inpaint_expand"]
    workflow["28"]["inputs"]["blur_radius"] = cfg["inpaint_blur_radius"]
    workflow["53"]["inputs"]["prompt"] = prompt
    workflow["43"]["inputs"]["seed"] = random.randint(0, 2**32 - 1)

    resp = requests.post(f"{COMFYUI_BASE_URL}/prompt", json={"prompt": workflow}, timeout=30)
    resp.raise_for_status()
    return _poll_for_image(resp.json()["prompt_id"])


def generate_image_upscale(image_bytes: bytes, filename: str, guild_id: int) -> bytes:
    upload = requests.post(
        f"{COMFYUI_BASE_URL}/upload/image",
        files={"image": (filename, image_bytes)},
        timeout=30,
    )
    upload.raise_for_status()
    uploaded_name = upload.json()["name"]

    cfg = config.load(guild_id)
    workflow = _get_workflow("upscale.json")
    workflow["571"]["inputs"]["image"] = uploaded_name
    workflow["185"]["inputs"]["seed"] = random.randint(0, 2**32 - 1)
    workflow["185"]["inputs"]["resolution"] = cfg["upscale_resolution"]
    workflow["185"]["inputs"]["color_correction"] = cfg["upscale_color_correction"]

    resp = requests.post(f"{COMFYUI_BASE_URL}/prompt", json={"prompt": workflow}, timeout=30)
    resp.raise_for_status()
    return _poll_for_image(resp.json()["prompt_id"])



def generate_image_flux2_i2i(prompt: str, image_bytes: bytes, filename: str, guild_id: int) -> bytes:
    upload = requests.post(
        f"{COMFYUI_BASE_URL}/upload/image",
        files={"image": (filename, image_bytes)},
        timeout=30,
    )
    upload.raise_for_status()
    uploaded_name = upload.json()["name"]

    cfg = config.load(guild_id)
    workflow = _get_workflow("flux2_i2i.json")
    workflow["76"]["inputs"]["image"] = uploaded_name
    workflow["75:74"]["inputs"]["text"] = prompt
    workflow["75:73"]["inputs"]["noise_seed"] = random.randint(0, 2**32 - 1)
    workflow["75:62"]["inputs"]["steps"] = cfg["flux2_i2i_steps"]
    workflow["75:63"]["inputs"]["cfg"] = cfg["flux2_i2i_cfg"]

    resp = requests.post(f"{COMFYUI_BASE_URL}/prompt", json={"prompt": workflow}, timeout=30)
    resp.raise_for_status()
    return _poll_for_image(resp.json()["prompt_id"])
