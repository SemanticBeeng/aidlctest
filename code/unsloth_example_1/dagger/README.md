# Dagger Setup Pipeline (Unsloth Eval Runner)

The authoritative Dagger **components + logical flow** documentation lives in:
[training/RUNPOD_EVAL_WORKFLOW.md](../training/RUNPOD_EVAL_WORKFLOW.md) under **Setup (Dagger-Oriented Logical Flow)**.

## Usage

From the repo root:

```bash
cd code/unsloth_example_1/dagger

# End-to-end: deps + datasets
# (This returns a container; use --help in your Dagger CLI for output options.)
dagger call setup

# Just dependencies

dagger call sync-deps

# Just dataset prefetch

dagger call prefetch-datasets

# Print judge config assumptions (from your local environment)
dagger call config-report
```

If you run Dagger locally, ensure your judge endpoint environment variables are set
before calling `config-report`.
