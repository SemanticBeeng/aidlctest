# Application Design Consolidation

## Overview
This document consolidates application-level design artifacts for the hybrid shopping planning assistant.

## Included Artifacts
- `components.md`
- `component-methods.md`
- `services.md`
- `component-dependency.md`
- `unsloth-phone-reuse-extraction.md`

## Design Summary
- Architecture is split into client UX, routing/policy core, inference adapters, memory/context reliability modules, and telemetry/evaluation modules.
- On-device execution remains default path, with explicit server fallback through policy-driven routing.
- Memory continuity, context-rot handling, readiness signaling, and fine-tuning triggers are modeled as first-class service responsibilities.
- Kotlin-first interface contracts are used for portability and testability in later stages.

## Component Inventory Snapshot
- C01 Mobile App Client
- C02 On-Device Inference Adapter
- C03 Routing Policy Engine
- C04 Server Inference Gateway
- C05 Memory & Context Store
- C06 Context-Rot Detector
- C07 Data Sufficiency Assessor
- C08 Fine-Tuning Signal Evaluator
- C09 Evaluation & Telemetry Collector

## Service Layer Snapshot
- S01 Planning Orchestration Service
- S02 Memory Lifecycle Service
- S03 Context Reliability Service
- S04 Readiness & Guidance Service
- S05 Fine-Tuning Recommendation Service
- S06 Policy Evaluation Service
- S07 Explainability Service

## Consistency Validation
- Each critical requirement area maps to at least one component and one service.
- User-story critical paths (routing transparency, memory continuity, context-rot recovery, readiness, fine-tuning signal) are represented in interfaces and dependencies.
- Detailed business logic intentionally deferred to Functional Design stage.

## External Reuse Inputs
- Reusable phone-deployment components and design decisions extracted from Unsloth + ExecuTorch references are documented in `unsloth-phone-reuse-extraction.md`.
- These reuse inputs should be treated as constraints/guidance for Units Generation, Functional Design, and NFR stages.
