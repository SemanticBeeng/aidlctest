# Unsloth + ExecuTorch Phone Deployment Research

> **Sources studied**:
> - https://unsloth.ai/docs/basics/inference-and-deployment/deploy-llms-phone
> - Colab notebook: `Qwen3_(0_6B)-Phone_Deployment.ipynb`
> - https://cactuscompute.com/docs (Cactus v1.7 docs — verification pass)
>
> **Date**: 2026-03-11
> **Last updated**: 2026-03-11 (added Cactus v1 verification findings)

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

**Reuse Decision**: This is the **critical tension point** with our current architecture. Our design specifies **Cactus as an on-device [[Model Inference Engine]]** (see Design Domain concept: [[Model Inference Engine]]). Note: Cactus v1 has moved from GGUF to a proprietary `.cact` format (see Section 3), making the gap wider than originally assumed. See Section 3 for architectural implications.

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

## 3. Architectural Tension: Cactus v1 (.cact) vs ExecuTorch (.pte)

> **CORRECTION (2026-03-11)**: Initial research assumed Cactus was GGUF/llama.cpp-based.
> Verification against Cactus v1.7 docs revealed Cactus has its own engine, proprietary
> `.cact` format, and built-in hybrid routing. All comparisons updated below.

### Current Architecture Assumption (CORRECTED)
Our FR-04 and C02 specify **Cactus as an on-device model inference engine** with a native iOS wrapper. Cactus v1 is **NOT** a llama.cpp wrapper — it is a standalone engine with three layers:
- **Cactus Engine**: Energy-efficient inference with OpenAI-compatible APIs (C/C++, Swift, Kotlin, Flutter), tool calling, auto RAG, NPU acceleration, INT4 quantization, and hybrid cloud handoff
- **Cactus Graph**: Zero-copy computation graph with PyTorch-like API for custom models, optimized for RAM efficiency and lossless weight quantization
- **Cactus Kernels**: Low-level ARM SIMD kernels optimized for Apple, Snapdragon, Google, Exynos, and MediaTek processors with custom attention kernels, KV-Cache quantization, and chunked prefill

Model format is proprietary **`.cact`** — not GGUF.

### Cactus Built-In Hybrid Routing (Overlap with C03)
Cactus v1 includes **confidence-based hybrid routing** that automatically switches between on-device and cloud inference. This directly overlaps with our C03 Routing Policy Engine design:
- Smart routing: dynamically routes to on-device NPU/CPU for simple tasks, cloud for complex ones
- Cloud fallback: configurable via `cactus auth` with fallback model selection
- Confidence monitoring: measures model confidence in real-time and routes accordingly
- Context window overflow handling: auto-failover when local model cannot handle context

**Architectural implication**: If we use Cactus, our C03 may need to either wrap/extend Cactus's routing or be redesigned as a policy layer on top of Cactus's built-in routing.

### Cactus v1 Performance Benchmarks (INT8 quantized)

| Device | LLM Performance | RAM |
|---|---|---|
| iPhone 17 Pro | 300/33 tps (prompt/gen) | 108 MB |
| iPad/Mac M4 | 379/46 tps | 30 MB |
| iPad/Mac M2 | 315/42 tps | 181 MB |
| Mac M4 Pro | 582/77 tps | 76 MB |
| Galaxy S25 Ultra | 226/36 tps | 1.2 GB |

**Note**: These benchmarks use INT8 quantized models on Cactus's own format. The RAM figures are dramatically lower than ExecuTorch's ~716 MB footprint for 0.6B, suggesting Cactus's zero-copy memory mapping is highly effective.

### Unsloth/ExecuTorch Approach
The studied pipeline uses **ExecuTorch** runtime with **XNNPACK** backend and **.pte** model format. This is Meta's official mobile inference framework.

### Comparison Matrix (CORRECTED)

| Dimension | Cactus v1 (.cact) | ExecuTorch (.pte) |
|---|---|---|
| Model format | `.cact` (proprietary, zero-copy) | `.pte` (ExecuTorch Program) |
| Quantization | Own INT4/INT8 with lossless weight quant | TorchAO QAT (int8-int4) |
| Backend | Cactus Kernels (ARM SIMD) + NPU | XNNPACK (CPU) / CoreML / Metal |
| NPU acceleration | Yes (Apple, Snapdragon, Exynos, MediaTek) | No (CPU-only in default pipeline) |
| Accuracy recovery | Unknown (proprietary quantization) | QAT-based (~70% accuracy recovery) |
| Training pipeline | No integrated training; needs converter to `.cact` | Integrated (Unsloth QAT → export_llama → .pte) |
| Hybrid routing | **Built-in** (confidence-based cloud fallback) | None (app-level only) |
| iOS integration | Swift SDK | Swift/ObjC ExecuTorch runtime |
| Maturity for Qwen3 | Check supported model list (may need request) | Officially supported by Unsloth + ExecuTorch |
| RAM efficiency | Very high (zero-copy memory mapping) | Standard (~716 MB for 0.6B) |
| Model loading | File-based (`.cact`) | File-based (`.pte` + `tokenizer.json`) |
| Community/support | Cactus Compute (YC-backed startup) | Meta / PyTorch Foundation |
| Open source | Partially (SDK open, format proprietary) | Fully open source |
| Pricing | Free tier + paid features | Free |

### QAT Compatibility with Cactus

**Statement investigated**: "If training LLM with QAT then cannot be used with Cactus"

| Step | Compatible? | Details |
|---|---|---|
| QAT training → HuggingFace checkpoint | Yes | QAT model saves as standard weights |
| HuggingFace checkpoint → `.cact` conversion | Unknown | Depends on Cactus converter supporting the architecture |
| QAT accuracy benefit preserved through `.cact` | **Unlikely** | QAT trains the model to tolerate a *specific* quantization pattern (TorchAO int8-int4). Re-quantizing with Cactus's different scheme would lose the matched QAT benefit |
| Unsloth pipeline outputs Cactus format | **No** | Outputs `.pte` only |

**Verdict**: QAT-trained models are not *physically incompatible* with Cactus (weights can be saved pre-quantization and re-converted), but the **QAT accuracy recovery advantage is likely lost** when re-quantizing to `.cact` format, since the model was trained to tolerate TorchAO's int8-int4 pattern, not Cactus's proprietary quantization.

### Options for Our Project (REVISED)

**Option A: Stay with Cactus (.cact)**
- Keep C02 as designed
- Use Cactus's own quantization pipeline (not Unsloth QAT)
- Gain: NPU acceleration, dramatically lower RAM, built-in hybrid routing, zero-copy mapping
- Lose: QAT accuracy recovery, integrated Unsloth training pipeline, open model format
- Risk: Qwen3 model support availability; proprietary format lock-in
- Simplifies C03: may wrap/extend Cactus routing instead of building from scratch

**Option B: Switch to ExecuTorch (.pte)**
- Replace Cactus with ExecuTorch runtime in C02
- Use Unsloth QAT pipeline directly for ~70% accuracy recovery
- Get integrated training-to-deployment pipeline
- XNNPACK CPU baseline, with Metal/CoreML as optimization path
- Stronger open-source ecosystem backing
- Higher RAM footprint; C03 routing built entirely custom

**Option C: Dual-Runtime Support (Adapter Pattern)**
- Keep C02's `OnDeviceInferencePort` interface
- Implement both `CactusInferenceAdapter` and `ExecuTorchInferenceAdapter`
- Model optimization loop (FR-07) evaluates both runtimes with their respective quantization
- C03 abstracts over Cactus's built-in routing vs custom ExecuTorch routing
- Highest implementation cost, maximum flexibility

**Recommendation (REVISED)**: The choice depends on two unknowns:
1. Does Cactus support Qwen3 models? (check model list)
2. How does Cactus's proprietary quantization compare to QAT for accuracy on our domain?

If Cactus supports Qwen3: Option A is compelling due to NPU acceleration, low RAM, and built-in hybrid routing (reducing C03 scope). If not: Option B with ExecuTorch. Option C is MVP-unfriendly but remains the safest long-term bet.

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
- QAT training execution (if ExecuTorch path) or Cactus-format conversion (if Cactus path)
- Model export (`.cact` or `.pte` depending on runtime choice)
- Benchmark evaluation
- Artifact publishing

### NC-02 Model Version / Pack Manager
The deployment artifact pattern (model + tokenizer for ExecuTorch; single `.cact` for Cactus) needs a versioning and distribution strategy for OTA model updates.

### NC-03 Context Window Budget Allocator
Given the 1024-token constraint, a component should manage token budget allocation across:
- System prompt
- Memory/preference injection
- Conversation history
- User's current turn
- Reserved generation tokens

This maps partially to C05 (Memory & Context Store) but is a distinct concern.

### NC-04 C03 Routing Policy Engine vs Cactus Built-In Routing (NEW)
Cactus v1 includes confidence-based hybrid routing that overlaps with our C03 Routing Policy Engine. Design must decide:
- **Wrap**: C03 delegates to Cactus routing, adding policy DSL evaluation on top
- **Replace**: C03 ignores Cactus routing and manages all decisions independently
- **Hybrid**: Use Cactus routing for simple confidence thresholds, C03 for domain-specific policies (context rot, data sufficiency, fine-tuning triggers)

This is a blocking design decision before Construction phase begins.

---

## 6. Key Numbers for Planning

| Metric | Value | Source |
|---|---|---|
| Qwen3-0.6B .pte size | ~472 MB | Colab notebook output |
| Activation memory (ExecuTorch) | ~244 MB | Export log (`Required memory for activation`) |
| Total RAM footprint — ExecuTorch (0.6B) | ~716 MB minimum | Model + activation |
| Total RAM footprint — Cactus (INT8) | ~108 MB (iPhone 17 Pro) | Cactus v1.7 docs |
| Inference speed — ExecuTorch (0.6B) | ~40 tok/s gen | Unsloth docs (iPhone 15 Pro) |
| Inference speed — Cactus (INT8, iPhone 17 Pro) | 300/33 tps (prompt/gen) | Cactus v1.7 docs |
| Max context length | 1024 tokens | Export parameter (ExecuTorch) |
| Max generation length | 128 tokens | Export parameter (ExecuTorch) |
| Training VRAM (0.6B, T4) | ~10.5 GB peak | Colab notebook output |
| Training time (100 steps, T4) | ~11.6 minutes | Colab notebook output |
| Vocab size | 151,936 | Export log |
| Hidden dim | 1024 | Export log |
| Transformer layers | 28 | Export log |

---

## 7. Open Questions Requiring Resolution

| # | Question | Blocking? | Needed For |
|---|---|---|---|
| OQ-1 | Does Cactus v1 support Qwen3 models? | Yes | Runtime selection (Option A vs B vs C) |
| OQ-2 | What is Cactus's `.cact` conversion path from HuggingFace checkpoints? | Yes | Training pipeline design |
| OQ-3 | How does Cactus's proprietary quantization compare to TorchAO QAT for domain-specific accuracy? | No (can evaluate post-MVP) | FR-07 optimization loop |
| OQ-4 | Should C03 wrap, replace, or extend Cactus's built-in hybrid routing? | Yes | C03 design finalization |
| OQ-5 | What is the Cactus `.cact` context window limit vs ExecuTorch's 1024? | Yes | C06, UC-14, UC-16 constraints |
