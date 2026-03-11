# Services

## S01 Planning Orchestration Service
- **Responsibilities**:
  - Coordinate prompt processing across memory loading, route decision, inference execution, and response assembly
  - Manage multi-turn continuity and refinement loops
- **Collaborators**: C03, C02, C04, C05, C09

## S02 Memory Lifecycle Service
- **Responsibilities**:
  - Handle read/write lifecycle for user memory and context checkpoints
  - Trigger freshness validation and memory repair workflows
- **Collaborators**: C05, C06, C09

## S03 Context Reliability Service
- **Responsibilities**:
  - Assess context rot risk and choose recovery patterns
  - Coordinate checkpoint restore and reconfirmation prompts
- **Collaborators**: C06, C05, C03

## S04 Readiness & Guidance Service
- **Responsibilities**:
  - Compute data sufficiency state
  - Produce targeted guided completion actions
- **Collaborators**: C07, C05, C01

## S05 Fine-Tuning Recommendation Service
- **Responsibilities**:
  - Evaluate repeat failure windows against policy thresholds
  - Emit explainable fine-tuning recommendation events
- **Collaborators**: C08, C09, C07

## S06 Policy Evaluation Service
- **Responsibilities**:
  - Parse and evaluate policy DSL rules for routing, rot, readiness, and fine-tuning
  - Provide policy decision traces for auditability
- **Collaborators**: C03, C06, C07, C08, C09

## S07 Explainability Service
- **Responsibilities**:
  - Build concise user-facing rationale for recommendations and route decisions
  - Ensure rationale references constraints and confidence indicators
- **Collaborators**: C02, C04, C03, C05

## Service Orchestration Pattern
- Request flow: `S01 -> (S02/S03/S04/S06) -> C03 route -> (C02 or C04) -> S07 -> response`
- Post-response telemetry: `S01 -> C09`
- Background signal flow: `C09 -> S05`
