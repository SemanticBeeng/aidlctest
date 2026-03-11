"""
Shared pytest fixtures for model evaluation tests.

Loads models and evaluation data once per session to avoid
redundant GPU memory allocation and HuggingFace downloads.
"""

import pytest
import torch
from datasets import load_dataset
from unsloth import FastLanguageModel
from unsloth.chat_templates import standardize_sharegpt

from training.evaluate_model import EvalConfig, build_metrics, generate_response


@pytest.fixture(scope="session")
def eval_config():
    """Session-wide evaluation config."""
    return EvalConfig(
        n_math_eval=20,  # Smaller for test speed
        n_chat_eval=10,
        max_new_tokens=256,
    )


@pytest.fixture(scope="session")
def metrics(eval_config):
    """Build all DeepEval metrics once per session."""
    return build_metrics(eval_config)


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


@pytest.fixture(scope="session")
def math_eval_samples(eval_config):
    """Load held-out math evaluation samples."""
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
def chat_eval_samples(eval_config, qat_model_and_tokenizer):
    """Load held-out chat evaluation samples."""
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
def math_test_cases(qat_model_and_tokenizer, math_eval_samples, eval_config):
    """Generate model outputs for all math samples (once per session)."""
    from deepeval.test_case import LLMTestCase

    model, tokenizer = qat_model_and_tokenizer
    cases = []
    for sample in math_eval_samples:
        output = generate_response(model, tokenizer, sample["input"], eval_config)
        cases.append(
            LLMTestCase(
                input=sample["input"],
                actual_output=output,
                expected_output=sample.get("expected_output"),
            )
        )
    return cases


@pytest.fixture(scope="session")
def chat_test_cases(qat_model_and_tokenizer, chat_eval_samples, eval_config):
    """Generate model outputs for all chat samples (once per session)."""
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
            )
        )
    return cases
