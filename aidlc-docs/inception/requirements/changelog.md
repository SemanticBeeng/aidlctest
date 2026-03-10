# Requirements Changelog

## Purpose
Track requirement change requests and the exact functional use case IDs introduced in response.

## Entries

### Entry 001
- **Timestamp**: 2026-03-10T22:12:48Z
- **User Request**: "Request Changes propose 7 functional use cases for the given area of functionlity that can be supported by this architecture"
- **Change Description**: Added baseline architecture-aligned functional use cases for shopping planning assistant workflows on hybrid inference.
- **Introduced Use Case IDs**: UC-01, UC-02, UC-03, UC-04, UC-05, UC-06, UC-07
- **Affected File**: `aidlc-docs/inception/requirements/requirements.md`

### Entry 002
- **Timestamp**: 2026-03-10T22:17:42Z
- **User Request**: "Request Changes: add 5+ more use cases using multi-turn conversations and that justify using AI memory"
- **Change Description**: Added multi-turn, memory-centric use cases focusing on preference continuity, state retention, and personalized planning over repeated sessions.
- **Introduced Use Case IDs**: UC-08, UC-09, UC-10, UC-11, UC-12, UC-13
- **Affected File**: `aidlc-docs/inception/requirements/requirements.md`

### Entry 003
- **Timestamp**: 2026-03-10T22:26:03Z
- **User Request**: "Request Changes: add 5+ use cases that detect and handle context rot. Include functionality that shows when user data is enough to achieve the desired support from the AI planning assistant and vs when model needs fine tuning."
- **Change Description**: Added context-rot detection/mitigation and readiness decision use cases, including data sufficiency indicators and fine-tuning recommendation triggers.
- **Introduced Use Case IDs**: UC-14, UC-15, UC-16, UC-17, UC-18, UC-19
- **Affected File**: `aidlc-docs/inception/requirements/requirements.md`

## Summary Matrix
| Change Entry | Topic | Use Cases Added |
|---|---|---|
| 001 | Baseline hybrid shopping assistant flows | UC-01 to UC-07 |
| 002 | Multi-turn + AI memory value | UC-08 to UC-13 |
| 003 | Context rot + data sufficiency vs fine-tuning | UC-14 to UC-19 |
