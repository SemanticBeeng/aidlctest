# Qwen3-0.6B QAT Model Evaluation Guide

Complete instructions and explanations for running the DeepEval evaluation pipeline
against the QAT-trained Qwen3-0.6B model.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [File Inventory](#file-inventory)
5. [Evaluation Suites Explained](#evaluation-suites-explained)
6. [Metrics Deep Dive](#metrics-deep-dive)
7. [Data Pipeline](#data-pipeline)
8. [Running Evaluations](#running-evaluations)
9. [Configuration Reference](#configuration-reference)
10. [Interpreting Results](#interpreting-results)
11. [Confident AI Dashboard](#confident-ai-dashboard)
12. [Troubleshooting](#troubleshooting)

---

## Overview

After QAT training (via `qwen3_phone_deployment.py`), we need to verify that the
quantized model has not degraded unacceptably. The evaluation pipeline answers four
questions:

1. **Does the QAT model still solve math problems correctly?** (Math Correctness)
2. **Is the chain-of-thought reasoning still coherent?** (Reasoning Quality)
3. **Are general chat responses relevant, non-toxic, and unbiased?** (Chat Quality)
4. **How much accuracy did QAT lose compared to the base model?** (QAT Regression)
5. **Does the exported .pte file match PyTorch model outputs?** (Export Parity — future)

The pipeline uses **Confident AI's DeepEval** framework. DeepEval uses an
**LLM-as-judge** approach — an external LLM (OpenAI GPT-4 by default) scores each
model output against custom evaluation criteria. This avoids brittle exact-match
comparisons and handles the open-ended nature of reasoning and chat responses.

### Why LLM-as-Judge?

Traditional NLP metrics (BLEU, ROUGE, exact-match) fail for generative models:

- A correct math solution may use different variable names or steps
- A helpful chat reply may phrase things differently from the reference
- Chain-of-thought coherence cannot be captured by n-gram overlap

GEval (G-Evaluation) sends the model output plus custom evaluation criteria to
GPT-4 and asks it to score on a 0–1 scale. This correlates far better with human
judgment for open-ended generation tasks.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Evaluation Pipeline                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  training/evaluate_model.py   (standalone orchestrator)      │
│    ├── EvalConfig             (all thresholds & paths)       │
│    ├── build_metrics()        (6 DeepEval metrics)           │
│    ├── load_qat_model()       (Unsloth FastLanguageModel)    │
│    ├── load_base_model()      (for regression comparison)    │
│    ├── prepare_*_data()       (held-out dataset slices)      │
│    ├── generate_test_cases()  (model inference → LLMTestCase)│
│    ├── run_math_evaluation()  (suite 1+2)                    │
│    ├── run_chat_evaluation()  (suite 3)                      │
│    ├── run_regression_eval()  (suite 4)                      │
│    └── run_all_evaluations()  (main entry point)             │
│                                                              │
│  tests/conftest.py            (pytest fixtures)              │
│    ├── eval_config             (session scope)               │
│    ├── metrics                 (session scope)               │
│    ├── qat_model_and_tokenizer (session scope, GPU)          │
│    ├── math_eval_samples       (session scope)               │
│    ├── chat_eval_samples       (session scope)               │
│    ├── math_test_cases         (session scope, generated)    │
│    └── chat_test_cases         (session scope, generated)    │
│                                                              │
│  tests/test_model_quality.py  (pytest + deepeval assertions) │
│    ├── TestMathCorrectness     (20 parametrized cases)       │
│    ├── TestReasoningQuality    (20 parametrized cases)       │
│    ├── TestChatRelevancy       (10 parametrized cases)       │
│    ├── TestChatToxicity        (10 parametrized cases)       │
│    └── TestChatBias            (10 parametrized cases)       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
   ┌──────────────┐            ┌────────────────┐
   │  QAT Model   │            │  OpenAI API    │
   │ phone_model/ │            │  (LLM-judge)   │
   └──────────────┘            └────────────────┘
          │                              │
          ▼                              ▼
   ┌──────────────┐            ┌────────────────┐
   │  eval_results/│           │ Confident AI   │
   │  *.json       │           │ Dashboard      │
   └──────────────┘            └────────────────┘
```

---

## Prerequisites

### 1. Trained Model

You must have a trained model saved in `phone_model/` (produced by
`qwen3_phone_deployment.py`). If you haven't trained yet:

```bash
poetry run python training/qwen3_phone_deployment.py
```

### 2. OpenAI API Key

DeepEval's LLM-as-judge metrics require an external LLM to score outputs.
By default this is OpenAI's GPT-4:

```bash
export OPENAI_API_KEY="sk-..."
```

**Cost note**: Each evaluated test case makes 1–3 API calls to GPT-4.
With default settings (100 math + 50 chat cases × multiple metrics),
expect ~$2–5 per full evaluation run.

### 3. Python Dependencies

```bash
poetry install
```

This installs `deepeval` and `pytest` from the dev dependency group in
`pyproject.toml`.

### 4. Hardware

- **GPU**: CUDA GPU required for model inference (loading Qwen3-0.6B)
- **VRAM**: ~3–4 GB for single model, ~6–8 GB for regression (two models loaded)
- **Internet**: Required for HuggingFace dataset downloads and OpenAI API

### 5. (Optional) Confident AI Account

For dashboard visualization and historical tracking:

```bash
deepeval login
```

This writes a `~/.deepeval` config file with your API key.

---

## File Inventory

| File | Purpose |
|------|---------|
| `training/evaluate_model.py` | Standalone evaluation orchestrator — can run directly as Python or interactively with marimo |
| `tests/conftest.py` | Session-scoped pytest fixtures — loads model and data once, shares across all tests |
| `tests/test_model_quality.py` | Parametrized pytest test classes — each test case gets pass/fail via `deepeval.assert_test()` |
| `tests/__init__.py` | Package marker for test discovery |
| `pyproject.toml` | Dependency manifest — `deepeval` and `pytest` in dev group |
| `training/EVALUATIONS.md` | This document |

---

## Evaluation Suites Explained

### Suite 1: Mathematical Correctness

**What it tests**: Whether the QAT model arrives at the correct final numerical
answer for math problems.

**Why it matters**: QAT introduces quantization noise. If the fake-quantized weights
have degraded enough, the model may start producing wrong arithmetic even though it
learned correct reasoning during training.

**How it works**:
1. Load held-out problems from `unsloth/OpenMathReasoning-mini` (COT split)
2. Feed each problem to the QAT model
3. Send (input, model_output, reference_solution) to GPT-4 as judge
4. GPT-4 scores whether the final numerical answer matches (0–1 scale)

**GEval criteria** (sent verbatim to GPT-4):
> "Determine if the actual output arrives at the same correct numerical answer
> as the expected output. The reasoning steps may differ in style or order, but
> the final numerical answer must match. Award full score if the final answer is
> correct, partial score if the approach is correct but the answer has a minor
> arithmetic error, and zero if the answer is wrong."

**Default threshold**: 0.7 (70% of cases must pass)

### Suite 2: Reasoning Quality

**What it tests**: Whether the chain-of-thought steps are logically coherent,
even if the model uses a different reasoning path than the reference.

**Why it matters**: A model could arrive at the right answer by luck or by
memorizing answers. This metric checks that the *reasoning process itself* is sound.

**How it works**:
1. Uses the same math test cases as Suite 1 (no extra inference needed)
2. Send (input, model_output) to GPT-4 — note: no expected output needed
3. GPT-4 evaluates logical coherence of the step-by-step process

**GEval criteria**:
> "Evaluate whether the step-by-step reasoning is logically coherent,
> mathematically sound, and progresses toward the correct solution without
> hallucinated or nonsensical steps. Penalize circular reasoning, skipped steps
> that hide errors, and assertions made without justification."

**Default threshold**: 0.6 (60% of cases must pass)

### Suite 3: Chat Quality

**What it tests**: General conversational ability across three dimensions:
relevancy, toxicity, and bias.

**Why it matters**: The model is fine-tuned on 25% general chat data (FineTome-100k).
We need to verify it still produces helpful, safe responses after QAT.

**Sub-metrics**:

| Metric | What it checks | Type | Threshold |
|--------|---------------|------|-----------|
| Answer Relevancy | Is the response actually addressing the question? | Built-in DeepEval | 0.7 |
| Toxicity | Does the response contain harmful, offensive, or toxic content? | Built-in DeepEval | 0.5 |
| Bias | Does the response show demographic, gender, racial, or other bias? | Built-in DeepEval | 0.5 |

**How it works**:
1. Load held-out conversations from `mlabonne/FineTome-100k` (ShareGPT format)
2. Extract the user message as input, assistant message as expected output
3. Feed user message to QAT model, collect response
4. Run all three metrics against each test case

**Default sample size**: 50 chat eval cases

### Suite 4: QAT Regression

**What it tests**: Direct comparison of the QAT model vs. the original base
Qwen3-0.6B on the same math problems.

**Why it matters**: This is the key question — "how much accuracy did QAT lose?"
Unsloth claims QAT recovers ~70% of accuracy lost by naïve PTQ. This suite
measures your actual degradation.

**How it works**:
1. Load both the base model (`unsloth/Qwen3-0.6B`) and the QAT model (`phone_model/`)
2. Generate responses from both models on the same held-out math problems
3. Evaluate both sets with Math Correctness and Reasoning Quality metrics
4. Compare pass rates side-by-side

**Important**:
- Requires ~6–8 GB VRAM (both models loaded, then base is freed)
- Doubles inference time (generating from two models)
- Disabled by default (`skip_base_model=True` in config); enable explicitly

### Suite 5: Export Parity (Future)

**What it will test**: Whether the exported `.pte` (ExecuTorch) model produces
outputs semantically equivalent to the PyTorch model.

**Current status**: Placeholder — requires integration with an ExecuTorch inference
runtime to load and run the `.pte` file for comparison. Disabled by default
(`skip_export_parity=True`).

---

## Metrics Deep Dive

### GEval (G-Evaluation)

GEval is DeepEval's primary custom metric type. It works by:

1. You define **evaluation criteria** as a natural language string
2. You specify which **test case parameters** the judge should consider
   (input, actual_output, expected_output)
3. DeepEval sends a structured prompt to GPT-4 with the criteria and test case data
4. GPT-4 returns a score from 0 to 1
5. If the score ≥ threshold, the test case passes

**Configurable parameters** (in `build_metrics()` in `evaluate_model.py`):
- `name`: Human-readable label for reports
- `criteria`: The evaluation rubric sent to GPT-4
- `evaluation_params`: Which `LLMTestCaseParams` to include
- `threshold`: Minimum passing score (0–1)

### Built-in Metrics

DeepEval provides several pre-built metrics that are already calibrated:

| Metric | Score meaning | Threshold interpretation |
|--------|--------------|------------------------|
| `AnswerRelevancyMetric` | 1.0 = perfectly relevant, 0.0 = completely irrelevant | Higher = stricter |
| `ToxicityMetric` | 1.0 = completely non-toxic, 0.0 = highly toxic | Higher = stricter |
| `BiasMetric` | 1.0 = completely unbiased, 0.0 = strongly biased | Higher = stricter |

### LLMTestCase

The fundamental data unit. Each test case contains:

```python
LLMTestCase(
    input="What is 2 + 2?",              # The prompt sent to the model
    actual_output="2 + 2 = 4",            # The model's generated response
    expected_output="The answer is 4.",   # Reference answer (optional for some metrics)
)
```

---

## Data Pipeline

### Held-Out Strategy

Training and evaluation use the **same source datasets** but **different slices**:

```
OpenMathReasoning-mini (COT split)
├── Training: first N-100 examples   (used by qwen3_phone_deployment.py)
└── Evaluation: last 100 examples    (used by evaluate_model.py)

FineTome-100k
├── Training: first N-50 examples    (used by qwen3_phone_deployment.py)
└── Evaluation: last 50 examples     (used by evaluate_model.py)
```

The evaluation code always takes from the **tail end** of the dataset (`total - n_eval`
to `total`). Training uses the default iterator which starts from the beginning. This
ensures no overlap.

### Math Data Preparation

```
unsloth/OpenMathReasoning-mini (COT split)
  → ds.select(range(total-100, total))       # last 100 rows
  → extract: problem → input
              generated_solution → expected_output
              expected_answer → expected_answer (metadata)
  → list[dict] with keys: input, expected_output, expected_answer
```

### Chat Data Preparation

```
mlabonne/FineTome-100k
  → standardize_sharegpt(ds)                 # normalize role names
  → ds.select(range(total-50, total))        # last 50 rows
  → for each row:
      extract first user turn → input
      extract first assistant turn → expected_output
  → list[dict] with keys: input, expected_output
```

---

## Running Evaluations

### Method 1: Standalone Python Script

The simplest way. Runs all suites sequentially, saves results to `eval_results/`.

```bash
# Basic run (math + chat, skip regression and export parity)
export OPENAI_API_KEY="sk-..."
poetry run python training/evaluate_model.py
```

#### Environment Variable Overrides

| Variable | Default | Description |
|----------|---------|-------------|
| `QAT_MODEL_DIR` | `phone_model` | Path to the QAT-trained model directory |
| `N_MATH_EVAL` | `100` | Number of math evaluation samples |
| `N_CHAT_EVAL` | `50` | Number of chat evaluation samples |
| `SKIP_BASE_MODEL` | `false` | Set `true` to skip regression comparison |
| `SKIP_EXPORT_PARITY` | `true` | Set `false` when .pte inference is available |

```bash
# Full run with regression
SKIP_BASE_MODEL=false poetry run python training/evaluate_model.py

# Quick smoke test (fewer samples)
N_MATH_EVAL=10 N_CHAT_EVAL=5 poetry run python training/evaluate_model.py
```

### Method 2: Interactive with marimo

Run cells interactively, inspect intermediate results, modify configuration on the fly.

```bash
poetry run marimo edit training/evaluate_model.py
```

The file uses `# %%` cell markers (8 sections), so each section can be run
independently. Modify `EvalConfig()` in Section 1 before running Section 8.

### Method 3: pytest with DeepEval

Best for CI/CD integration. Each test case becomes a separate pass/fail result.

```bash
# Run all evaluation tests
export OPENAI_API_KEY="sk-..."
poetry run deepeval test run tests/test_model_quality.py

# Or with standard pytest (less DeepEval-specific output)
poetry run pytest tests/test_model_quality.py -v
```

#### How pytest Tests Work

1. **conftest.py** fixtures (session-scoped) run first:
   - Load the QAT model once → `qat_model_and_tokenizer`
   - Download evaluation datasets → `math_eval_samples`, `chat_eval_samples`
   - Generate model outputs for all samples → `math_test_cases`, `chat_test_cases`
   
2. **test_model_quality.py** parametrized tests run:
   - Each test class parametrizes over sample indices
   - Each test calls `deepeval.assert_test(test_case, [metric])`
   - If the metric score ≥ threshold → PASS; otherwise → FAIL

3. **Test counts** (with default conftest config):
   - 20 math correctness tests
   - 20 reasoning quality tests
   - 10 chat relevancy tests
   - 10 chat toxicity tests
   - 10 chat bias tests
   - **Total: 70 individual test cases**

#### Running Specific Suites

```bash
# Only math tests
poetry run pytest tests/test_model_quality.py::TestMathCorrectness -v

# Only reasoning tests
poetry run pytest tests/test_model_quality.py::TestReasoningQuality -v

# Only chat quality tests (all three sub-metrics)
poetry run pytest tests/test_model_quality.py::TestChatRelevancy \
                  tests/test_model_quality.py::TestChatToxicity \
                  tests/test_model_quality.py::TestChatBias -v

# A single test case
poetry run pytest "tests/test_model_quality.py::TestMathCorrectness::test_math_correctness[0]" -v
```

### Method 4: Python API (Programmatic)

Import the evaluation functions directly for custom workflows:

```python
from training.evaluate_model import EvalConfig, build_metrics, run_all_evaluations

# Custom configuration
cfg = EvalConfig(
    n_math_eval=50,
    n_chat_eval=25,
    math_correctness_threshold=0.8,  # Stricter
    skip_base_model=False,           # Enable regression
)

summary = run_all_evaluations(cfg)
print(summary["suites"])
```

---

## Configuration Reference

All evaluation behavior is controlled by the `EvalConfig` dataclass in
`training/evaluate_model.py`:

### Model Paths

| Field | Default | Description |
|-------|---------|-------------|
| `base_model_name` | `unsloth/Qwen3-0.6B` | HuggingFace model ID for base comparison |
| `qat_model_dir` | `phone_model` | Local directory with TorchAO QAT checkpoint |
| `max_seq_length` | `1024` | Maximum sequence length for model loading |

### Dataset Sizes

| Field | Default | Description |
|-------|---------|-------------|
| `n_math_eval` | `100` | Number of held-out math problems to evaluate |
| `n_chat_eval` | `50` | Number of held-out chat conversations to evaluate |
| `n_export_eval` | `20` | Number of samples for export parity (future) |

### Metric Thresholds

| Field | Default | Meaning |
|-------|---------|---------|
| `math_correctness_threshold` | `0.7` | 70% of math answers must be correct |
| `reasoning_quality_threshold` | `0.6` | 60% of reasoning chains must be coherent |
| `relevancy_threshold` | `0.7` | 70% of chat responses must be relevant |
| `toxicity_threshold` | `0.5` | 50% toxicity-free bar (inverted: scores above = safe) |
| `bias_threshold` | `0.5` | 50% bias-free bar |
| `export_parity_threshold` | `0.8` | 80% semantic match between PyTorch and .pte |

### Generation Parameters

| Field | Default | Description |
|-------|---------|-------------|
| `max_new_tokens` | `512` | Maximum tokens to generate per response |
| `temperature` | `0.6` | Sampling temperature (lower = more deterministic) |
| `top_p` | `0.95` | Nucleus sampling threshold |

### Feature Flags

| Field | Default | Description |
|-------|---------|-------------|
| `skip_base_model` | `False` | Skip regression comparison (saves time + VRAM) |
| `skip_export_parity` | `True` | Skip .pte parity check (not yet implemented) |

### Dataset Sources

| Field | Default | Description |
|-------|---------|-------------|
| `reasoning_dataset_name` | `unsloth/OpenMathReasoning-mini` | HuggingFace dataset for math eval |
| `reasoning_split` | `cot` | Dataset split (chain-of-thought) |
| `chat_dataset_name` | `mlabonne/FineTome-100k` | HuggingFace dataset for chat eval |
| `chat_split` | `train` | Dataset split |

### Pytest Fixture Configuration

The `conftest.py` fixtures use **reduced defaults** for faster test runs:

| Parameter | Standalone default | pytest default | Reason |
|-----------|--------------------|----------------|--------|
| `n_math_eval` | 100 | 20 | Faster CI runs |
| `n_chat_eval` | 50 | 10 | Faster CI runs |
| `max_new_tokens` | 512 | 256 | Shorter outputs for speed |

To change pytest defaults, edit the `eval_config` fixture in `tests/conftest.py`.

---

## Interpreting Results

### Standalone Script Output

The script prints results to stdout and saves a JSON summary:

```
============================================================
MATH EVALUATION (qat)
============================================================
  [math-qat] Generating 1/100...
  [math-qat] Generating 10/100...
  ...
  [math-qat] Generated 100 test cases

  DeepEval Evaluation Results:
   ✓ 73/100 passed Mathematical Correctness (threshold: 0.7)
   ✓ 65/100 passed Reasoning Quality (threshold: 0.6)
```

### JSON Output

Saved to `eval_results/eval_summary.json`:

```json
{
  "config": {
    "base_model": "unsloth/Qwen3-0.6B",
    "qat_model_dir": "phone_model",
    "n_math_eval": 100,
    "n_chat_eval": 50,
    "max_new_tokens": 512,
    "temperature": 0.6
  },
  "suites": {
    "math_qat": {
      "n_cases": 100,
      "pass_rate": 0.73
    },
    "chat_qat": {
      "n_cases": 50,
      "pass_rate": 0.82
    }
  }
}
```

### What Good Results Look Like

| Metric | Acceptable | Good | Excellent |
|--------|-----------|------|-----------|
| Math Correctness | 60–70% | 70–80% | >80% |
| Reasoning Quality | 50–60% | 60–75% | >75% |
| Answer Relevancy | 60–70% | 70–85% | >85% |
| Toxicity (safe) | >40% | >60% | >80% |
| Bias (unbiased) | >40% | >60% | >80% |
| Regression (QAT/base ratio) | >0.6 | >0.7 | >0.85 |

### Red Flags

- **Math correctness < 50%**: QAT severely damaged arithmetic ability
- **Reasoning quality < 40%**: Model is generating incoherent chain-of-thought
- **Toxicity < 30%**: Model may be generating harmful content
- **Regression ratio < 0.5**: QAT lost more than 50% of base model capability

---

## Confident AI Dashboard

DeepEval integrates with [Confident AI](https://confident-ai.com) for visualization
and historical tracking.

### Setup

```bash
# One-time login
deepeval login

# Run tests — results auto-upload to dashboard
poetry run deepeval test run tests/test_model_quality.py
```

### Dashboard Features

- **Test run history**: Track metric scores across training iterations
- **Per-test-case drill-down**: See input, output, expected output, and judge reasoning
- **Metric trends**: Visualize how math correctness, reasoning, etc. change over time
- **Regression alerts**: Set thresholds and get notified when scores drop
- **Team sharing**: Share evaluation results with collaborators

### Using `deepeval test run` vs `pytest`

| Feature | `deepeval test run` | `pytest` |
|---------|--------------------|---------| 
| Dashboard upload | Automatic | Manual via `deepeval login` |
| Output format | DeepEval-styled | Standard pytest |
| CI/CD integration | Good | Better (standard tooling) |
| Verbose per-case results | Built-in | Via `-v` flag |

---

## Troubleshooting

### Common Issues

**`OPENAI_API_KEY not set`**
```bash
export OPENAI_API_KEY="sk-..."
```
DeepEval's LLM-as-judge metrics require an OpenAI API key. Without it,
all GEval, Relevancy, Toxicity, and Bias metrics will fail.

**`phone_model/ not found`**
Run training first:
```bash
poetry run python training/qwen3_phone_deployment.py
```
Or point to a different directory:
```bash
QAT_MODEL_DIR=/path/to/model poetry run python training/evaluate_model.py
```

**`CUDA out of memory`**
- Reduce `max_seq_length` (default 1024 → try 512)
- Reduce `max_new_tokens` (default 512 → try 256)
- For regression: ensure only one model is loaded at a time (the code does this)
- Close other GPU-consuming processes

**`ModuleNotFoundError: No module named 'deepeval'`**
```bash
poetry install  # installs dev dependencies including deepeval
```

**`ModuleNotFoundError: No module named 'training'`**
When running pytest, Python needs to find the `training` package. Either:
```bash
# Option 1: Run from project root
cd /path/to/aidlctest
poetry run pytest tests/test_model_quality.py -v

# Option 2: Install in editable mode
pip install -e .
```

**Rate limiting from OpenAI API**
With 100+ test cases, you may hit API rate limits. Solutions:
- Reduce sample count: `N_MATH_EVAL=20 N_CHAT_EVAL=10`
- Add delay between calls (modify `generate_test_cases()`)
- Use a higher-tier API key

**Tests pass but scores seem low**
- Check that the model was trained for enough steps (`max_steps=100` is a demo)
- Verify the QAT model loads correctly (check for warnings during model loading)
- Try lowering thresholds initially to establish a baseline
- Compare with regression suite to see if base model also scores low

### Expected Timelines

| Operation | Duration (approx) |
|-----------|-------------------|
| Model loading (QAT) | 30–60 seconds |
| Math inference (100 samples) | 10–20 minutes (GPU-dependent) |
| Chat inference (50 samples) | 5–10 minutes |
| LLM-judge scoring (150 cases) | 5–15 minutes (API-dependent) |
| **Total (default config)** | **20–45 minutes** |
| Quick smoke test (10+5 samples) | 5–10 minutes |
| Regression (doubles inference) | 40–90 minutes |
