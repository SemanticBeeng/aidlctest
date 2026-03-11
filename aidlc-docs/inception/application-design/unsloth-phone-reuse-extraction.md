# Unsloth Phone Deployment Reuse Extraction

## Scope
This document extracts reusable components and design decisions from:
- Unsloth docs: deploy LLMs on phone
- Referenced Qwen3 (0.6B) phone deployment notebook

Target reuse context: hybrid iOS + server shopping-planning assistant with on-device default and server fallback.

## Reusable Components

### R01 Training/Adaptation Pipeline Component
- **What to reuse**: QAT-based adaptation flow using `qat_scheme = "phone-deployment"` (internally aligned with INT8-activation/INT4-weight simulation patterns).
- **Why**: Better on-device quality/size tradeoff versus naive post-training quantization.
- **Where it fits**: Pre-deployment model preparation pipeline, feeding mobile-ready artifacts.

### R02 Export Toolchain Component
- **What to reuse**: Two-step export path:
  1. `save_pretrained_torchao`
  2. ExecuTorch conversion + `.pte` export
- **Why**: Produces runtime-compatible artifact (`.pte`) for mobile ExecuTorch-based apps.
- **Where it fits**: Build/release pipeline for on-device model artifacts.

### R03 On-Device Runtime Container Component
- **What to reuse**: ExecuTorch app/runtime integration and model loading of `.pte` + tokenizer artifacts.
- **Why**: Proven deployment path for iOS/Android with CPU backends and kv-cache support.
- **Where it fits**: Device-side inference adapter implementation.

### R04 Model Asset Provisioning Component
- **What to reuse**: File-based model/tokenizer delivery pattern (simulator/phone file placement and selection).
- **Why**: Decouples app binary from large model asset lifecycle and supports iterative swaps.
- **Where it fits**: Mobile asset manager and environment-specific deployment scripts.

### R05 Device Compatibility Gate Component
- **What to reuse**: Platform setup constraints (Xcode/signing/memory capability on iOS; Java17/SDK/NDK on Android).
- **Why**: Prevents non-functional deployment failures from environment drift.
- **Where it fits**: CI preflight checks and developer setup automation.

### R06 Runtime Backend Configuration Component
- **What to reuse**: Export/runtime flags and partitioners (kv-cache mode, xnnpack-focused path, max lengths).
- **Why**: Performance and memory behavior on phones is highly sensitive to runtime config.
- **Where it fits**: Inference runtime profile registry for device classes.

### R07 Model Profile Registry Component
- **What to reuse**: Explicit model profile tuple:
  - model id/version
  - tokenizer version
  - export config hash
  - context/token limits
  - expected artifact size
- **Why**: Enables deterministic rollout and debugging of routing/quality regressions.
- **Where it fits**: Shared metadata service consumed by routing and telemetry modules.

## Reusable Design Decisions

### D01 Keep On-Device Models Small-First
- Start with Qwen3-0.6B class artifact for broad device viability; scale up by capability tiers later.

### D02 Separate Model Build from App Build
- Treat model as external deployable asset (`.pte` + tokenizer), versioned independently from app binary.

### D03 Route by Capability + Confidence + Context Signals
- Keep existing architecture decision: on-device default, server fallback.
- Add explicit policy inputs from runtime constraints (context length limits, load latency, memory pressure).

### D04 Use Explicit Context/Sequence Limits per Profile
- Export config includes fixed max context/sequence lengths; enforce these limits in request planner before inference.

### D05 Make Telemetry First-Class for Device Inference
- Capture route choice, load success/fail, model profile id, tokens/sec, first-token latency, and memory warnings.

### D06 Preserve Tokenizer/Model Pair Integrity
- Always load tokenizer and model as a validated pair (same profile/version) to avoid silent quality failure.

### D07 Optimize for Operational Portability
- Keep iOS and Android deployment scripts separate but normalize artifact naming and metadata schema.

### D08 Design for Progressive Hardening
- Current project keeps security extension disabled (MVP), but deployment decisions should stay compatible with future confidential server runtime controls.

## Mapping to Current Application Components
- **C02 On-Device Inference Adapter** <- R03, R06
- **C03 Routing Policy Engine** <- D03, D04
- **C04 Server Inference Gateway** <- D08 compatibility constraints
- **C05 Memory & Context Store** <- D04 context-boundary coordination
- **C07 Data Sufficiency Assessor** <- D03 policy support signals
- **C09 Evaluation & Telemetry Collector** <- D05, R07
- **New build-time concern**: R01 + R02 should be represented as model-release pipeline responsibilities (outside runtime app components)

## Recommended Additions to Upcoming Stages

### For Units Generation
- Add a dedicated unit: `Model Preparation & Phone Artifact Pipeline`.
- Add a dedicated unit: `Mobile Asset Provisioning & Profile Management`.

### For Functional Design
- Define policy formulas for fallback using:
  - confidence threshold
  - context length guard
  - model profile capability
  - runtime memory pressure signal

### For NFR Requirements/Design
- Add device metrics targets:
  - first-token latency budget per profile
  - steady-state tokens/sec floor
  - model load success SLO

## Caveats
- Notebook snippets indicate operational patterns, not strict production architecture standards.
- Exact throughput numbers vary significantly by device class and runtime build settings.
- Export/runtime flags must be pinned per model profile and validated in CI.
