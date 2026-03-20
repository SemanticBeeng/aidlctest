# Technology: Cactus

## Classification
- Primary: [[Model Inference Engine]] (on-device runtime)
- Also provides: SDK-level APIs that resemble a [[Model Inference Server]] interface (OpenAI-compatible semantics), but used on-device

## What it is (in this architecture)
Cactus is the default on-device inference engine for the MVP. It uses proprietary `.cact` artifacts and is optimized for constrained devices.

## When to choose it
- Offline + memory-constrained mobile inference is the priority
- You want a mobile-first engine with tight footprint targets

## Evaluation notes
- On-device evaluation requires an adapter/harness. The server-side DeepEval MVP focuses on server inference first.
