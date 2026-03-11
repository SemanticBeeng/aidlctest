"""
Model Quality Tests — DeepEval + pytest
========================================
Run with:  poetry run deepeval test run tests/test_model_quality.py
    or:    poetry run pytest tests/test_model_quality.py -v

Dataset-specific evaluation suites:

  OpenMathReasoning-mini (COT split) — the 75% reasoning training source:
    - TestMathCorrectness: Final numerical answer accuracy
    - TestReasoningQuality: Chain-of-thought logical coherence
    - TestCOTFormatCompliance: COT format structure (LLM-judge)
    - TestFinalAnswerExtraction: Clear answer demarcation (LLM-judge)
    - TestThinkTokenUsage: Proper <think>...</think> usage (programmatic)
    - TestExpectedAnswerMatch: Exact-match against expected_answer (programmatic)

  FineTome-100k (ShareGPT) — the 25% chat training source:
    - TestChatRelevancy: Response relevance to the question
    - TestChatToxicity: Freedom from toxic content
    - TestChatBias: Freedom from demographic bias
    - TestInstructionFollowing: Faithful instruction compliance
    - TestResponseCompleteness: Full, non-truncated responses
    - TestMultiTurnCoherence: Multi-turn conversation context handling

Fixtures in conftest.py handle model loading and output generation once
per session to avoid redundant GPU work.

Requires:
  - OPENAI_API_KEY env var (for LLM-as-judge metrics)
  - Trained model in phone_model/ directory
"""

import pytest
from deepeval import assert_test

from training.evaluate_model import (
    check_expected_answer_match,
    check_final_answer_extractable,
    check_think_token_usage,
)


# ===========================================================================
# OpenMathReasoning-mini — Reasoning Dataset Tests (75% of training data)
# ===========================================================================


# ---------------------------------------------------------------------------
# Suite 1: Mathematical Correctness (LLM-judge)
# ---------------------------------------------------------------------------
class TestMathCorrectness:
    """Does the QAT model produce correct final answers for math problems?

    Evaluates against held-out samples from unsloth/OpenMathReasoning-mini
    (COT split). GPT-4 judges whether the final numerical answer matches
    the reference solution, allowing for different reasoning paths.
    """

    @pytest.mark.parametrize("idx", range(20))
    def test_math_correctness(self, idx, math_test_cases, metrics):
        if idx >= len(math_test_cases):
            pytest.skip(f"Only {len(math_test_cases)} math cases available")
        assert_test(math_test_cases[idx], [metrics["math_correctness"]])


# ---------------------------------------------------------------------------
# Suite 2: Reasoning Quality (LLM-judge)
# ---------------------------------------------------------------------------
class TestReasoningQuality:
    """Is the chain-of-thought reasoning coherent and logically sound?

    Checks that step-by-step reasoning progresses logically without
    hallucinated steps, circular reasoning, or unjustified assertions.
    Uses the same math test cases — no additional inference needed.
    """

    @pytest.mark.parametrize("idx", range(20))
    def test_reasoning_quality(self, idx, math_test_cases, metrics):
        if idx >= len(math_test_cases):
            pytest.skip(f"Only {len(math_test_cases)} math cases available")
        assert_test(math_test_cases[idx], [metrics["reasoning_quality"]])


# ---------------------------------------------------------------------------
# Suite 3: COT Format Compliance (LLM-judge)
# ---------------------------------------------------------------------------
class TestCOTFormatCompliance:
    """Does the model follow the COT format from OpenMathReasoning training?

    The training data uses structured chain-of-thought with discrete steps,
    intermediate calculations, mathematical notation, and clear final answer
    demarcation. This tests whether the QAT model retained that structure.
    """

    @pytest.mark.parametrize("idx", range(20))
    def test_cot_format(self, idx, math_test_cases, metrics):
        if idx >= len(math_test_cases):
            pytest.skip(f"Only {len(math_test_cases)} math cases available")
        assert_test(math_test_cases[idx], [metrics["cot_format_compliance"]])


# ---------------------------------------------------------------------------
# Suite 4: Final Answer Extraction (LLM-judge)
# ---------------------------------------------------------------------------
class TestFinalAnswerExtraction:
    """Can the final answer be clearly extracted from model output?

    Tests whether the model produces a clearly identifiable final answer
    (boxed, labeled, or otherwise demarcated) rather than trailing off
    or burying the answer in the reasoning.
    """

    @pytest.mark.parametrize("idx", range(20))
    def test_final_answer_extraction(self, idx, math_test_cases, metrics):
        if idx >= len(math_test_cases):
            pytest.skip(f"Only {len(math_test_cases)} math cases available")
        assert_test(math_test_cases[idx], [metrics["final_answer_extraction"]])


# ---------------------------------------------------------------------------
# Suite 5: Think Token Usage (programmatic — no LLM judge)
# ---------------------------------------------------------------------------
class TestThinkTokenUsage:
    """Does the model use <think>...</think> tokens correctly?

    Qwen3 uses think tokens for internal reasoning. This programmatically
    checks that:
    - Think tokens are properly opened AND closed (balanced)
    - The model produces actual answer content OUTSIDE think tokens
    - The model uses think tokens for math problems (reasoning should
      trigger thinking mode)

    This is a fast, deterministic check — no OpenAI API calls.
    """

    @pytest.mark.parametrize("idx", range(20))
    def test_think_tokens_balanced(self, idx, math_test_cases):
        """Think tokens must be properly opened and closed."""
        if idx >= len(math_test_cases):
            pytest.skip(f"Only {len(math_test_cases)} math cases available")

        tc = math_test_cases[idx]
        result = check_think_token_usage(tc.actual_output)

        if result["has_think_tokens"]:
            assert result["balanced"], (
                f"Unbalanced think tokens: {result['open_count']} opens, "
                f"{result['close_count']} closes"
            )

    @pytest.mark.parametrize("idx", range(20))
    def test_answer_outside_think(self, idx, math_test_cases):
        """Model must produce answer content outside <think> blocks."""
        if idx >= len(math_test_cases):
            pytest.skip(f"Only {len(math_test_cases)} math cases available")

        tc = math_test_cases[idx]
        result = check_think_token_usage(tc.actual_output)

        if result["has_think_tokens"]:
            assert result["has_answer_outside_think"], (
                "Model produced think tokens but no answer content outside them. "
                "The entire response is inside <think>...</think>."
            )


# ---------------------------------------------------------------------------
# Suite 6: Expected Answer Exact Match (programmatic — no LLM judge)
# ---------------------------------------------------------------------------
class TestExpectedAnswerMatch:
    """Does the extracted final answer match the dataset's expected_answer?

    OpenMathReasoning-mini includes an expected_answer field with the
    known-correct numerical result. This tries to extract the model's
    final answer programmatically and compare it exactly (after
    normalization) to the expected value.

    Skips samples where expected_answer is empty or extraction fails.
    This is a stricter check than the LLM-judge math correctness.
    """

    @pytest.mark.parametrize("idx", range(20))
    def test_expected_answer_match(self, idx, math_test_cases):
        if idx >= len(math_test_cases):
            pytest.skip(f"Only {len(math_test_cases)} math cases available")

        tc = math_test_cases[idx]
        expected_answer = (tc.additional_metadata or {}).get("expected_answer", "")

        if not expected_answer:
            pytest.skip("No expected_answer available for this sample")

        result = check_expected_answer_match(tc.actual_output, expected_answer)

        if not result["matchable"]:
            pytest.skip(result["reason"])

        # This is informational — we don't hard-fail on extraction issues
        # but DO fail when extraction succeeds and the answer is wrong
        if result.get("actual_extracted"):
            assert result["match"], (
                f"Answer mismatch: extracted '{result['actual_extracted']}' "
                f"but expected '{result['expected']}' "
                f"(normalized: '{result['norm_actual']}' vs '{result['norm_expected']}')"
            )
        else:
            # Could not extract — check via the LLM-judge metrics instead
            pytest.skip("Could not programmatically extract final answer")


# ---------------------------------------------------------------------------
# Suite 7: Final Answer Extractability (programmatic — no LLM judge)
# ---------------------------------------------------------------------------
class TestAnswerExtractability:
    """Can a simple parser find the final answer in the model output?

    Uses regex patterns to detect common answer-demarcation formats:
    \\boxed{}, 'The answer is', 'Therefore', 'Thus', etc.
    Complements the LLM-judge TestFinalAnswerExtraction with a
    deterministic, fast check.
    """

    @pytest.mark.parametrize("idx", range(20))
    def test_programmatic_extractability(self, idx, math_test_cases):
        if idx >= len(math_test_cases):
            pytest.skip(f"Only {len(math_test_cases)} math cases available")

        tc = math_test_cases[idx]
        result = check_final_answer_extractable(tc.actual_output)

        assert result["extractable"], (
            f"No recognizable answer pattern found in output. "
            f"Checked: boxed, 'the answer is', therefore, thus, "
            f"final answer label, trailing number. "
            f"Output (first 200 chars): {result['clean_output'][:200]}"
        )


# ===========================================================================
# FineTome-100k — Chat Dataset Tests (25% of training data)
# ===========================================================================


# ---------------------------------------------------------------------------
# Suite 8: Chat Relevancy (LLM-judge)
# ---------------------------------------------------------------------------
class TestChatRelevancy:
    """Are general chat responses relevant to the user's question?

    Evaluated on held-out single-turn samples from FineTome-100k.
    Uses DeepEval's built-in AnswerRelevancyMetric.
    """

    @pytest.mark.parametrize("idx", range(10))
    def test_answer_relevancy(self, idx, chat_test_cases, metrics):
        if idx >= len(chat_test_cases):
            pytest.skip(f"Only {len(chat_test_cases)} chat cases available")
        assert_test(chat_test_cases[idx], [metrics["relevancy"]])


# ---------------------------------------------------------------------------
# Suite 9: Chat Toxicity (LLM-judge)
# ---------------------------------------------------------------------------
class TestChatToxicity:
    """Are general chat responses free from toxic content?"""

    @pytest.mark.parametrize("idx", range(10))
    def test_toxicity(self, idx, chat_test_cases, metrics):
        if idx >= len(chat_test_cases):
            pytest.skip(f"Only {len(chat_test_cases)} chat cases available")
        assert_test(chat_test_cases[idx], [metrics["toxicity"]])


# ---------------------------------------------------------------------------
# Suite 10: Chat Bias (LLM-judge)
# ---------------------------------------------------------------------------
class TestChatBias:
    """Are general chat responses free from demographic bias?"""

    @pytest.mark.parametrize("idx", range(10))
    def test_bias(self, idx, chat_test_cases, metrics):
        if idx >= len(chat_test_cases):
            pytest.skip(f"Only {len(chat_test_cases)} chat cases available")
        assert_test(chat_test_cases[idx], [metrics["bias"]])


# ---------------------------------------------------------------------------
# Suite 11: Instruction Following (LLM-judge)
# ---------------------------------------------------------------------------
class TestInstructionFollowing:
    """Does the model faithfully follow user instructions from FineTome?

    FineTome-100k is an instruction-following dataset. This tests whether
    the QAT model retained the ability to: (1) address all parts of an
    instruction, (2) respect format requests, (3) stay on topic, and
    (4) follow explicit constraints.
    """

    @pytest.mark.parametrize("idx", range(10))
    def test_instruction_following(self, idx, chat_test_cases, metrics):
        if idx >= len(chat_test_cases):
            pytest.skip(f"Only {len(chat_test_cases)} chat cases available")
        assert_test(chat_test_cases[idx], [metrics["instruction_following"]])


# ---------------------------------------------------------------------------
# Suite 12: Response Completeness (LLM-judge)
# ---------------------------------------------------------------------------
class TestResponseCompleteness:
    """Are chat responses complete and not truncated?

    QAT quantization can sometimes cause the model to generate shorter
    or truncated responses. This checks that responses are full,
    non-trailing, and cover the expected depth.
    """

    @pytest.mark.parametrize("idx", range(10))
    def test_response_completeness(self, idx, chat_test_cases, metrics):
        if idx >= len(chat_test_cases):
            pytest.skip(f"Only {len(chat_test_cases)} chat cases available")
        assert_test(chat_test_cases[idx], [metrics["response_completeness"]])


# ---------------------------------------------------------------------------
# Suite 13: Multi-Turn Conversation Coherence (LLM-judge)
# ---------------------------------------------------------------------------
class TestMultiTurnCoherence:
    """Can the model handle multi-turn conversation context?

    FineTome-100k contains multi-turn ShareGPT conversations. The model
    receives all preceding turns and must generate a coherent final
    assistant response that:
    - References prior context appropriately
    - Maintains the conversation thread
    - Doesn't repeat or contradict earlier turns

    Tests relevancy, instruction following, and completeness on
    multi-turn inputs (as opposed to the single-turn tests above).
    """

    @pytest.mark.parametrize("idx", range(10))
    def test_multiturn_relevancy(self, idx, multiturn_test_cases, metrics):
        if idx >= len(multiturn_test_cases):
            pytest.skip(f"Only {len(multiturn_test_cases)} multi-turn cases available")
        assert_test(multiturn_test_cases[idx], [metrics["relevancy"]])

    @pytest.mark.parametrize("idx", range(10))
    def test_multiturn_instruction_following(
        self, idx, multiturn_test_cases, metrics
    ):
        if idx >= len(multiturn_test_cases):
            pytest.skip(f"Only {len(multiturn_test_cases)} multi-turn cases available")
        assert_test(multiturn_test_cases[idx], [metrics["instruction_following"]])

    @pytest.mark.parametrize("idx", range(10))
    def test_multiturn_completeness(self, idx, multiturn_test_cases, metrics):
        if idx >= len(multiturn_test_cases):
            pytest.skip(f"Only {len(multiturn_test_cases)} multi-turn cases available")
        assert_test(multiturn_test_cases[idx], [metrics["response_completeness"]])
