"""
Shared pytest fixtures for model evaluation tests.

Loads models and evaluation data once per session to avoid
redundant GPU memory allocation and HuggingFace downloads.

Fixtures cover:
  - OpenMathReasoning-mini: math eval samples with expected_answer metadata
  - FineTome-100k: single-turn chat samples + multi-turn conversation samples
  - Model output generation for all sample types
"""

import pytest
import torch
from datasets import load_dataset
from unsloth import FastLanguageModel
from unsloth.chat_templates import standardize_sharegpt

from training.evaluate_model import (
    EvalConfig,
    build_metrics,
    generate_response,
    prepare_multiturn_eval_data,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def eval_config():
    """Session-wide evaluation config with reduced sizes for test speed.

    Respects QAT_MODEL_DIR env var to override the model path,
    allowing evaluation of the base model without training.
    """
    import os

    return EvalConfig(
        qat_model_dir=os.environ.get("QAT_MODEL_DIR", "phone_model"),
        n_math_eval=20,
        n_chat_eval=10,
        n_multiturn_eval=10,
        max_new_tokens=256,
    )


@pytest.fixture(scope="session")
def metrics(eval_config):
    """Build all DeepEval metrics once per session."""
    return build_metrics(eval_config)


# ---------------------------------------------------------------------------
# Model Loading
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def qat_model_and_tokenizer(eval_config):
    """Load the QAT model once per session."""
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=eval_config.qat_model_dir,
        max_seq_length=eval_config.max_seq_length,
    )
    FastLanguageModel.for_inference(model)
    yield model, tokenizer
    del model
    torch.cuda.empty_cache()


# ---------------------------------------------------------------------------
# OpenMathReasoning-mini Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def math_eval_samples(eval_config):
    """Load held-out math evaluation samples with full metadata.

    Includes expected_answer for programmatic exact-match checking.
    Source: unsloth/OpenMathReasoning-mini (COT split), tail-end holdout.
    """
    ds = load_dataset(
        eval_config.reasoning_dataset_name, split=eval_config.reasoning_split
    )
    total = len(ds)
    start_idx = max(0, total - eval_config.n_math_eval)
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
    return samples


@pytest.fixture(scope="session")
def math_test_cases(qat_model_and_tokenizer, math_eval_samples, eval_config):
    """Generate model outputs for all math samples (once per session).

    Each test case preserves expected_answer in additional_metadata
    for downstream programmatic checks.
    """
    from deepeval.test_case import LLMTestCase

    model, tokenizer = qat_model_and_tokenizer
    cases = []
    for sample in math_eval_samples:
        output = generate_response(model, tokenizer, sample["input"], eval_config)
        tc = LLMTestCase(
            input=sample["input"],
            actual_output=output,
            expected_output=sample.get("expected_output"),
            additional_metadata={
                "expected_answer": sample.get("expected_answer", ""),
                "dataset": "OpenMathReasoning-mini",
                "split": "cot",
            },
        )
        cases.append(tc)
    return cases


# ---------------------------------------------------------------------------
# FineTome-100k Single-Turn Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def chat_eval_samples(eval_config, qat_model_and_tokenizer):
    """Load held-out single-turn chat evaluation samples.

    Source: mlabonne/FineTome-100k (ShareGPT format), tail-end holdout.
    Extracts first user→assistant turn pair from each conversation.
    """
    _, tokenizer = qat_model_and_tokenizer
    ds = load_dataset(eval_config.chat_dataset_name, split=eval_config.chat_split)
    ds = standardize_sharegpt(ds)

    total = len(ds)
    start_idx = max(0, total - eval_config.n_chat_eval)
    eval_ds = ds.select(range(start_idx, total))

    samples = []
    for row in eval_ds:
        conversations = row["conversations"]
        if len(conversations) >= 2:
            user_msg = None
            assistant_msg = None
            for turn in conversations:
                if turn["role"] == "user" and user_msg is None:
                    user_msg = turn["content"]
                elif turn["role"] == "assistant" and assistant_msg is None:
                    assistant_msg = turn["content"]
            if user_msg and assistant_msg:
                samples.append(
                    {"input": user_msg, "expected_output": assistant_msg}
                )

    return samples[: eval_config.n_chat_eval]


@pytest.fixture(scope="session")
def chat_test_cases(qat_model_and_tokenizer, chat_eval_samples, eval_config):
    """Generate model outputs for single-turn chat samples."""
    from deepeval.test_case import LLMTestCase

    model, tokenizer = qat_model_and_tokenizer
    cases = []
    for sample in chat_eval_samples:
        output = generate_response(model, tokenizer, sample["input"], eval_config)
        cases.append(
            LLMTestCase(
                input=sample["input"],
                actual_output=output,
                expected_output=sample.get("expected_output"),
                additional_metadata={
                    "dataset": "FineTome-100k",
                    "type": "single_turn",
                },
            )
        )
    return cases


# ---------------------------------------------------------------------------
# FineTome-100k Multi-Turn Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def multiturn_eval_samples(eval_config, qat_model_and_tokenizer):
    """Load held-out multi-turn conversation samples.

    Source: mlabonne/FineTome-100k, conversations with 4+ turns.
    The model receives all turns up to the last assistant turn and
    must generate the final assistant response.
    """
    _, tokenizer = qat_model_and_tokenizer
    return prepare_multiturn_eval_data(eval_config, tokenizer)


@pytest.fixture(scope="session")
def multiturn_test_cases(
    qat_model_and_tokenizer, multiturn_eval_samples, eval_config
):
    """Generate model outputs for multi-turn conversation samples.

    Input is the full pre-formatted conversation context (via
    apply_chat_template), so we pass it directly rather than
    using generate_response which wraps in a single-user template.
    """
    from deepeval.test_case import LLMTestCase

    model, tokenizer = qat_model_and_tokenizer
    cases = []
    for sample in multiturn_eval_samples:
        # The input is already formatted via apply_chat_template,
        # so tokenize and generate directly
        inputs = tokenizer(
            sample["input"], return_tensors="pt"
        ).to(model.device)

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=eval_config.max_new_tokens,
                temperature=eval_config.temperature,
                top_p=eval_config.top_p,
                do_sample=True,
            )
        generated_ids = output_ids[0][inputs["input_ids"].shape[1] :]
        actual_output = tokenizer.decode(generated_ids, skip_special_tokens=True)

        cases.append(
            LLMTestCase(
                # Use the raw last-user-turn as display input
                input=sample.get("raw_input", sample["input"][:200]),
                actual_output=actual_output,
                expected_output=sample.get("expected_output"),
                additional_metadata={
                    "dataset": "FineTome-100k",
                    "type": "multi_turn",
                    "n_context_turns": sample.get("n_turns", 0),
                },
            )
        )
    return cases
