# Unsloth + ExecuTorch Phone Deployment Research

> **Sources studied**:
> - https://unsloth.ai/docs/basics/inference-and-deployment/deploy-llms-phone
> - Colab notebook: `Qwen3_(0_6B)-Phone_Deployment.ipynb`
>
> **Date**: 2026-03-11

---

## 1. Pipeline Components Extracted

### 1.1 Training Pipeline (Unsloth + TorchAO QAT)

| Aspect | Detail |
|---|---|
| Entry point | `FastLanguageModel.from_pretrained()` |
| QAT scheme | `"phone-deployment"` (alias for `"int8-int4"`) |
| Quantization strategy | INT8 dynamic activation quantization + INT4 weight quantization via fake-quantization ops during training; computations stay in FP16 |
| Post-training conversion | Real quantized model produced after training finishes |
| Accuracy claim | QAT recovers ~70% of accuracy lost by naïve PTQ |
| Fine-tuning mode | `full_finetuning = True` (full parameter updates, not LoRA) |
| Trainer | `SFTTrainer` from HuggingFace TRL library with `SFTConfig` |
| Optimizer | `adamw_8bit` |
| Hardware | Runs on free Tesla T4 (14.7 GB VRAM); peak reserved ~10.5 GB |

**Reuse Decision**: The QAT `int8-int4` scheme is directly relevant to our FR-07 (Model Optimization and Selection Process). Our iterative QAT/DeepEval/benchmarking loop should use this exact scheme as the baseline quantization strategy for on-device Qwen3 models.

### 1.2 Data Preparation Pipeline

| Aspect | Detail |
|---|---|
| Dataset mixing | Controlled ratio of reasoning vs non-reasoning data |
| Example ratio | 75% reasoning (OpenMathReasoning-mini COT traces) + 25% chat (FineTome-100k ShareGPT) |
| Format normalization | `standardize_sharegpt()` converts ShareGPT format to HuggingFace multiturn |
| Chat templates | `tokenizer.apply_chat_template()` converts both data sources to unified conversation format |
| Combination | `pd.concat()` + shuffle with seed for reproducibility |

**Reuse Decision**: Our shopping domain will need its own data preparation pipeline. The mixing-ratio pattern (domain reasoning traces + general chat) is directly reusable. Our ratio will likely be inverted: majority domain shopping data + minority general conversation data.

### 1.3 Model Export Pipeline (ExecuTorch)

| Step | Command / Tool | Output |
|---|---|---|
| Save QAT model | `model.save_pretrained_torchao("phone_model", tokenizer=tokenizer)` | Checkpoint directory |
| Convert weights | `python -m executorch.examples.models.qwen3.convert_weights "phone_model" pytorch_model_converted.bin` | ExecuTorch-compatible weight format |
| Download config | `curl -L -o 0.6B_config.json` from ExecuTorch repo | Model architecture config |
| Export to .pte | `python -m executorch.examples.models.llama.export_llama` | `.pte` file (~472 MB for 0.6B) |

**Export parameters of note**:
- `--max_context_length 1024` — maximum context window
- `--max_seq_length 128` — maximum generation length per forward pass
- `--dtype fp32` — inference precision
- `-kv --use_sdpa_with_kv_cache` — efficient KV cache attention
- `-X --xnnpack-extended-ops` — XNNPACK CPU backend with extended operations
- `--metadata '{"get_bos_id":199999, "get_eos_ids":[200020,199999]}'` — Qwen3 tokenizer special tokens

**Reuse Decision**: This is the **critical tension point** with our current architecture. Our design specifies **Cactus inference engine** (GGUF-based), not ExecuTorch (.pte-based). See Section 3 for architectural implications.

### 1.4 iOS Deployment Components (ExecuTorch Runtime)

| Component | Detail |
|---|---|
| Demo app | `etLLM.xcodeproj` from `meta-pytorch/executorch-examples` |
| Platform req | Xcode 15+, iOS 18 for simulator |
| Critical capability | `increased-memory-limit` (requires paid Apple Developer account for physical device) |
| Model artifacts | `.pte` model file + `tokenizer.json` |
| Model loading | File-system based; model loaded from app-local directory |
| Inference speed | ~40 tokens/s on Qwen3-0.6B (iPhone 15 Pro, Pixel 8) |
| Model size | ~472 MB for Qwen3-0.6B |

**Reuse Decision**: The iOS deployment constraints (memory limit capability, artifact size planning, file-based model loading pattern) apply regardless of whether we use ExecuTorch or Cactus.

### 1.5 Model Architecture Internals (Qwen3-0.6B)

From export logs:
- 28 Transformer layers
- Embedding: 151,936 vocab size, 1024 hidden dim
- Attention: Multi-Head Attention with RMSNorm on Q/K, Rope position encoding
- Q projection: 1024→2048, K/V: 1024→1024
- Feed-forward: 1024→3072→1024
- CustomKVCache + SDPACustom for efficient inference
- Total activation memory: ~244 MB at inference time

**Reuse Decision**: These dimensions inform our memory budget planning for iOS. The 472 MB model + ~244 MB activation memory = ~716 MB minimum RAM footprint for 0.6B model alone.

---

## 2. Design Decisions Extracted

### D1. QAT > PTQ for On-Device Models
- QAT (quantization-aware training) recovers ~70% of accuracy lost by post-training quantization
- The `int8-int4` scheme keeps training in FP16 with fake quantization, then converts to real quantized weights
- **Project impact**: Aligns with FR-07. Our model optimization loop should prioritize QAT over PTQ for deployed on-device models.

### D2. Context Length Constraints for Mobile
- `max_context_length=1024` tokens for the on-device model
- `max_seq_length=128` tokens for generation per forward pass
- **Project impact**: Directly constrains UC-14 (Context-Rot Detection), UC-16 (Context Integrity Checkpointing), and UC-06 (Multi-Turn Plan Refinement). Our C06 Context-Rot Detector must operate within these limits. The 1024-token context window means multi-turn conversations will need aggressive checkpointing and summarization.

### D3. XNNPACK Backend for CPU Inference
- ExecuTorch uses XNNPACK with extended ops for CPU-based inference
- No GPU/ANE (Apple Neural Engine) in this default pipeline
- **Project impact**: If we supplement or replace Cactus with ExecuTorch, XNNPACK is the baseline backend. Metal/CoreML backends would be a separate optimization path.

### D4. Data Mixing Ratios Are Tunable
- The notebook demonstrates explicit control over reasoning vs chat data ratios
- Sampling uses reproducible seeds
- **Project impact**: Our domain-specific shopping data pipeline should implement the same mixing-ratio pattern. Key parameter: what percentage general conversational data vs domain shopping training data.

### D5. Full Fine-Tuning (Not LoRA) for Phone Deployment
- `full_finetuning = True` is used, not adapter-based fine-tuning
- This produces a standalone model with no adapter overhead at inference
- **Project impact**: For on-device deployment, full fine-tuning eliminates adapter merging complexity and ensures a single monolithic model file.

### D6. Model File = Single .pte Artifact + Tokenizer
- Deployment artifacts are exactly two files: the model `.pte` and `tokenizer.json`
- No additional configuration or adapter files needed at runtime
- **Project impact**: Simplifies our C02 On-Device Inference Adapter model management. Model packs can be versioned as pairs of (model-file, tokenizer-file).

### D7. Memory Limit Capability is Mandatory on iOS
- ExecuTorch requires `increased-memory-limit` entitlement on iOS
- This is an iOS provisioning constraint, not just a code constraint
- **Project impact**: Our Xcode project configuration must include this entitlement. This also means testing on physical devices requires a paid Apple Developer account.

### D8. ~40 tok/s Benchmark on 0.6B
- Qwen3-0.6B achieves ~40 tokens/s on modern hardware (iPhone 15 Pro, Pixel 8)
- **Project impact**: This is a baseline for our NFR-01 latency expectations. For larger Qwen3 variants (4B, 8B), expect proportionally lower tok/s, which influences the routing threshold in C03.

---

## 3. Architectural Tension: Cactus (GGUF) vs ExecuTorch (.pte)

### Current Architecture Assumption
Our FR-04 and C02 specify **Cactus inference engine** with a native iOS wrapper. Cactus is ggml/llama.cpp-based and uses **GGUF** model format.

### Unsloth/ExecuTorch Approach
The studied pipeline uses **ExecuTorch** runtime with **XNNPACK** backend and **.pte** model format. This is Meta's official mobile inference framework.

### Comparison Matrix

| Dimension | Cactus (GGUF) | ExecuTorch (.pte) |
|---|---|---|
| Model format | GGUF | .pte (ExecuTorch Program) |
| Quantization | GGML quantization (Q4_K_M, Q5_K_M, etc.) | TorchAO QAT (int8-int4) |
| Backend | llama.cpp / Metal | XNNPACK (CPU) / CoreML / Metal |
| Accuracy recovery | PTQ-based (lower recovery) | QAT-based (~70% accuracy recovery) |
| Training pipeline | Separate (any trainer → GGUF convert) | Integrated (Unsloth QAT → export_llama → .pte) |
| iOS integration | C library wrapper | Swift/ObjC ExecuTorch runtime |
| Maturity for Qwen3 | Depends on ggml Qwen3 support | Officially supported by Unsloth + ExecuTorch |
| Model loading | File-based | File-based |
| Community/support | llama.cpp community | Meta / PyTorch Foundation |

### Options for Our Project

**Option A: Stay with Cactus (GGUF)**
- Keep C02 as designed
- Use separate GGUF quantization (PTQ with Q4_K_M or similar)
- Lose QAT accuracy recovery advantage
- Cactus may have Metal acceleration support out of the box

**Option B: Switch to ExecuTorch (.pte)**
- Replace Cactus with ExecuTorch runtime in C02
- Use Unsloth QAT pipeline directly
- Get integrated training-to-deployment pipeline
- XNNPACK CPU baseline, with Metal/CoreML as optimization path
- Stronger Meta/PyTorch ecosystem backing

**Option C: Dual-Runtime Support (Adapter Pattern)**
- Keep C02's `OnDeviceInferencePort` interface
- Implement both `CactusInferenceAdapter` and `ExecuTorchInferenceAdapter`
- Model optimization loop (FR-07) evaluates both runtimes
- Higher implementation cost, maximum flexibility

**Recommendation**: Option B or C depending on Cactus's actual Qwen3 support maturity. The QAT accuracy advantage and integrated pipeline from Unsloth are significant. Our adapter-pattern architecture (NFR-04) already supports this switch cleanly.

---

## 4. Reusable Components Mapped to Existing Architecture

| Unsloth/ET Component | Maps To | Reuse Type |
|---|---|---|
| QAT training pipeline (`phone-deployment` scheme) | FR-07, Model Optimization loop | Training infrastructure |
| Data mixing ratio pattern | Training data pipeline (new) | Data engineering pattern |
| `save_pretrained_torchao()` | Model artifact management | Export tooling |
| `.pte` export pipeline | C02 model packaging | Build pipeline |
| `etLLM` iOS app structure | C01 Mobile App Client | Reference architecture |
| XNNPACK backend config | C02 On-Device Inference Adapter | Runtime configuration |
| `tokenizer.json` + model pair | C02 model-pack abstraction | Artifact schema |
| `increased-memory-limit` entitlement | iOS project config | Build constraint |
| Context length bounds (1024/128) | C03 routing thresholds, C06 rot detection | System parameters |
| 40 tok/s benchmark | NFR-01, C03 routing decisions | Performance baseline |

---

## 5. New Components / Concerns Surfaced

### NC-01 Training Pipeline Orchestrator (not in current design)
The current architecture has no explicit component for managing the QAT training pipeline. FR-07 describes the process but no component owns it.

**Suggestion**: Add a build-time component or CI pipeline stage for:
- Dataset preparation (mixing, formatting)
- QAT training execution
- Model export (GGUF or .pte)
- Benchmark evaluation
- Artifact publishing

### NC-02 Model Version / Pack Manager
The two-file deployment pattern (model + tokenizer) needs a versioning and distribution strategy for OTA model updates.

### NC-03 Context Window Budget Allocator
Given the 1024-token constraint, a component should manage token budget allocation across:
- System prompt
- Memory/preference injection
- Conversation history
- User's current turn
- Reserved generation tokens

This maps partially to C05 (Memory & Context Store) but is a distinct concern.

---

## 6. Key Numbers for Planning

| Metric | Value | Source |
|---|---|---|
| Qwen3-0.6B .pte size | ~472 MB | Colab notebook output |
| Activation memory | ~244 MB | Export log (`Required memory for activation`) |
| Total RAM footprint (0.6B) | ~716 MB minimum | Model + activation |
| Inference speed (0.6B) | ~40 tok/s | Unsloth docs (iPhone 15 Pro) |
| Max context length | 1024 tokens | Export parameter |
| Max generation length | 128 tokens | Export parameter |
| Training VRAM (0.6B, T4) | ~10.5 GB peak | Colab notebook output |
| Training time (100 steps, T4) | ~11.6 minutes | Colab notebook output |
| Vocab size | 151,936 | Export log |
| Hidden dim | 1024 | Export log |
| Transformer layers | 28 | Export log |
