#!/bin/bash
# Post-create setup for RunPod dev container.
# Idempotent: safe to re-run on pod restart. Skips already-completed steps.
set -euo pipefail

echo "============================================"
echo "  Dev Container Setup — RunPod Eval Runner"
echo "  (Implements the Dagger logical flow documented in code/unsloth_example_1/training/RUNPOD_EVAL_WORKFLOW.md)"
echo "============================================"

# ── 1. Map generic env vars to tool-specific ones (uv) ──
export UV_PROJECT_ENVIRONMENT="${VENV_DIR:-/buildcache/venv}"
export UV_CACHE_DIR="${PKG_CACHE_DIR:-/buildcache/pkg-cache}"

# ── 2. Ensure volume mount points are writable ──
for dir in /buildcache /data /data/eval_results /data/huggingface; do
    if [ -d "$dir" ]; then
        sudo chown -R "$(id -u):$(id -g)" "$dir" 2>/dev/null || true
    else
        sudo mkdir -p "$dir"
        sudo chown -R "$(id -u):$(id -g)" "$dir"
    fi
done

# Create buildcache subdirectories
mkdir -p /buildcache/venv /buildcache/pkg-cache /buildcache/pycache \
         /buildcache/pytest /buildcache/ruff /buildcache/mypy

# ── 3. Install Python dependencies (cached on /buildcache volume) ──
VENV_MARKER="/buildcache/.uv-installed"

cd /workspace

if [ ! -f "$VENV_MARKER" ]; then
    echo ""
    echo "▸ First run: installing dependencies to /buildcache/venv ..."
    if [ -f "uv.lock" ]; then
        uv sync --locked
    else
        echo "  ⚠ uv.lock not found — running 'uv sync' without --locked."
        echo "    To restore reproducibility, generate and commit uv.lock (uv lock)."
        uv sync
    fi
    touch "$VENV_MARKER"
    echo "  ✓ Dependencies installed."
else
    echo ""
    echo "▸ Syncing dependencies (venv exists on volume) ..."
    if [ -f "uv.lock" ]; then
        uv sync --locked
    else
        echo "  ⚠ uv.lock not found — running 'uv sync' without --locked."
        echo "    To restore reproducibility, generate and commit uv.lock (uv lock)."
        uv sync
    fi
    echo "  ✓ Dependencies synced."
fi

# ── 4. Pre-download evaluation datasets (cached on /data volume) ──
MATH_CACHE="/data/huggingface/hub/datasets--nvidia--OpenMathReasoning-mini"
CHAT_CACHE="/data/huggingface/hub/datasets--mlabonne--FineTome-100k"

echo ""
echo "▸ Checking dataset cache ..."

if [ ! -d "$MATH_CACHE" ]; then
    echo "  Downloading OpenMathReasoning-mini ..."
    uv run python -c "
from datasets import load_dataset
load_dataset('nvidia/OpenMathReasoning-mini', split='cot')
print('  ✓ OpenMathReasoning-mini cached.')
"
else
    echo "  ✓ OpenMathReasoning-mini already cached."
fi

if [ ! -d "$CHAT_CACHE" ]; then
    echo "  Downloading FineTome-100k ..."
    uv run python -c "
from datasets import load_dataset
load_dataset('mlabonne/FineTome-100k', split='train')
print('  ✓ FineTome-100k cached.')
"
else
    echo "  ✓ FineTome-100k already cached."
fi

# ── 5. Verify GPU availability ──
echo ""
echo "▸ GPU status:"
uv run python -c "
import torch
if torch.cuda.is_available():
    name = torch.cuda.get_device_name(0)
    mem = torch.cuda.get_device_properties(0).total_mem / 1e9
    print(f'  ✓ GPU: {name} ({mem:.1f} GB)')
else:
    print('  ✗ No CUDA GPU detected — model inference will fail.')
" 2>/dev/null || echo "  ✗ Could not check GPU (torch not yet installed?)."

# ── 6. Check for required env vars ──
echo ""
echo "▸ Environment check:"
if [ -n "${DEEPEVAL_JUDGE_BASE_URL:-}" ]; then
    echo "  ✓ DEEPEVAL_JUDGE_BASE_URL is set: ${DEEPEVAL_JUDGE_BASE_URL}"
else
    echo "  ⚠ DEEPEVAL_JUDGE_BASE_URL not set — defaulting to http://localhost:8000/v1"
    echo "    Set it: export DEEPEVAL_JUDGE_BASE_URL='http://<judge-host>:8000/v1'"
fi

if [ -n "${DEEPEVAL_JUDGE_MODEL:-}" ]; then
    echo "  ✓ DEEPEVAL_JUDGE_MODEL is set: ${DEEPEVAL_JUDGE_MODEL}"
else
    echo "  ⚠ DEEPEVAL_JUDGE_MODEL not set — defaulting to Meta-Llama-3-8B-Instruct"
    echo "    Set it: export DEEPEVAL_JUDGE_MODEL='meta-llama/Meta-Llama-3-8B-Instruct'"
fi

if [ -n "${OPENAI_API_KEY:-}" ] || [ -n "${DEEPEVAL_JUDGE_API_KEY:-}" ]; then
    echo "  ✓ Judge API key is set (OPENAI_API_KEY or DEEPEVAL_JUDGE_API_KEY)."
else
    echo "  ⚠ No judge API key set — may still work for local vLLM, but DeepEval client may require a non-empty key."
    echo "    Set it: export DEEPEVAL_JUDGE_API_KEY='local-vllm'"
fi

# ── 7. Check for trained model ──
if [ -d "/workspace/phone_model" ] || [ -d "/data/phone_model" ]; then
    echo "  ✓ Trained model found."
else
    echo "  ⚠ phone_model/ not found. To eval the base model instead:"
    echo "    export QAT_MODEL_DIR=unsloth/Qwen3-0.6B"
fi

echo ""
echo "============================================"
echo "  Setup complete. Run evals with:"
echo "    uv run pytest tests/test_model_quality.py -v"
echo "============================================"
