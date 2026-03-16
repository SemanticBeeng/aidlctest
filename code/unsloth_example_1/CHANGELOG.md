# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased] — 2026-03-13

### Changed

- **Package manager**: Replaced Poetry with **uv** (Astral, Rust-based)
  - Dockerfile: removed Poetry installer, added `COPY --from=ghcr.io/astral-sh/uv:latest`
  - devcontainer.json: `POETRY_VIRTUALENVS_PATH` → `VENV_DIR`,
    `PIP_CACHE_DIR` → `PKG_CACHE_DIR`, interpreter path → `/buildcache/venv/bin/python`
  - setup.sh maps generic vars to tool-specific ones:
    `VENV_DIR` → `UV_PROJECT_ENVIRONMENT`, `PKG_CACHE_DIR` → `UV_CACHE_DIR`
  - setup.sh: `poetry install` → `uv sync --locked`, `poetry run` → `uv run`,
    marker file `.poetry-installed` → `.uv-installed`
  - `uv.lock` to be committed for deterministic cross-environment installs;
    `--locked` flag ensures `setup.sh` fails fast if lockfile is stale
  - pyproject.toml: `[tool.poetry]` → PEP 621 `[project]` table,
    `[tool.poetry.group.dev.dependencies]` → `[dependency-groups]`,
    build backend `poetry-core` → `hatchling`
  - All docs (EVALUATIONS.md, README.md, RUNPOD_EVAL_WORKFLOW.md,
    DEVCONTAINER_DESIGN.md): `poetry run` → `uv run`, `poetry install` → `uv sync`
  - `/buildcache/virtualenvs/` → `/buildcache/venv/`,
    `/buildcache/pip-cache/` → `/buildcache/pkg-cache/`

---

## [Unreleased] — 2026-03-12

### Added

- **Dev container environment** for running evaluations on RunPod GPU pods
  - `.devcontainer/Dockerfile` — PyTorch 2.4.0 + CUDA 12.4.1 + Poetry + SSH,
    non-root `vscode` user, pre-created `/buildcache` mount point
  - `.devcontainer/devcontainer.json` — GPU passthrough (`--gpus all`),
    two named Docker volumes (`eval-buildcache` at `/buildcache`,
    `eval-datasets` at `/data`), environment variables for all cache
    directories, VS Code extensions and Python interpreter path
  - `.devcontainer/setup.sh` — idempotent post-create script: installs Poetry
    deps to `/buildcache/virtualenvs`, downloads HuggingFace datasets to
    `/data/huggingface`, verifies GPU and env vars
- **Evaluation documentation**
  - `training/EVALUATIONS.md` — comprehensive evaluation guide covering
    architecture, 10 metrics, 5 evaluation suites, data pipeline,
    configuration reference, results interpretation, and troubleshooting
  - `training/RUNPOD_EVAL_WORKFLOW.md` — end-to-end RunPod workflow with
    architecture diagram, network volume setup, VS Code SSH connection,
    eval commands, results retrieval, and cost breakdown
  - `.devcontainer/DEVCONTAINER_DESIGN.md` — design criteria, constraints,
    and rationale for the dev container architecture
- **Evaluation test suite** — 13 parametrized test classes (~210 tests) in
  `tests/test_model_quality.py` covering:
  - Math correctness, COT format compliance, think token usage,
    answer extraction, expected answer matching
  - Chat relevancy, toxicity, bias, instruction following,
    response completeness, multi-turn coherence
  - Programmatic checks (no OpenAI API required) and LLM-as-judge metrics
- **Standalone evaluation orchestrator** (`training/evaluate_model.py`) —
  `EvalConfig` dataclass, 10 DeepEval metrics, programmatic check functions,
  multi-turn data preparation, Confident AI integration
- **Session-scoped pytest fixtures** (`tests/conftest.py`) — model loading,
  dataset sampling, output generation, multi-turn conversation support,
  `QAT_MODEL_DIR` env var override for base model evaluation

### Changed

- **Volume strategy**: `/buildcache` changed from host bind mount
  (`~/appdata/tmp/builds/...`) to a named Docker volume (`eval-buildcache`)
  so it can be synced to RunPod as a network volume
  - Removed `initializeCommand` (no host directory creation needed)
  - Updated architecture diagram and workflow docs to reflect two
    network volumes (`eval-buildcache` 20 GB + `eval-datasets` 50 GB)
- **Cache directory configuration** in `pyproject.toml` — pytest, ruff, and
  mypy caches redirected to `/buildcache/` subdirectories via tool config
  sections (`[tool.pytest.ini_options]`, `[tool.ruff]`, `[tool.mypy]`)
