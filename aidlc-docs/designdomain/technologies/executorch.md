# Technology: ExecuTorch

## Classification
- Primary: [[Model Inference Engine]] (on-device runtime)

## What it is (in this architecture)
ExecuTorch is the on-device runtime path used when the artifact pipeline is PyTorch → `.pte`. It is used for mobile/edge execution.

## When to choose it
- You have a PyTorch-centric training/export pipeline
- You want a well-defined on-device runtime model

## Evaluation notes
- ExecuTorch is not a server by default. If used for evaluation, it typically requires a harness (app or wrapper) to produce outputs.
