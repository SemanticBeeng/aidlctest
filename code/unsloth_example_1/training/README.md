# Qwen3-0.6B QAT Phone Deployment Training Pipeline

Extracted from the [Unsloth Qwen3 Phone Deployment Colab notebook](https://colab.research.google.com/github/unslothai/notebooks/blob/main/nb/Qwen3_(0_6B)-Phone_Deployment.ipynb).

## Overview

This pipeline trains Qwen3-0.6B using **Quantization-Aware Training (QAT)** with Unsloth's `phone-deployment` scheme, then exports the model to ExecuTorch `.pte` format for on-device inference.

### QAT Scheme
- **INT8 dynamic activations + INT4 weights** (via fake-quant during training)
- Full fine-tuning (all 751M parameters, not LoRA)
- Recovers ~70% of accuracy lost by naïve post-training quantization

### Training Data
- **75% reasoning**: [OpenMathReasoning-mini](https://huggingface.co/datasets/unsloth/OpenMathReasoning-mini) COT traces (~19K examples)
- **25% general chat**: [FineTome-100k](https://huggingface.co/datasets/mlabonne/FineTome-100k) in ShareGPT format

## Files

| File | Description |
|------|-------------|
| `../pyproject.toml` | uv dependency manifest |
| `qwen3_phone_deployment.py` | Complete training pipeline (marimo / VS Code cell compatible) |
| `export_executorch.sh` | Standalone shell script for ExecuTorch export |

## Quick Start

### 1. Install dependencies
```bash
uv sync --locked
```

### 2. Run training
```bash
# As a script
uv run python training/qwen3_phone_deployment.py

# Or interactively with marimo
uv run marimo edit training/qwen3_phone_deployment.py
```

### 3. Export to .pte (if not done in step 2)
```bash
cd training
uv run bash export_executorch.sh
```

## Hardware Requirements

- **GPU**: CUDA GPU required (tested on Tesla T4)
- **VRAM**: ~10.5 GB peak reserved memory
- **Training time**: ~11.5 minutes for 100 steps on T4

## Output

After training and export:
- `phone_model/` — TorchAO checkpoint directory
- `qwen3_0.6B_model.pte` — ExecuTorch model file (~472 MB)

## Pipeline Stages

The Python script is organized into numbered sections with `# %%` cell markers:

1. **Environment Setup** — Install/verify dependencies
2. **Load Model with QAT** — `FastLanguageModel.from_pretrained()` with `qat_scheme="phone-deployment"`
3. **Prepare Training Data** — Load, format, and mix reasoning + chat datasets
4. **Train** — `SFTTrainer` with `SFTConfig` (100 steps demo, or full epoch)
5. **Training Stats** — GPU memory and time reporting
6. **Save Model** — `save_pretrained_torchao()` to TorchAO format
7. **Export to ExecuTorch** — Convert weights → download config → export `.pte`

## Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| `max_seq_length` | 1024 | Training context window |
| `batch_size` | 2 | Per device |
| `gradient_accumulation` | 4 | Effective batch = 8 |
| `learning_rate` | 5e-5 | |
| `weight_decay` | 0.001 | |
| `lr_scheduler` | linear | |
| `max_steps` | 100 | Demo; set `num_train_epochs=1` for full run |
| `optimizer` | adamw_8bit | Memory-efficient |
