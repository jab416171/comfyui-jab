#  Package Modules
import hashlib
import json
import logging
import os
from typing import List, Tuple
from tqdm import tqdm

import comfy.model_management
import comfy.utils
import folder_paths
import requests
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARN)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[jab] %(levelname)s %(message)s"))
    logger.addHandler(handler)

#  Basic practice to get paths from ComfyUI
custom_nodes_script_dir = os.path.dirname(os.path.abspath(__file__))
custom_nodes_model_dir = os.path.join(folder_paths.models_dir, "comfyui-jab")
custom_nodes_output_dir = os.path.join(
    folder_paths.get_output_directory(), "comfyui-jab"
)


def _normalize_base_url(base_url: str) -> str:
    """Remove trailing slashes and /v1 suffix from base_url to avoid double paths."""
    base_url = base_url.rstrip("/")
    while base_url.endswith("/v1"):
        base_url = base_url[:-3]
    return base_url


def _get_dynamic_model_list(base_url: str) -> List[str]:
    """Fetch model list from the API at the given base_url."""
    base_url = _normalize_base_url(base_url)
    try:
        response = requests.get(f"{base_url}/v1/models", timeout=10)
        response.raise_for_status()
        data = response.json()
        model_ids = [m["id"] for m in data.get("data", [])]
        print(f"Fetched {len(model_ids)} models from {base_url}: {model_ids}")
        return model_ids  # Return empty list if no models
    except Exception as e:
        print(f"Error fetching models from {base_url}: {e}")
        return []  # Return empty list on error


#  OpenAI Node 1: Get List of Models with Dropdown Selection
class GetOpenAIModels:
    """
    Node to fetch a list of available models from a local OpenAI API instance
    and provide a dropdown for model selection.
    Input: base_url (string - can be connected or set directly)
    Output: model (STRING - the selected model ID)
    """

    RETURN_TYPES = ("STRING","STRING")
    RETURN_NAMES = ("model","base_url")
    FUNCTION = "get_models"
    CATEGORY = "OpenAI"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "base_url": ("STRING", {"default": "http://localhost:8080"}),
                "model": ("STRING", {}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, base_url, model):
        models = _get_dynamic_model_list(base_url)
        return hashlib.sha256(",".join(sorted(models)).encode()).hexdigest()

    def get_models(
        self,
        base_url: str,
        model: str,
    ) -> Tuple[str]:
        # Fetch the current model list
        model_list = _get_dynamic_model_list(base_url)

        # If model is empty or not in the list, return the first model if available, otherwise empty string
        if not model or model not in model_list:
            if model_list:
                return (model_list[0],)
            return ("",)
        return (model,base_url)


def _image_to_base64(image) -> Tuple[str, str]:
    """Convert a ComfyUI image (tensor or numpy array) to base64 and return (base64_string, mime_type)."""
    import base64
    import io

    if hasattr(image, "cpu"):
        image = image.cpu()
    if hasattr(image, "numpy"):
        image = image.numpy()

    if image.ndim == 4:
        image = image[0]

    if image.dtype == np.float32 or image.dtype == np.float64:
        image = np.clip(image, 0, 1) * 255

    img = Image.fromarray(image.astype(np.uint8))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    image_bytes = buf.getvalue()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    return image_base64, "image/png"


#  OpenAI Node 2: Prompt a Model
class OpenAIPrompt:
    """
    Node to send a prompt to an OpenAI model and get the response.
    Inputs: model (STRING from GetOpenAIModels), base_url (STRING), prompt (STRING), image (IMAGE - optional)
    Output: response (STRING), thinking (STRING)
    """

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("response", "thinking")
    FUNCTION = "prompt_model"
    CATEGORY = "OpenAI"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("STRING", {"default": ""}),
                "base_url": ("STRING", {"default": "http://localhost:8080"}),
                "prompt_text": (
                    "STRING",
                    {"default": "What can you do?", "multiline": True},
                ),
            },
            "optional": {
                "image": ("IMAGE",),
                "seed": (
                    "INT",
                    {"default": 0, "min": 0, "max": 18446744073709551615, "step": 1},
                ),
                "enable_thinking": (
                    "BOOLEAN",
                    {"default": True},
                ),
                "temperature": (
                    "FLOAT",
                    {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1},
                ),
                "max_tokens": (
                    "INT",
                    {"default": 500, "min": 1, "max": 4096, "step": 1},
                ),
            },
        }

    @classmethod
    def IS_CHANGED(cls, model, base_url, prompt_text, image=None, seed=0, enable_thinking=True, temperature=0.7, max_tokens=500):
        import hashlib
        parts = [
            str(model) if model is not None else "None",
            str(base_url) if base_url is not None else "None",
            str(prompt_text) if prompt_text is not None else "None",
            str(seed),
            str(enable_thinking),
            str(temperature),
            str(max_tokens),
        ]
        if image is not None:
            if hasattr(image, "tobytes"):
                parts.append(image.tobytes().hex())
            else:
                parts.append(str(image.shape))
        return hashlib.sha256(",".join(parts).encode()).hexdigest()

    def prompt_model(
        self,
        model: str,
        base_url: str,
        prompt_text: str,
        image: np.ndarray = None,
        seed: int = 0,
        enable_thinking: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Tuple[str]:
        # Determine the prompt content based on mode
        prompt = prompt_text

        # Normalize base_url to avoid double paths like /v1/v1
        base_url = _normalize_base_url(base_url)

        if not model or model.startswith("Error:"):
            logger.debug("Early return: model=%r", model)
            return (model, "")

        import time

        max_retries = 30
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                # Build the request payload for chat completions
                if image is not None:
                    image_b64, mime_type = _image_to_base64(image[0])
                    messages_content = [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ]
                else:
                    messages_content = prompt

                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": messages_content}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                }
                if seed >= 0:
                    payload["seed"] = seed
                if not enable_thinking:
                    payload["extra_body"] = {"thinking_budget_tokens": 0, "reasoning": "none"}

                logger.debug("Sending request: model=%s base_url=%s max_tokens=%d", model, base_url, max_tokens)
                response = requests.post(
                    f"{base_url}/v1/chat/completions", json=payload, stream=True, timeout=120
                )

                if response.status_code == 500:
                    if attempt < max_retries - 1:
                        logger.warning("Model loading, retrying in %ds (attempt %d/%d)", retry_delay, attempt + 1, max_retries)
                        time.sleep(retry_delay)
                        continue
                    return (f"Error: Model still loading after {max_retries} attempts", "")

                response.raise_for_status()

                accumulated_content = ""
                accumulated_reasoning = ""
                final_message = None
                pbar = comfy.utils.ProgressBar(max_tokens)
                t = tqdm(total=max_tokens, desc="Generating tokens", unit="token")

                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        raw = line[6:].decode() if line.startswith(b"data: ") else line.decode()
                        if raw == "[DONE]":
                            continue
                        data = json.loads(raw)
                        choice = data.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        if "content" in delta and delta["content"] is not None:
                            accumulated_content += delta["content"]
                            pbar.update(1)
                            t.update(len(delta["content"]))
                        if "reasoning_content" in delta and delta["reasoning_content"] is not None:
                            accumulated_reasoning += delta["reasoning_content"]
                        if "reasoning" in delta and delta["reasoning"] is not None:
                            accumulated_reasoning += delta["reasoning"]
                        if choice.get("finish_reason") is not None:
                            final_message = choice.get("message", {})
                    except json.JSONDecodeError:
                        logger.debug("Skipping non-JSON SSE line: %s", line)
                    comfy.model_management.throw_exception_if_processing_interrupted()

                logger.debug("Stream complete: content_len=%d reasoning_len=%d", len(accumulated_content), len(accumulated_reasoning))

                if final_message is None:
                    final_message = {}

                response_text = final_message.get("content") or accumulated_content
                thinking_text = final_message.get("reasoning") or accumulated_reasoning or final_message.get("reasoning_content", "")

                logger.debug("Returning: response_len=%d thinking_len=%d", len(response_text), len(thinking_text))
                return (response_text, thinking_text)
            except requests.exceptions.ConnectionError:
                logger.error("Connection error")
                return ("Error: Could not connect to the API", "")
            except requests.exceptions.Timeout:
                logger.error("Request timed out")
                return ("Error: Request timed out", "")
            except (json.JSONDecodeError, KeyError, IndexError):
                logger.error("Invalid response format", exc_info=True)
                return ("Error: Invalid response format from API", "")
            except Exception as e:
                logger.error("Unexpected error: %s", e, exc_info=True)
                return (f"Error: {str(e)}", "")
