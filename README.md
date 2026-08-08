# ComfyUI-jab

A ComfyUI custom node package for interacting with an OpenAI-compatible API.

## Nodes

### Get OpenAI Models
Fetches available models from a local OpenAI API instance and returns the first model as the default selection.
- **Input**: `base_url` (STRING)
- **Output**: `model` (STRING) - Selected model ID, `base_url` (STRING) - The base URL

### OpenAI Prompt
Sends a prompt to an OpenAI model and returns the response.
- **Inputs**:
  - `model` (STRING) - Model name to prompt (can be connected from Get OpenAI Models or entered manually)
  - `base_url` (STRING)
  - `prompt_text` (STRING, multiline) - The prompt text
  - `temperature` (FLOAT, optional) - Sampling temperature (default: 0.7)
  - `max_tokens` (INT, optional) - Maximum tokens to generate (default: 500)
- **Output**: `response` (STRING) - The model's response text

## Installation

1. Clone repository into `ComfyUI/custom_nodes/`
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/jab416171/comfyui-jab.git
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

For ComfyUI portable version:
```bash
python_embeded\python.exe -m pip install -r ComfyUI\custom_nodes\comfyui-jab\requirements.txt
```

## Requirements

- ComfyUI
- Python 3.8+
- requests >= 2.28.0

## Usage

1. Add the "Get OpenAI Models" node and provide your local API base URL (e.g., `http://localhost:8080`)
2. Connect the output models JSON to your workflow or manually enter a model name in the "OpenAI Prompt" node
3. Use the "OpenAI Prompt" node to send prompts and receive responses

## Example Workflow

See [`workflows/example-1.json`](workflows/example-1.json) for an example workflow.


