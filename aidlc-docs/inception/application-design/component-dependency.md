# Component Dependency

## Dependency Matrix
| From \ To | C01 | C02 | C03 | C04 | C05 | C06 | C07 | C08 | C09 |
|---|---|---|---|---|---|---|---|---|---|
| C01 Mobile App Client | - |  | X |  | X |  | X |  |  |
| C02 On-Device Inference Adapter |  | - |  |  |  |  |  |  | X |
| C03 Routing Policy Engine |  | X | - | X | X | X | X |  | X |
| C04 Server Inference Gateway |  |  |  | - | X |  |  |  | X |
| C05 Memory & Context Store |  |  |  |  | - | X | X |  | X |
| C06 Context-Rot Detector |  |  | X |  | X | - |  |  | X |
| C07 Data Sufficiency Assessor |  |  | X |  | X |  | - | X | X |
| C08 Fine-Tuning Signal Evaluator |  |  |  |  | X | X | X | - | X |
| C09 Evaluation & Telemetry Collector |  |  |  |  |  |  |  |  | - |

## Communication Patterns
- **Synchronous**:
  - C01 -> C03 for immediate route decision and transparency
  - C03 -> C02/C04 for inference execution path
  - C03/C06/C07/C08 -> C05 for memory/context reads
- **Asynchronous/Event-driven**:
  - C02/C03/C04/C06/C07/C08 -> C09 for telemetry events
  - C09 -> C08 for evaluation-window aggregation inputs

## Data Flow Summary
1. User prompt enters C01.
2. C01 loads memory context (C05) and requests route decision (C03).
3. C03 evaluates policy signals (C06/C07) and dispatches to C02 or C04.
4. Inference result returns to C01 with explanation metadata.
5. Telemetry and policy evidence are written to C09.
6. C08 periodically evaluates fine-tuning recommendation based on C09 windows and readiness state.

## Dependency Constraints
- C01 must never call C04 directly; all routing passes through C03.
- C08 recommendation signal must depend on C07 readiness state and C09 evidence window.
- C06 recovery actions must reference checkpoint availability in C05.
