from .nodes import GetOpenAIModels, OpenAIPrompt


#  Map all your custom nodes classes with the names that will be displayed in the UI.
NODE_CLASS_MAPPINGS = {
    "Get OpenAI Models": GetOpenAIModels,
    "OpenAI Prompt": OpenAIPrompt,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Get OpenAI Models": "Get OpenAI Models",
    "OpenAI Prompt": "OpenAI Prompt",
}

# Register the JavaScript directory for custom UI extensions
WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

#  Add custom API endpoint for proxying model list requests
try:
    from aiohttp import web
    from server import PromptServer
    import requests as req

    async def get_models_handler(request):
        """Proxy endpoint to fetch models from OpenAI-compatible API."""
        base_url = request.query.get("base_url", "")
        if not base_url:
            return web.json_response(
                {"error": "base_url parameter is required"}, status=400
            )

        base_url = base_url.rstrip("/")
        while base_url.endswith("/v1"):
            base_url = base_url[:-3]
        try:
            response = req.get(f"{base_url}/v1/models", timeout=10)
            response.raise_for_status()
            data = response.json()
            return web.json_response(data)
        except req.exceptions.ConnectionError:
            return web.json_response(
                {"error": "Could not connect to the API"}, status=502
            )
        except req.exceptions.Timeout:
            return web.json_response({"error": "Request timed out"}, status=504)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    # Register the route directly with ComfyUI's web app via PromptServer instance
    PromptServer.instance.app.router.add_get("/jab/models", get_models_handler)
    print("[jab] API route registered at /jab/models")

except Exception as e:
    print(f"[jab] Failed to register API routes: {e}")
