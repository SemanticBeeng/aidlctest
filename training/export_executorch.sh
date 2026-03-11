#!/usr/bin/env bash
# ExecuTorch Export Script for Qwen3-0.6B
# ========================================
# Extracted from Unsloth Colab notebook.
# Run this AFTER training completes and phone_model/ directory exists.
#
# Usage: bash export_executorch.sh [MODEL_DIR] [OUTPUT_NAME]
#
# Defaults:
#   MODEL_DIR   = phone_model
#   OUTPUT_NAME = qwen3_0.6B_model.pte

set -euo pipefail

MODEL_DIR="${1:-phone_model}"
OUTPUT_NAME="${2:-qwen3_0.6B_model.pte}"
CONFIG_FILE="0.6B_config.json"
CONVERTED_WEIGHTS="pytorch_model_converted.bin"
CONFIG_URL="https://raw.githubusercontent.com/pytorch/executorch/main/examples/models/qwen3/config/0_6b_config.json"

echo "=== Step 1/3: Converting weight checkpoint keys ==="
python -m executorch.examples.models.qwen3.convert_weights \
    "${MODEL_DIR}" "${CONVERTED_WEIGHTS}"

echo ""
echo "=== Step 2/3: Downloading model config ==="
curl -L -o "${CONFIG_FILE}" "${CONFIG_URL}"

echo ""
echo "=== Step 3/3: Exporting to .pte ==="
python -m executorch.examples.models.llama.export_llama \
    --model "qwen3_0_6b" \
    --checkpoint "${CONVERTED_WEIGHTS}" \
    --params "${CONFIG_FILE}" \
    --output_name "${OUTPUT_NAME}" \
    -kv \
    --use_sdpa_with_kv_cache \
    -X \
    --xnnpack-extended-ops \
    --max_context_length 1024 \
    --max_seq_length 128 \
    --dtype fp32 \
    --metadata '{"get_bos_id":199999, "get_eos_ids":[200020,199999]}'

echo ""
echo "=== Export complete ==="
ls -lh "${OUTPUT_NAME}"
