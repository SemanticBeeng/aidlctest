# Application Design Changelog

All notable architecture and application-design changes are documented here.

## 2026-03-19
- Added/expanded the hybrid inference architecture addendum, including explicit MVP design decisions for on-device runtimes (Cactus vs ExecuTorch vs MLX), server inference (vLLM vs Lemonade), and evaluation topology (DeepEval SUT vs judge separation).
- Added Decision D-EVAL-SUT-02 to explicitly capture the MVP0 choice: run Qwen3-under-test inference in-process via Unsloth for fast iteration, with exit criteria and an MVP1 migration path to vLLM.
- Added an explicit compatibility assessment between the current Unsloth evaluation implementation and the vLLM-oriented MVP decisions, plus minimal alignment paths (judge-first vs full vLLM endpoints).
- Added elaborated decision criteria comparing D-EVAL-SUT-02 vs D-SERVER-01 for the current DeepEval test suites in `code/unsloth_example_1`.
- Captured review feedback via the architecture addendum review question file and incorporated requested decision refinements.

## 2026-03-20
- Introduced a Design Domain ubiquitous language under `aidlc-docs/designdomain/`.
- Added concept pages for Model Inference Engine and Model Inference Server and technology pages (vLLM, SGLang, Lemonade, TensorRT-LLM, NVIDIA NIM, ExecuTorch, Cactus, Apple MLX, Unsloth, Privatemode pattern).
- Refactored architecture/design docs to reference these abstract concepts consistently.
