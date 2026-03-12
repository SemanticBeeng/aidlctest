# Running Evaluations on RunPod — Dev Container Workflow

End-to-end guide for running the Qwen3-0.6B QAT evaluation pipeline on
RunPod using a VS Code dev container with persistent network volumes.

---

## Architecture Overview

```
Local Machine                          RunPod Pod (GPU)
┌─────────────┐    SSH tunnel    ┌─────────────────────────────────────┐
│  VS Code    │◄────────────────►│  Dev Container                      │
│  + Remote   │                  │  ┌───────────────────────────────┐  │
│    SSH ext  │                  │  │ /workspace   ← git clone      │  │
│             │                  │  │ /env         ← Network Vol 1  │  │
│             │                  │  │   virtualenvs/  (Poetry venv) │  │
│             │                  │  │   pip-cache/                  │  │
│             │                  │  │ /data        ← Network Vol 2  │  │
│             │                  │  │   huggingface/  (datasets)    │  │
│             │                  │  │   eval_results/ (output JSON) │  │
│             │                  │  │   phone_model/  (trained QAT) │  │
│             │                  │  └───────────────────────────────┘  │
│             │                  │  GPU: T4 / A10G (CUDA passthrough)  │
└─────────────┘                  └─────────────────────────────────────┘
```

**Key principle**: The pod is disposable. Network volumes persist. You can
destroy and recreate pods without losing your Python environment, datasets,
or evaluation results.

---

## File Reference

| File | Purpose |
|------|---------|
| [`.devcontainer/Dockerfile`](../.devcontainer/Dockerfile) | Container image: PyTorch + CUDA + Poetry + SSH |
| [`.devcontainer/devcontainer.json`](../.devcontainer/devcontainer.json) | VS Code dev container config: volumes, env vars, extensions |
| [`.devcontainer/setup.sh`](../.devcontainer/setup.sh) | Post-create script: installs deps, caches datasets, checks GPU |
| [`training/evaluate_model.py`](evaluate_model.py) | Standalone evaluation orchestrator (10 metrics, 5 suites) |
| [`tests/conftest.py`](../tests/conftest.py) | Session-scoped pytest fixtures for model/data/test-cases |
| [`tests/test_model_quality.py`](../tests/test_model_quality.py) | 13 parametrized test classes (~210 tests) |
| [`training/EVALUATIONS.md`](EVALUATIONS.md) | Detailed evaluation guide (metrics, thresholds, interpretation) |
| [`pyproject.toml`](../pyproject.toml) | Poetry dependencies (deepeval, pytest, unsloth, etc.) |

---

## Prerequisites

1. **RunPod account** with billing configured
2. **SSH key** uploaded to RunPod (Dashboard → Settings → SSH Keys)
3. **VS Code** with these extensions installed locally:
   - [Remote - SSH](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-ssh)
   - [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
4. **OpenAI API key** for LLM-as-judge metrics
5. (Optional) **Confident AI login** for dashboard tracking: `deepeval login`

---

## Step 1: Create Network Volumes (one-time)

In RunPod Dashboard → **Storage** → **Network Volumes**, create two volumes
in the **same data center region** you'll launch pods in:

| Volume Name | Size | Purpose |
|-------------|------|---------|
| `eval-python-env` | 20 GB | Poetry virtualenvs, pip cache |
| `eval-datasets` | 50 GB | HuggingFace datasets, trained models, eval results |

> **Cost**: Network volumes cost ~$0.07/GB/month when idle.
> 20 + 50 GB = ~$4.90/month if kept attached.

---

## Step 2: Launch Pod

### Option A: RunPod Dashboard (UI)

1. **GPU**: Select **NVIDIA T4** (16 GB, cheapest — sufficient for 0.6B model)
   - Or **A10G** (24 GB) if running QAT regression tests (two models loaded)
2. **Template**: Select **RunPod PyTorch 2.4.0**
3. **Network Volumes**: Attach both volumes:
   - `eval-python-env` → mount at `/env`
   - `eval-datasets` → mount at `/data`
4. **Expose ports**: `22` (SSH)
5. **Environment Variables**:
   - `OPENAI_API_KEY` = `sk-...`
6. Launch the pod

### Option B: runpodctl CLI

```bash
pip install runpodctl

# Authenticate
runpodctl config --apiKey "YOUR_RUNPOD_API_KEY"

# Launch pod with both network volumes
runpodctl create pod \
  --name "eval-runner" \
  --gpuType "NVIDIA GeForce RTX 4090" \
  --gpuCount 1 \
  --imageName "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04" \
  --volumeId "vol_abc123" \
  --volumeMountPath "/env" \
  --env "OPENAI_API_KEY=sk-..." \
  --ports "22/tcp"

# Note: attach second volume via dashboard or API call
```

---

## Step 3: Connect VS Code via SSH

1. Copy the SSH connection string from RunPod Dashboard → Pod → **Connect**
2. Add to `~/.ssh/config`:

```
Host runpod-eval
    HostName <pod-ip-or-proxy>
    User root
    Port <dynamic-port>
    IdentityFile ~/.ssh/id_runpod
    StrictHostKeyChecking no
```

3. In VS Code: **Ctrl+Shift+P** → `Remote-SSH: Connect to Host` → `runpod-eval`
4. Once connected, clone the repo:

```bash
cd /workspace
git clone https://github.com/SemanticBeeng/aidlctest.git .
```

5. VS Code detects `.devcontainer/devcontainer.json` and prompts:
   **"Reopen in Container"** — click it.

6. The dev container builds, then runs [`setup.sh`](../.devcontainer/setup.sh):
   - Installs Poetry dependencies to `/env/virtualenvs/`
   - Downloads datasets to `/data/huggingface/`
   - Verifies GPU and env vars

---

## Step 4: Run Evaluations

All commands assume you're in the dev container terminal in VS Code.

### Quick smoke test (3 math + 3 chat, ~2 min)

```bash
cd /workspace/code/unsloth_example_1
poetry run pytest tests/test_model_quality.py -v -k "TestMathCorrectness" --co | head -5
```

### Full eval suite (~15 min, ~$2-5 OpenAI cost)

```bash
poetry run pytest tests/test_model_quality.py -v
```

### Individual test classes

```bash
# Math-only (COT format, think tokens, answer extraction)
poetry run pytest tests/test_model_quality.py -v \
  -k "TestMathCorrectness or TestCOTFormat or TestThinkToken or TestFinalAnswer"

# Chat-only (relevancy, toxicity, bias, instruction following)
poetry run pytest tests/test_model_quality.py -v \
  -k "TestChat or TestInstruction or TestResponseCompleteness"

# Multi-turn coherence
poetry run pytest tests/test_model_quality.py -v -k "TestMultiTurn"

# Programmatic checks only (no OpenAI API calls)
poetry run pytest tests/test_model_quality.py -v \
  -k "TestThinkToken or TestExpectedAnswer or TestAnswerExtractability"
```

### Standalone orchestrator (outside pytest)

```bash
poetry run python training/evaluate_model.py
```

### With Confident AI dashboard tracking

```bash
deepeval login                                           # one-time
poetry run deepeval test run tests/test_model_quality.py  # auto-pushes results
```

---

## Step 5: Retrieve Results

Results are written to the `/data` network volume and persist across pod restarts.

```bash
ls /data/eval_results/

# Copy to local machine (from your local terminal)
scp -r runpod-eval:/data/eval_results/ ./eval_results_$(date +%Y%m%d)/
```

---

## Step 6: Stop Pod

When done, stop (don't delete) the pod to retain volumes:

```bash
# Via CLI
runpodctl stop pod <pod-id>

# Or in dashboard: Pod → Stop
```

**Cost when stopped**: $0 for the pod, ~$4.90/month for the two network volumes.

---

## Network Volume Contents

After first run, the volumes contain:

### `/env` — Python Environment (20 GB)

```
/env/
├── .poetry-installed        ← marker: skip reinstall on next boot
├── pip-cache/               ← pip download cache
└── virtualenvs/
    └── qwen3-phone-deployment-py3.11/
        ├── bin/python       ← interpreter used by VS Code
        ├── lib/python3.11/site-packages/
        │   ├── deepeval/
        │   ├── torch/
        │   ├── unsloth/
        │   ├── transformers/
        │   └── ...
        └── ...
```

### `/data` — Datasets & Artifacts (50 GB)

```
/data/
├── huggingface/
│   └── hub/
│       ├── datasets--nvidia--OpenMathReasoning-mini/
│       └── datasets--mlabonne--FineTome-100k/
├── phone_model/             ← trained QAT model (copy here or symlink)
│   ├── config.json
│   ├── model.safetensors
│   └── tokenizer.json
└── eval_results/
    ├── math_eval_20260312_143000.json
    └── chat_eval_20260312_143000.json
```

---

## Evaluating the Base Model (no training needed)

To run a pre-training baseline evaluation against the unmodified Qwen3-0.6B:

```bash
# Override model path to use HuggingFace base model
export QAT_MODEL_DIR="unsloth/Qwen3-0.6B"

poetry run pytest tests/test_model_quality.py -v
```

This downloads the base model to `/data/huggingface/` and evaluates it.
Compare results against a post-training run to measure QAT impact.

> **Note**: The base model has not been fine-tuned on COT data, so
> `TestCOTFormatCompliance`, `TestThinkTokenUsage`, and
> `TestExpectedAnswerMatch` will likely show lower scores. This is expected
> and provides a useful baseline.

---

## Troubleshooting

### Pod can't find network volumes

Ensure the volumes are in the **same data center region** as the pod.
Volumes cannot be mounted cross-region.

### `poetry install` is slow

First run downloads ~4 GB of packages. Subsequent runs use the cached
venv on `/env` and complete in seconds. If the venv seems corrupted:

```bash
rm /env/.poetry-installed
bash .devcontainer/setup.sh
```

### Out of VRAM

The 0.6B model needs ~3-4 GB. If running QAT regression (two models),
you need ~6-8 GB. Use a T4 (16 GB) or A10G (24 GB). Check usage:

```bash
nvidia-smi
```

### OpenAI API errors

LLM-as-judge metrics require a valid `OPENAI_API_KEY`. Programmatic tests
(`TestThinkTokenUsage`, `TestExpectedAnswerMatch`, `TestAnswerExtractability`)
run without an API key.

### VS Code can't find Python interpreter

The interpreter path is set in [`devcontainer.json`](../.devcontainer/devcontainer.json):
```
/env/virtualenvs/qwen3-phone-deployment-py3.11/bin/python
```
If Poetry created the venv with a different name, check:
```bash
ls /env/virtualenvs/
```
Then update the `python.defaultInterpreterPath` setting.
