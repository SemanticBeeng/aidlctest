# Requirements Document

## Intent Analysis Summary
- **User Request**: Design and implement a hybrid LLM inference architecture and application where inference runs on mobile device and server.
- **Request Type**: New Project
- **Scope Estimate**: Multiple Components (mobile client, on-device inference runtime, server inference layer, routing/orchestration)
- **Complexity Estimate**: Complex
- **Domain Focus**: Shopping planning assistant

## Product Vision
Build a domain-specific shopping planning assistant that supports hybrid inference:
- on-device inference on iOS using Cactus inference engine and Qwen3-family models,
- server-side inference using `llm-d` as primary backend,
- intelligent routing with on-device default and server fallback,
- privacy-aware behavior with encrypted server communication and auditable server processing,
- future-ready confidential computing posture via Edgeless Systems Contrast-aligned server design.

## Functional Requirements

### FR-01 Mobile Platform Support
- First release must support iOS.

### FR-02 Core Use Case
- The application must provide a domain-specific shopping planning assistant experience.
- The assistant should support shopping intent interpretation and plan generation workflows.

### FR-03 Hybrid Inference Architecture
- The system must support both on-device and server inference execution paths.
- A unified application API must abstract the inference path from product UX flows.

### FR-04 On-Device Inference
- On-device inference must use Cactus inference engine in v1.
- On-device model family starts with Qwen3.
- Integration mode is a native mobile wrapper around Cactus (no alternative engine in v1 path).

### FR-05 Inference Routing Policy
- Routing policy must be: on-device by default, server fallback when local capability/confidence is insufficient.
- Fallback conditions must be explicit and observable (e.g., capability limits, quality thresholds, runtime constraints).

### FR-06 Server Inference Backend
- Primary v1 server backend must be llm-d`.
- `chutes.ai` may be considered in future iterations but is not the v1 baseline target.

### FR-07 Model Optimization and Selection Process
- On-device model size/quantization must be selected iteratively using:
  - QAT-driven tuning decisions,
  - server-side evaluation loops (DeepEval or equivalent),
  - device performance benchmarking.
- Final model packaging strategy is determined by this evaluation loop rather than fixed upfront size.

### FR-08 Privacy and Data Handling
- Server usage is allowed with encryption and audit logging.
- Prompt/response flows sent to server must be transmitted over encrypted channels.
- Server-side inference requests and responses must be auditable.

### FR-09 Confidential AI Design Direction
- Although full security extension enforcement is disabled for MVP, server architecture must be designed with a confidential AI direction using Edgeless Systems Contrast principles as a design constraint for future hardening.

## Non-Functional Requirements

### NFR-01 Latency
- First-token latency target is best-effort for v1 (no strict hard SLA).

### NFR-02 Security/Posture Level
- Delivery target is MVP/prototype hardening level.
- Security extension rules are explicitly disabled for current phase as blocking constraints.

### NFR-03 Observability Minimum
- Routing decisions and fallback events must be captured for analysis.
- Server-side processing logs must support auditability requirements in FR-08.

### NFR-04 Maintainability
- Inference provider integration should isolate backend-specific logic behind adapter interfaces to simplify later addition of alternate backends.

### NFR-05 Performance Validation
- Mobile performance acceptance must be based on benchmark results on target iOS devices.
- Server-side model quality/performance must be validated through repeatable evaluation runs.

## User Scenarios
- User asks for shopping planning help; app attempts on-device response first.
- If on-device path cannot meet quality/capability thresholds, request is routed to server `llm-d` backend.
- User receives a response regardless of route, while system captures route and audit metadata.

## Functional Use Cases (Supported by Hybrid Architecture)

### UC-01 Conversational Shopping List Generation
- User describes shopping goals (e.g., weekly groceries, event shopping).
- On-device Cactus + Qwen3 path produces a structured shopping list with categories and quantities.

### UC-02 Budget-Aware Basket Optimization
- User provides a budget ceiling and preference constraints.
- System computes an initial plan on-device, then falls back to server when optimization complexity exceeds device confidence/capability.

### UC-03 Dietary and Preference-Constrained Planning
- User requests plans filtered by dietary rules (e.g., vegan, low-sodium, allergen exclusions).
- Routing policy keeps simple constraint handling on-device and escalates nuanced multi-constraint reasoning to server when needed.

### UC-04 Store-Specific Plan Adaptation
- User asks to tailor shopping output for a selected store or catalog context.
- On-device handles base adaptation; server fallback is used for deeper ranking/suggestion quality improvements.

### UC-05 Offline Shopping Assistant Mode
- User interacts in low/no connectivity conditions.
- App continues responding using on-device inference as primary mode, preserving core planning functionality without server dependence.

### UC-06 Multi-Turn Plan Refinement
- User iteratively refines a shopping plan through follow-up prompts (replace items, adjust quantities, reprioritize).
- Architecture supports seamless transition between on-device and server inference while maintaining a consistent multi-turn conversation experience.

### UC-07 Explainability and Rationale Summaries
- User asks why specific products/quantities were recommended.
- System returns concise rationale, generated on-device when feasible and via server fallback for higher-complexity explanation synthesis.

### UC-08 Preference Memory Across Sessions
- User teaches long-term preferences over multiple chats (favorite brands, disliked ingredients, price sensitivity).
- AI memory stores and reuses these preferences in future sessions to avoid repeated user re-entry and improve recommendation relevance.

### UC-09 Pantry and Purchase History Continuity
- User updates pantry state and marks purchased items over time in multi-turn conversations.
- Memory tracks inventory and recent purchases so subsequent plans avoid duplicates and prioritize depleted items.

### UC-10 Recurring Shopping Routine Builder
- User iteratively defines weekly/biweekly shopping routines in several conversation turns.
- Memory captures recurring cadence and category templates, enabling one-shot generation of future routine-specific plans.

### UC-11 Event Planning Thread Persistence
- User plans for events (party, travel, holiday) over several days with evolving constraints.
- Memory preserves event context, guest counts, and prior decisions so the assistant can continue planning without restarting context each session.

### UC-12 Goal-Driven Budget Coaching
- User sets monthly budget goals and revisits them across multiple interactions.
- Memory retains prior budget decisions, substitutions, and spend patterns to provide longitudinal coaching and adaptive optimization suggestions.

### UC-13 Personalized Clarification Reduction
- User repeatedly responds to preference-clarification prompts in early sessions.
- Memory learns stable user traits and reduces repetitive follow-up questions in later multi-turn conversations, improving UX efficiency.

### UC-14 Context-Rot Signal Detection in Long Conversations
- User runs extended multi-turn planning sessions over many edits and topic shifts.
- Assistant detects context-rot signals (contradictions, stale assumptions, low-reference grounding) and flags confidence degradation before giving final recommendations.

### UC-15 Memory Freshness Validation and Repair
- User asks for updated plans after lifestyle or preference changes.
- System validates memory freshness (last-confirmed timestamps and conflict checks), prompts selective reconfirmation, and repairs outdated memory slots instead of silently using stale context.

### UC-16 Context Integrity Checkpointing
- During iterative planning, user reaches key milestones (budget finalized, dietary constraints locked, store selected).
- Assistant creates checkpoint summaries and reuses them as canonical context anchors to prevent drift and recover from context rot in later turns.

### UC-17 Data Sufficiency Readiness Indicator
- User expects personalized planning quality but has provided limited profile/history data.
- Assistant computes and displays a readiness status (e.g., insufficient/partial/sufficient) showing whether available user data is enough for desired planning support quality.

### UC-18 Guided Data Completion for Better Personalization
- When readiness is insufficient, assistant asks targeted multi-turn questions (constraints, pantry baseline, budget bands, recurring items) to close the minimum data gap.
- System shows progress toward sufficiency so users know when data quality has reached reliable-support thresholds.

### UC-19 Fine-Tuning Recommendation Trigger
- User requests higher consistency/accuracy than current memory+prompt adaptation can provide.
- Assistant identifies persistent failure patterns from evaluations and interaction logs, then recommends model fine-tuning only when thresholds indicate that additional user data alone is no longer sufficient.

## Constraints and Assumptions
- Cactus engine availability and integration on iOS is assumed for v1.
- Qwen3 model variants used must be compatible with Cactus runtime constraints.
- MVP timeline prioritizes functional hybrid flow over enterprise security completion.

## Out of Scope (Current Stage)
- Enterprise-grade security control enforcement as blocking gates.
- Full multi-provider production orchestration for server inference.
- Android support in initial release.

## Requirements Summary
The v1 product is an iOS shopping planning assistant using hybrid Qwen3 inference with Cactus on-device default execution and `llm-d` server fallback, delivered as MVP with encrypted/auditable server interactions and confidential AI-aligned architecture direction.
