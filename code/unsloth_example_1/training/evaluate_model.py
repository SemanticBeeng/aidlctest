"""
Qwen3-0.6B QAT Model Evaluation Pipeline
==========================================
Evaluates the QAT-trained model using Confident AI's DeepEval framework.

Covers five evaluation suites:
  1. Math correctness  — does the QAT model still solve math problems?
  2. Reasoning quality  — is the chain-of-thought coherent?
  3. Chat quality       — are general responses relevant, non-toxic, unbiased?
  4. QAT regression     — how does QAT model compare to the base model?
  5. Export parity       — does the .pte export match PyTorch model outputs?

Prerequisites:
  - Trained model saved in phone_model/ (from qwen3_phone_deployment.py)
  - OPENAI_API_KEY env var set (for LLM-as-judge metrics)
  - poetry install (deepeval is a dev dependency)

Usage:
  - As plain Python:  python evaluate_model.py
  - With marimo:       marimo edit evaluate_model.py
  - As pytest:         poetry run deepeval test run tests/test_model_quality.py

Requirements: See pyproject.toml (managed by Poetry)
GPU: Requires CUDA GPU for model inference
"""

# %% [markdown]
# ## 1. Configuration & Imports

# %%
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import torch
from datasets import load_dataset
from deepeval import evaluate
from deepeval.dataset import EvaluationDataset
from deepeval.metrics import (
    AnswerRelevancyMetric,
    BiasMetric,
    GEval,
    ToxicityMetric,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from unsloth import FastLanguageModel
from unsloth.chat_templates import standardize_sharegpt


@dataclass
class EvalConfig:
    """Evaluation configuration with sensible defaults."""

    # Model paths
    base_model_name: str = "unsloth/Qwen3-0.6B"
    qat_model_dir: str = "phone_model"
    max_seq_length: int = 1024

    # Eval dataset sizes (held-out samples)
    n_math_eval: int = 100
    n_chat_eval: int = 50
    n_export_eval: int = 20

    # Metric thresholds
    math_correctness_threshold: float = 0.7
    reasoning_quality_threshold: float = 0.6
    relevancy_threshold: float = 0.7
    toxicity_threshold: float = 0.5
    bias_threshold: float = 0.5
    export_parity_threshold: float = 0.8

    # Generation parameters
    max_new_tokens: int = 512
    temperature: float = 0.6
    top_p: float = 0.95

    # Output
    results_dir: str = "eval_results"
    skip_base_model: bool = False
    skip_export_parity: bool = True  # requires .pte file

    # Datasets to hold out from (same sources as training)
    reasoning_dataset_name: str = "unsloth/OpenMathReasoning-mini"
    reasoning_split: str = "cot"
    chat_dataset_name: str = "mlabonne/FineTome-100k"
    chat_split: str = "train"

    # Reproducibility
    seed: int = 42
    # Indices to skip (used for training) — use tail end for eval
    reasoning_eval_offset: int = -1  # take last n_math_eval samples


config = EvalConfig()


# %% [markdown]
# ## 2. Define DeepEval Metrics

# %%
def build_metrics(cfg: EvalConfig) -> dict:
    """Build all DeepEval metric instances."""

    math_correctness = GEval(
        name="Mathematical Correctness",
        criteria=(
            "Determine if the actual output arrives at the same correct "
            "numerical answer as the expected output. The reasoning steps "
            "may differ in style or order, but the final numerical answer "
            "must match. Award full score if the final answer is correct, "
            "partial score if the approach is correct but the answer has "
            "a minor arithmetic error, and zero if the answer is wrong."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        threshold=cfg.math_correctness_threshold,
    )

    reasoning_quality = GEval(
        name="Reasoning Quality",
        criteria=(
            "Evaluate whether the step-by-step reasoning is logically "
            "coherent, mathematically sound, and progresses toward the "
            "correct solution without hallucinated or nonsensical steps. "
            "Penalize circular reasoning, skipped steps that hide errors, "
            "and assertions made without justification."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        threshold=cfg.reasoning_quality_threshold,
    )

    relevancy = AnswerRelevancyMetric(threshold=cfg.relevancy_threshold)
    toxicity = ToxicityMetric(threshold=cfg.toxicity_threshold)
    bias = BiasMetric(threshold=cfg.bias_threshold)

    export_parity = GEval(
        name="Export Parity",
        criteria=(
            "Compare the PyTorch model output and the exported .pte model "
            "output for the same input. They should convey the same meaning "
            "and arrive at the same conclusion, even if the exact wording "
            "differs slightly due to quantization effects."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        threshold=cfg.export_parity_threshold,
    )

    return {
        "math_correctness": math_correctness,
        "reasoning_quality": reasoning_quality,
        "relevancy": relevancy,
        "toxicity": toxicity,
        "bias": bias,
        "export_parity": export_parity,
    }


# %% [markdown]
# ## 3. Model Loading Utilities

# %%
def load_qat_model(cfg: EvalConfig):
    """Load the QAT-trained model from phone_model/ directory."""
    print(f"Loading QAT model from {cfg.qat_model_dir}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=cfg.qat_model_dir,
        max_seq_length=cfg.max_seq_length,
    )
    FastLanguageModel.for_inference(model)
    return model, tokenizer


def load_base_model(cfg: EvalConfig):
    """Load the original base model (pre-QAT) for regression comparison."""
    print(f"Loading base model {cfg.base_model_name}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=cfg.base_model_name,
        max_seq_length=cfg.max_seq_length,
    )
    FastLanguageModel.for_inference(model)
    return model, tokenizer


def generate_response(model, tokenizer, prompt: str, cfg: EvalConfig) -> str:
    """Generate a single response from a model given a prompt."""
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=cfg.max_new_tokens,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            do_sample=True,
        )

    # Decode only the newly generated tokens
    generated_ids = output_ids[0][inputs["input_ids"].shape[1] :]
    return tokenizer.decode(generated_ids, skip_special_tokens=True)


# %% [markdown]
# ## 4. Evaluation Dataset Preparation

# %%
def prepare_math_eval_data(cfg: EvalConfig) -> list[dict]:
    """Load and prepare held-out math evaluation samples."""
    print(f"Loading reasoning eval data ({cfg.n_math_eval} samples)...")
    ds = load_dataset(cfg.reasoning_dataset_name, split=cfg.reasoning_split)

    # Take from the tail end to avoid overlap with training data
    total = len(ds)
    start_idx = max(0, total - cfg.n_math_eval)
    eval_ds = ds.select(range(start_idx, total))

    samples = []
    for row in eval_ds:
        samples.append(
            {
                "input": row["problem"],
                "expected_output": row["generated_solution"],
                "expected_answer": row.get("expected_answer", ""),
            }
        )
    print(f"  Prepared {len(samples)} math eval samples (indices {start_idx}:{total})")
    return samples


def prepare_chat_eval_data(cfg: EvalConfig, tokenizer) -> list[dict]:
    """Load and prepare held-out chat evaluation samples."""
    print(f"Loading chat eval data ({cfg.n_chat_eval} samples)...")
    ds = load_dataset(cfg.chat_dataset_name, split=cfg.chat_split)

    # Standardize ShareGPT format
    ds = standardize_sharegpt(ds)

    # Take from the tail end to avoid overlap with training data
    total = len(ds)
    start_idx = max(0, total - cfg.n_chat_eval)
    eval_ds = ds.select(range(start_idx, total))

    samples = []
    for row in eval_ds:
        conversations = row["conversations"]
        if len(conversations) >= 2:
            # Use first user message as input, first assistant message as expected
            user_msg = None
            assistant_msg = None
            for turn in conversations:
                if turn["role"] == "user" and user_msg is None:
                    user_msg = turn["content"]
                elif turn["role"] == "assistant" and assistant_msg is None:
                    assistant_msg = turn["content"]
            if user_msg and assistant_msg:
                samples.append(
                    {
                        "input": user_msg,
                        "expected_output": assistant_msg,
                    }
                )

    samples = samples[: cfg.n_chat_eval]  # Limit to requested count
    print(f"  Prepared {len(samples)} chat eval samples")
    return samples


# %% [markdown]
# ## 5. Test Case Generation

# %%
def generate_test_cases(
    model,
    tokenizer,
    samples: list[dict],
    cfg: EvalConfig,
    label: str = "",
) -> list[LLMTestCase]:
    """Generate model outputs and wrap in LLMTestCase objects."""
    test_cases = []
    total = len(samples)
    for i, sample in enumerate(samples):
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  [{label}] Generating {i + 1}/{total}...")

        actual_output = generate_response(model, tokenizer, sample["input"], cfg)

        tc = LLMTestCase(
            input=sample["input"],
            actual_output=actual_output,
            expected_output=sample.get("expected_output"),
        )
        test_cases.append(tc)

    print(f"  [{label}] Generated {len(test_cases)} test cases")
    return test_cases


# %% [markdown]
# ## 6. Evaluation Suites

# %%
def run_math_evaluation(
    model, tokenizer, metrics: dict, cfg: EvalConfig, label: str = "qat"
) -> dict:
    """Suite 1 & 2: Math correctness + reasoning quality."""
    print(f"\n{'='*60}")
    print(f"MATH EVALUATION ({label})")
    print(f"{'='*60}")

    samples = prepare_math_eval_data(cfg)
    test_cases = generate_test_cases(model, tokenizer, samples, cfg, label=f"math-{label}")

    results = evaluate(
        test_cases=test_cases,
        metrics=[metrics["math_correctness"], metrics["reasoning_quality"]],
        print_results=True,
    )

    return {
        "label": label,
        "suite": "math",
        "n_cases": len(test_cases),
        "test_cases": test_cases,
        "results": results,
    }


def run_chat_evaluation(
    model, tokenizer, metrics: dict, cfg: EvalConfig, label: str = "qat"
) -> dict:
    """Suite 3: Chat quality — relevancy, toxicity, bias."""
    print(f"\n{'='*60}")
    print(f"CHAT EVALUATION ({label})")
    print(f"{'='*60}")

    samples = prepare_chat_eval_data(cfg, tokenizer)
    test_cases = generate_test_cases(model, tokenizer, samples, cfg, label=f"chat-{label}")

    results = evaluate(
        test_cases=test_cases,
        metrics=[metrics["relevancy"], metrics["toxicity"], metrics["bias"]],
        print_results=True,
    )

    return {
        "label": label,
        "suite": "chat",
        "n_cases": len(test_cases),
        "test_cases": test_cases,
        "results": results,
    }


def run_regression_evaluation(metrics: dict, cfg: EvalConfig) -> dict:
    """Suite 4: QAT regression — compare base vs QAT model on same inputs."""
    print(f"\n{'='*60}")
    print("QAT REGRESSION EVALUATION (base vs QAT)")
    print(f"{'='*60}")

    # Load both models
    qat_model, qat_tokenizer = load_qat_model(cfg)
    base_model, base_tokenizer = load_base_model(cfg)

    # Use same math samples for both
    samples = prepare_math_eval_data(cfg)

    print("\nGenerating base model outputs...")
    base_cases = generate_test_cases(
        base_model, base_tokenizer, samples, cfg, label="base"
    )

    print("\nGenerating QAT model outputs...")
    qat_cases = generate_test_cases(
        qat_model, qat_tokenizer, samples, cfg, label="qat"
    )

    # Evaluate both
    eval_metrics = [metrics["math_correctness"], metrics["reasoning_quality"]]

    print("\nEvaluating base model...")
    base_results = evaluate(
        test_cases=base_cases, metrics=eval_metrics, print_results=True
    )

    print("\nEvaluating QAT model...")
    qat_results = evaluate(
        test_cases=qat_cases, metrics=eval_metrics, print_results=True
    )

    # Free base model memory
    del base_model
    torch.cuda.empty_cache()

    return {
        "suite": "regression",
        "n_cases": len(samples),
        "base_results": base_results,
        "qat_results": qat_results,
        "base_cases": base_cases,
        "qat_cases": qat_cases,
    }


# %% [markdown]
# ## 7. Results Reporting

# %%
def extract_metric_scores(test_cases: list[LLMTestCase], metric_name: str) -> list:
    """Extract individual scores for a named metric from test cases."""
    scores = []
    for tc in test_cases:
        for metric_data in tc.metrics_data:
            if metric_data.name == metric_name:
                scores.append(metric_data.score)
    return scores


def summarize_results(all_results: list[dict], cfg: EvalConfig) -> dict:
    """Build a summary report from all evaluation results."""
    summary = {
        "config": {
            "base_model": cfg.base_model_name,
            "qat_model_dir": cfg.qat_model_dir,
            "n_math_eval": cfg.n_math_eval,
            "n_chat_eval": cfg.n_chat_eval,
            "max_new_tokens": cfg.max_new_tokens,
            "temperature": cfg.temperature,
        },
        "suites": {},
    }

    for result in all_results:
        suite_name = result.get("suite", "unknown")
        label = result.get("label", "")
        key = f"{suite_name}_{label}" if label else suite_name

        suite_summary = {"n_cases": result["n_cases"]}

        if "results" in result and result["results"] is not None:
            # DeepEval evaluate() returns an EvaluationResult
            eval_result = result["results"]
            suite_summary["pass_rate"] = (
                len([tc for tc in eval_result.test_results if tc.success])
                / max(len(eval_result.test_results), 1)
            )

        summary["suites"][key] = suite_summary

    return summary


def save_results(summary: dict, cfg: EvalConfig):
    """Save evaluation summary to JSON."""
    results_dir = Path(cfg.results_dir)
    results_dir.mkdir(exist_ok=True)

    output_path = results_dir / "eval_summary.json"
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")


# %% [markdown]
# ## 8. Main Evaluation Orchestrator

# %%
def run_all_evaluations(cfg: EvalConfig | None = None) -> dict:
    """Run the complete evaluation pipeline.

    Executes suites in order:
      1. Math correctness + reasoning quality (QAT model)
      2. Chat quality (QAT model)
      3. QAT regression comparison (base vs QAT) — optional
      4. Export parity (.pte vs PyTorch) — optional
    """
    if cfg is None:
        cfg = EvalConfig()

    print("=" * 60)
    print("QWEN3-0.6B QAT MODEL EVALUATION")
    print("=" * 60)
    print(f"QAT model: {cfg.qat_model_dir}")
    print(f"Math eval samples: {cfg.n_math_eval}")
    print(f"Chat eval samples: {cfg.n_chat_eval}")
    print(f"Skip base model: {cfg.skip_base_model}")
    print(f"Skip export parity: {cfg.skip_export_parity}")
    print()

    # Build metrics
    metrics = build_metrics(cfg)

    all_results = []

    # --- Suites 1 & 2: Math + Reasoning (QAT model) ---
    qat_model, qat_tokenizer = load_qat_model(cfg)
    math_results = run_math_evaluation(
        qat_model, qat_tokenizer, metrics, cfg, label="qat"
    )
    all_results.append(math_results)

    # --- Suite 3: Chat quality (QAT model) ---
    chat_results = run_chat_evaluation(
        qat_model, qat_tokenizer, metrics, cfg, label="qat"
    )
    all_results.append(chat_results)

    # Free QAT model before loading base
    del qat_model
    torch.cuda.empty_cache()

    # --- Suite 4: QAT regression (base vs QAT) ---
    if not cfg.skip_base_model:
        regression_results = run_regression_evaluation(metrics, cfg)
        all_results.append(regression_results)
    else:
        print("\nSkipping QAT regression evaluation (skip_base_model=True)")

    # --- Suite 5: Export parity ---
    if not cfg.skip_export_parity:
        print("\nExport parity evaluation not yet implemented.")
        print("Requires .pte inference runtime integration.")
    else:
        print("\nSkipping export parity evaluation (skip_export_parity=True)")

    # Summarize and save
    summary = summarize_results(all_results, cfg)
    save_results(summary, cfg)

    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)

    return summary


# %%
if __name__ == "__main__":
    # Override defaults here or via environment variables
    cfg = EvalConfig(
        qat_model_dir=os.environ.get("QAT_MODEL_DIR", "phone_model"),
        n_math_eval=int(os.environ.get("N_MATH_EVAL", "100")),
        n_chat_eval=int(os.environ.get("N_CHAT_EVAL", "50")),
        skip_base_model=os.environ.get("SKIP_BASE_MODEL", "false").lower() == "true",
        skip_export_parity=os.environ.get("SKIP_EXPORT_PARITY", "true").lower()
        == "true",
    )
    run_all_evaluations(cfg)
