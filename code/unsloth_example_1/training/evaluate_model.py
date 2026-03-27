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
  - uv sync --locked (deepeval is a dev dependency)

Usage:
  - As plain Python:  python evaluate_model.py
  - With marimo:       marimo edit evaluate_model.py
  - As pytest:         uv run deepeval test run tests/test_model_quality.py

Requirements: See pyproject.toml (managed by uv)
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


def _configure_llm_judge_env(cfg: "EvalConfig") -> None:
    """Best-effort configuration for DeepEval LLM-as-judge.

    DeepEval uses OpenAI-compatible providers for LLM-as-judge metrics.
    Different DeepEval/OpenAI client versions look for slightly different
    environment variable names.

    We set defaults only (do not override user-supplied values).
    """

    if getattr(cfg, "judge_base_url", None):
        # Common conventions across OpenAI-compatible clients
        os.environ.setdefault("OPENAI_BASE_URL", cfg.judge_base_url)
        os.environ.setdefault("OPENAI_API_BASE", cfg.judge_base_url)

    if getattr(cfg, "judge_api_key", None):
        os.environ.setdefault("OPENAI_API_KEY", cfg.judge_api_key)

    if getattr(cfg, "judge_model", None):
        os.environ.setdefault("OPENAI_MODEL", cfg.judge_model)
        os.environ.setdefault("DEEPEVAL_JUDGE_MODEL", cfg.judge_model)


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
    n_multiturn_eval: int = 20
    n_export_eval: int = 20

    # Metric thresholds
    math_correctness_threshold: float = 0.7
    reasoning_quality_threshold: float = 0.6
    cot_format_threshold: float = 0.7
    final_answer_threshold: float = 0.7
    instruction_following_threshold: float = 0.7
    response_completeness_threshold: float = 0.6
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

    # LLM-as-judge configuration (OpenAI-compatible endpoint)
    # Intended MVP: Llama 3 served via vLLM on RunPod.
    judge_base_url: str = os.environ.get(
        "DEEPEVAL_JUDGE_BASE_URL", "http://judgepodforedgeai:8000/v1"
    )
    judge_api_key: str = os.environ.get("DEEPEVAL_JUDGE_API_KEY", os.environ.get("OPENAI_API_KEY", "local-vllm"))
    judge_model: str = os.environ.get("DEEPEVAL_JUDGE_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")

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

    _configure_llm_judge_env(cfg)

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

    # --- Dataset-specific metrics for OpenMathReasoning-mini ---

    cot_format_compliance = GEval(
        name="COT Format Compliance",
        criteria=(
            "Evaluate whether the model output follows a proper chain-of-thought "
            "reasoning format as found in the OpenMathReasoning dataset. "
            "The output should: (1) break the solution into discrete numbered "
            "or clearly separated steps, (2) show intermediate calculations "
            "rather than jumping to an answer, (3) use mathematical notation "
            "appropriately, and (4) clearly state the final answer at the end, "
            "ideally with a summary statement like 'The answer is ...' or "
            "boxed notation. Deduct points for stream-of-consciousness text "
            "without structure, missing intermediate steps, or no clear final "
            "answer demarcation."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        threshold=cfg.cot_format_threshold,
    )

    final_answer_extraction = GEval(
        name="Final Answer Extraction",
        criteria=(
            "Determine whether the model output contains a clearly extractable "
            "final answer to the math problem. The final answer should appear "
            "at or near the end of the response and be unambiguous — for example "
            "boxed (\\boxed{...}), preceded by 'The answer is', 'Therefore', "
            "'Thus', or 'Final answer:', or otherwise clearly separated from "
            "working steps. Award full score if the final answer is trivially "
            "extractable by a simple parser; partial score if interspersed "
            "with other text but still identifiable; zero if the response "
            "trails off without stating a conclusion."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        threshold=cfg.final_answer_threshold,
    )

    # --- Dataset-specific metrics for FineTome-100k ---

    instruction_following = GEval(
        name="Instruction Following",
        criteria=(
            "Evaluate how faithfully the model follows the user's instruction. "
            "Consider: (1) does the response address ALL parts of the "
            "instruction, including sub-questions or constraints? (2) does it "
            "respect format requests (e.g. 'list', 'explain', 'compare')? "
            "(3) does it stay within the scope of the instruction without "
            "going off-topic? (4) does it follow any explicit constraints "
            "(length, style, perspective)? Full score for complete compliance; "
            "partial for addressing most but not all parts; zero for ignoring "
            "the instruction entirely or producing an unrelated response."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        threshold=cfg.instruction_following_threshold,
    )

    response_completeness = GEval(
        name="Response Completeness",
        criteria=(
            "Assess whether the model's response is complete and not truncated. "
            "A complete response: (1) answers the question fully without "
            "trailing off mid-sentence, (2) covers all major points that a "
            "knowledgeable assistant would include, (3) does not end abruptly "
            "or with incomplete code/lists/explanations, and (4) provides "
            "sufficient depth for the complexity of the question. Compare "
            "the completeness against the expected output as a reference for "
            "the appropriate level of detail. Deduct heavily for truncated "
            "or obviously incomplete responses."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        threshold=cfg.response_completeness_threshold,
    )

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
        "cot_format_compliance": cot_format_compliance,
        "final_answer_extraction": final_answer_extraction,
        "instruction_following": instruction_following,
        "response_completeness": response_completeness,
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


def prepare_multiturn_eval_data(cfg: EvalConfig, tokenizer) -> list[dict]:
    """Load held-out multi-turn conversations from FineTome-100k.

    Unlike prepare_chat_eval_data which extracts only the first turn,
    this preserves the full conversation for multi-turn coherence testing.
    The model is given all turns up to the last assistant turn, and must
    generate the final assistant response.
    """
    print(f"Loading multi-turn eval data ({cfg.n_multiturn_eval} samples)...")
    ds = load_dataset(cfg.chat_dataset_name, split=cfg.chat_split)
    ds = standardize_sharegpt(ds)

    total = len(ds)
    # Use a different offset from single-turn to avoid overlap
    start_idx = max(0, total - cfg.n_chat_eval - cfg.n_multiturn_eval)
    end_idx = max(0, total - cfg.n_chat_eval)
    eval_ds = ds.select(range(start_idx, end_idx))

    samples = []
    for row in eval_ds:
        conversations = row["conversations"]
        # Only use conversations with 4+ turns (at least 2 user + 2 assistant)
        user_turns = [t for t in conversations if t["role"] == "user"]
        asst_turns = [t for t in conversations if t["role"] == "assistant"]
        if len(user_turns) >= 2 and len(asst_turns) >= 2:
            # Build context: all turns except the last assistant turn
            # The model must generate the final assistant response
            last_asst_idx = None
            for i in range(len(conversations) - 1, -1, -1):
                if conversations[i]["role"] == "assistant":
                    last_asst_idx = i
                    break
            if last_asst_idx is None:
                continue

            context_turns = conversations[:last_asst_idx]
            expected_response = conversations[last_asst_idx]["content"]

            # Format the context as a multi-turn prompt
            context_text = tokenizer.apply_chat_template(
                context_turns, tokenize=False, add_generation_prompt=True
            )
            samples.append(
                {
                    "input": context_text,
                    "expected_output": expected_response,
                    "n_turns": len(context_turns),
                    "raw_input": context_turns[-1]["content"] if context_turns else "",
                }
            )

    samples = samples[: cfg.n_multiturn_eval]
    print(f"  Prepared {len(samples)} multi-turn eval samples")
    return samples


# %% [markdown]
# ## 4b. Programmatic Dataset-Specific Checks

# %%
import re as _re


def check_think_token_usage(actual_output: str) -> dict:
    """Check whether the model uses <think> tokens properly.

    Qwen3 uses <think>...</think> for internal reasoning. This checks:
    - Whether think tokens appear at all
    - Whether they are properly opened and closed
    - Whether content exists outside think tokens (the actual answer)
    """
    has_open = "<think>" in actual_output
    has_close = "</think>" in actual_output
    open_count = actual_output.count("<think>")
    close_count = actual_output.count("</think>")
    balanced = open_count == close_count

    # Extract content outside think blocks
    outside_think = _re.sub(r"<think>.*?</think>", "", actual_output, flags=_re.DOTALL)
    has_answer_outside = len(outside_think.strip()) > 0

    return {
        "has_think_tokens": has_open and has_close,
        "balanced": balanced,
        "open_count": open_count,
        "close_count": close_count,
        "has_answer_outside_think": has_answer_outside,
        "answer_text": outside_think.strip(),
    }


def check_final_answer_extractable(actual_output: str) -> dict:
    """Programmatically check if a final answer can be extracted.

    Looks for common patterns: \\boxed{...}, 'The answer is', 'Therefore',
    'Thus', 'Final answer:', or a number/expression at the end.
    """
    # Strip think tokens first
    clean = _re.sub(r"<think>.*?</think>", "", actual_output, flags=_re.DOTALL).strip()

    patterns = {
        "boxed": bool(_re.search(r"\\boxed\{[^}]+\}", clean)),
        "the_answer_is": bool(
            _re.search(r"[Tt]he\s+(final\s+)?answer\s+is", clean)
        ),
        "therefore": bool(_re.search(r"\b[Tt]herefore\b", clean)),
        "thus": bool(_re.search(r"\b[Tt]hus\b", clean)),
        "final_answer_label": bool(
            _re.search(r"[Ff]inal\s+[Aa]nswer\s*:", clean)
        ),
        "trailing_number": bool(
            _re.search(r"(?:=\s*|is\s+)(-?\d+[\d.,/]*)\s*\.?\s*$", clean)
        ),
    }

    extractable = any(patterns.values())
    matched_patterns = [k for k, v in patterns.items() if v]

    # Try to extract the actual answer value
    extracted_answer = None
    if patterns["boxed"]:
        m = _re.search(r"\\boxed\{([^}]+)\}", clean)
        if m:
            extracted_answer = m.group(1)
    elif patterns["the_answer_is"]:
        m = _re.search(
            r"[Tt]he\s+(?:final\s+)?answer\s+is\s+(.+?)[\.\n]", clean
        )
        if m:
            extracted_answer = m.group(1).strip()

    return {
        "extractable": extractable,
        "matched_patterns": matched_patterns,
        "extracted_answer": extracted_answer,
        "clean_output": clean,
    }


def check_expected_answer_match(
    actual_output: str, expected_answer: str
) -> dict:
    """Check if the model's extracted answer matches the expected answer.

    Uses normalization to handle formatting differences (whitespace,
    commas in numbers, trailing periods, etc.).
    """
    if not expected_answer:
        return {"matchable": False, "reason": "no expected_answer available"}

    extraction = check_final_answer_extractable(actual_output)
    if not extraction["extracted_answer"]:
        return {
            "matchable": True,
            "match": False,
            "reason": "could not extract answer from output",
            "expected": expected_answer,
        }

    def normalize(s: str) -> str:
        s = s.strip().lower()
        s = s.replace(",", "")  # Remove thousands separators
        s = s.rstrip(".")  # Remove trailing periods
        s = _re.sub(r"\s+", " ", s)  # Normalize whitespace
        # Remove $ signs and other common math wrappers
        s = s.strip("$").strip()
        return s

    norm_actual = normalize(extraction["extracted_answer"])
    norm_expected = normalize(expected_answer)

    return {
        "matchable": True,
        "match": norm_actual == norm_expected,
        "actual_extracted": extraction["extracted_answer"],
        "expected": expected_answer,
        "norm_actual": norm_actual,
        "norm_expected": norm_expected,
    }


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
