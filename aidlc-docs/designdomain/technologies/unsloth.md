# Technology: Unsloth

## Classification
- Primary: model workflow (training/export)
- In MVP0 (Decision D-EVAL-SUT-02): functions as an in-process [[Model Inference Engine]] for Qwen3 evaluation

## What it is (in this architecture)
Unsloth provides an efficient workflow to train, run, and export models. In this repo’s MVP0 evaluation implementation, Unsloth is also the in-process runtime used to generate Qwen3 outputs.

## Why it matters for MVP evaluation
- Enables fast iteration without standing up a server
- Keeps evaluation failures attributable to model/prompt/data rather than server configuration

## Transition
When evaluation must measure system performance/concurrency realism, move to a [[Model Inference Server]] (default: vLLM) per D-SERVER-01.
