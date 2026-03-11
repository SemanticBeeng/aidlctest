# Components

## C01 Mobile App Client (iOS)
- **Purpose**: User interaction surface for shopping planning workflows.
- **Responsibilities**:
  - Capture user prompts, profile inputs, and follow-up answers
  - Render planning output, explanations, readiness state, and route transparency
  - Manage session lifecycle and local UX state
- **Interfaces**:
  - `PlanningFacade`
  - `SessionCoordinator`
  - `ReadinessPresenter`

## C02 On-Device Inference Adapter (Cactus + Qwen3)
- **Purpose**: Execute low-latency local inference.
- **Responsibilities**:
  - Run on-device prompt execution
  - Return confidence/quality signals for routing
  - Support model-pack selection outcomes from optimization process
- **Interfaces**:
  - `OnDeviceInferencePort`
  - `OnDeviceTelemetryPort`

## C03 Routing Policy Engine
- **Purpose**: Decide device vs server execution path.
- **Responsibilities**:
  - Evaluate confidence, context age, rot signals, and complexity
  - Emit routing decision and rationale
  - Enforce policy DSL thresholds
- **Interfaces**:
  - `RoutingDecisionPort`
  - `PolicyEvaluationPort`

## C04 Server Inference Gateway (`llm-d` primary)
- **Purpose**: Execute server-side inference and return normalized responses.
- **Responsibilities**:
  - Adapt requests/responses to primary backend
  - Preserve conversation continuity and metadata
  - Handle fallback-safe errors for client experience
- **Interfaces**:
  - `ServerInferencePort`
  - `BackendAdapterPort`

## C05 Memory & Context Store
- **Purpose**: Persist and retrieve user preference/context artifacts.
- **Responsibilities**:
  - Manage preference memory, pantry state, and event threads
  - Track freshness timestamps and conflict markers
  - Store checkpoint summaries for drift recovery
- **Interfaces**:
  - `MemoryReadPort`
  - `MemoryWritePort`
  - `CheckpointPort`

## C06 Context-Rot Detector
- **Purpose**: Detect context drift and degraded reliability.
- **Responsibilities**:
  - Aggregate contradiction/staleness/reference-grounding signals
  - Trigger recovery actions when threshold exceeded
  - Produce rot evidence for observability
- **Interfaces**:
  - `ContextRotPort`
  - `RecoverySuggestionPort`

## C07 Data Sufficiency Assessor
- **Purpose**: Determine whether current user data is sufficient for high-quality support.
- **Responsibilities**:
  - Calculate readiness state (insufficient/partial/sufficient)
  - Identify highest-impact missing attributes
  - Feed guided completion flow
- **Interfaces**:
  - `ReadinessAssessmentPort`
  - `DataGapPort`

## C08 Fine-Tuning Signal Evaluator
- **Purpose**: Determine when model fine-tuning recommendation is warranted.
- **Responsibilities**:
  - Evaluate policy thresholds against repeated failure windows and readiness state
  - Emit recommendation signal with evidence
  - Ensure recommendation remains off for insufficient-data states
- **Interfaces**:
  - `FineTuningSignalPort`

## C09 Evaluation & Telemetry Collector
- **Purpose**: Collect route outcomes, quality metrics, and policy evidence.
- **Responsibilities**:
  - Persist route decisions and policy checks
  - Track evaluation metrics for reliability and consistency
  - Provide traceable audit data for explainability
- **Interfaces**:
  - `TelemetryWritePort`
  - `EvaluationMetricsPort`
