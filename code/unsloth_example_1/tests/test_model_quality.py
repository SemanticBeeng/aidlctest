"""
Model Quality Tests — DeepEval + pytest
========================================
Run with:  poetry run deepeval test run tests/test_model_quality.py
    or:    poetry run pytest tests/test_model_quality.py -v

Each test function evaluates one metric against pre-generated test cases.
Fixtures in conftest.py handle model loading and output generation once
per session to avoid redundant GPU work.

Requires:
  - OPENAI_API_KEY env var (for LLM-as-judge metrics)
  - Trained model in phone_model/ directory
"""

import pytest
from deepeval import assert_test


# ---------------------------------------------------------------------------
# Suite 1: Mathematical Correctness
# ---------------------------------------------------------------------------
class TestMathCorrectness:
    """Does the QAT model produce correct final answers for math problems?"""

    @pytest.mark.parametrize("idx", range(20))  # matches n_math_eval in conftest
    def test_math_correctness(self, idx, math_test_cases, metrics):
        if idx >= len(math_test_cases):
            pytest.skip(f"Only {len(math_test_cases)} math cases available")
        assert_test(math_test_cases[idx], [metrics["math_correctness"]])


# ---------------------------------------------------------------------------
# Suite 2: Reasoning Quality
# ---------------------------------------------------------------------------
class TestReasoningQuality:
    """Is the chain-of-thought reasoning coherent and logically sound?"""

    @pytest.mark.parametrize("idx", range(20))
    def test_reasoning_quality(self, idx, math_test_cases, metrics):
        if idx >= len(math_test_cases):
            pytest.skip(f"Only {len(math_test_cases)} math cases available")
        assert_test(math_test_cases[idx], [metrics["reasoning_quality"]])


# ---------------------------------------------------------------------------
# Suite 3: Chat Quality — Relevancy
# ---------------------------------------------------------------------------
class TestChatRelevancy:
    """Are general chat responses relevant to the user's question?"""

    @pytest.mark.parametrize("idx", range(10))  # matches n_chat_eval in conftest
    def test_answer_relevancy(self, idx, chat_test_cases, metrics):
        if idx >= len(chat_test_cases):
            pytest.skip(f"Only {len(chat_test_cases)} chat cases available")
        assert_test(chat_test_cases[idx], [metrics["relevancy"]])


# ---------------------------------------------------------------------------
# Suite 3: Chat Quality — Toxicity
# ---------------------------------------------------------------------------
class TestChatToxicity:
    """Are general chat responses free from toxic content?"""

    @pytest.mark.parametrize("idx", range(10))
    def test_toxicity(self, idx, chat_test_cases, metrics):
        if idx >= len(chat_test_cases):
            pytest.skip(f"Only {len(chat_test_cases)} chat cases available")
        assert_test(chat_test_cases[idx], [metrics["toxicity"]])


# ---------------------------------------------------------------------------
# Suite 3: Chat Quality — Bias
# ---------------------------------------------------------------------------
class TestChatBias:
    """Are general chat responses free from demographic bias?"""

    @pytest.mark.parametrize("idx", range(10))
    def test_bias(self, idx, chat_test_cases, metrics):
        if idx >= len(chat_test_cases):
            pytest.skip(f"Only {len(chat_test_cases)} chat cases available")
        assert_test(chat_test_cases[idx], [metrics["bias"]])
