# Dev Container Design — Criteria and Solution

Design rationale for the dev container environment used to run Qwen3-0.6B
QAT evaluations on cloud GPU providers (RunPod).

---

## 1. Design Criteria

### 1.1 Workspace Purity

**Constraint**: No build byproducts may exist in the project workspace —
not on the host filesystem, and not inside the container's `/workspace`
bind mount.

**Byproducts covered**:
- Python virtual environment (uv-managed venv)
- pip download cache
- `__pycache__` bytecode files (all packages)
- Tool caches: pytest, ruff, mypy

**Rationale**: The project workspace is a git clone. Build artifacts are
large (4+ GB for PyTorch alone), machine-specific, and must not appear in
`git status` or be accidentally committed.

### 1.2 Volume Portability

**Constraint**: All persistent state must live on Docker volumes (not host
bind mounts) so it can be transferred to cloud GPU providers.

**Rationale**: RunPod network volumes can be pre-populated and attached to
disposable pods. A host bind mount like `~/appdata/tmp/builds/...` only
works on a specific local machine and cannot be synced to a cloud pod.
Named Docker volumes can be exported, transferred, or recreated from the
same setup script.

### 1.3 Pod Disposability

**Constraint**: Pods are ephemeral. Destroying and recreating a pod must
not lose installed dependencies, downloaded datasets, or evaluation
results.

**Rationale**: GPU pods cost $0.20–$1.00+/hr. Users stop/destroy pods
between eval runs. All state that survives pod lifecycle must be on
persistent volumes.

### 1.4 Idempotent Setup

**Constraint**: The post-create script (`setup.sh`) must be safe to re-run
on every container start without redundant work.

**Rationale**: Dev containers run `postCreateCommand` on first build. But
pods restart, volumes get reattached, and users re-open containers. The
script must detect existing state (marker files, cached directories) and
skip completed steps.

### 1.5 Single Configuration for Local and Cloud

**Constraint**: The same `devcontainer.json` must work for both local
Docker (development/debugging) and RunPod (GPU evaluation).

**Rationale**: Developers test container configuration locally before
deploying to RunPod. The only difference should be the volume backing
(local Docker volume vs. RunPod network volume) — not the container
config itself.

### 1.6 Non-Root Execution

**Constraint**: The container must run as a non-root user (`vscode`,
UID 1000) for VS Code Dev Containers compatibility.

**Rationale**: RunPod images default to root. VS Code Dev Containers
expect a non-root `remoteUser`. The Dockerfile creates the user and
grants passwordless sudo for operations that need elevated privileges
(e.g., `chown` on volume mount points).

---

## 2. Solution Architecture

### 2.1 Volume Layout

Two named Docker volumes separate concerns:

| Volume | Mount Point | Docker Name | RunPod Name | Size | Contents |
|--------|-------------|-------------|-------------|------|----------|
| Build cache | `/buildcache` | `eval-buildcache` | `eval-buildcache` | 20 GB | uv venv, download cache, `__pycache__`, tool caches |
| Data | `/data` | `eval-datasets` | `eval-datasets` | 50 GB | HuggingFace datasets, trained models, eval results |

**Why two volumes instead of one**: Build cache is disposable (can be
fully rebuilt from `uv sync` + `setup.sh`). Data is not — trained
models and eval results represent hours of GPU time. Separating them
allows deleting/recreating the build cache without risking data loss.

#### Volume identity across environments

The Docker name and RunPod name are intentionally the same
(`eval-buildcache`, `eval-datasets`) but they are **different volumes**
created and managed by different systems. They never coexist — only one
is active depending on where the container runs.

| Environment | Who creates the volume | Backing storage | Lifecycle |
|---|---|---|---|
| **Local Docker** | Docker Engine, on first `docker compose up` or dev container open | Docker-managed directory on host (e.g. `/var/lib/docker/volumes/eval-buildcache/`) | Survives container rebuilds; deleted by `docker volume rm eval-buildcache` |
| **RunPod** | Operator, via RunPod Dashboard → Storage → Network Volumes | RunPod network-attached block storage in the selected data center | Persists across pod stop/start/destroy; deleted via Dashboard |

**How to tell which is in use**: Inside the container, `/buildcache`
always looks the same regardless of backing. To verify:

```bash
# On local Docker
docker volume inspect eval-buildcache   # shows Mountpoint on host

# On RunPod
df -h /buildcache                       # shows network volume device
```

**The workflow**:

1. **Local development** — `eval-buildcache` is a local Docker volume.
   Opening the dev container creates it if missing. `setup.sh` populates
   `venv/` and `pkg-cache/`. This volume cannot be transferred to RunPod.

2. **RunPod deployment** — The operator creates a RunPod network volume
   also named `eval-buildcache` (20 GB) in the target data center. On
   first pod launch, it is empty. `setup.sh` runs `uv sync` which
   populates `venv/` and `pkg-cache/` from scratch (~4 GB download).
   Subsequent pod launches reuse the populated volume (marker file
   `/buildcache/.uv-installed` skips reinstall).

3. **No sync between them** — The local and RunPod volumes are
   independent. Rebuilding locally does not affect RunPod, and vice
   versa. Both install identical packages because `uv sync --locked`
   reads the committed `uv.lock`, which pins every transitive
   dependency with exact versions and hashes. The inputs are
   `pyproject.toml` (direct deps) + `uv.lock` (resolved graph) +
   `setup.sh` (orchestration). As long as the same git commit is
   checked out, both environments are byte-for-byte identical.

#### Lockfile workflow

`uv.lock` is committed to the repo alongside `pyproject.toml`.

| Action | Command | When |
|---|---|---|
| Generate or update lockfile | `uv lock` | After editing `pyproject.toml` |
| Install from lockfile (no resolution) | `uv sync --locked` | In `setup.sh`, CI, fresh pods |
| Add a dependency | `uv add <pkg>` | Updates both `pyproject.toml` and `uv.lock` |
| Add a dev dependency | `uv add --group dev <pkg>` | Same, into `[dependency-groups] dev` |

`--locked` makes `uv sync` fail fast if the lockfile is out of date
relative to `pyproject.toml`, preventing silent version drift between
environments.

The matching names are a convention for readability — so that
`devcontainer.json`, `RUNPOD_EVAL_WORKFLOW.md`, and Dashboard entries
all reference the same logical name, even though the physical volumes
are distinct.

### 2.2 Cache Redirection

Every tool that writes cache files is redirected to `/buildcache/` via
environment variables or tool configuration:

| Tool | Mechanism | Target |
|------|-----------|--------|
| uv (venv) | `VENV_DIR` → mapped to `UV_PROJECT_ENVIRONMENT` in setup.sh | `/buildcache/venv` |
| uv (cache) | `PKG_CACHE_DIR` → mapped to `UV_CACHE_DIR` in setup.sh | `/buildcache/pkg-cache` |
| Python bytecode | `PYTHONPYCACHEPREFIX` env var | `/buildcache/pycache` |
| pytest | `[tool.pytest.ini_options] cache_dir` in pyproject.toml | `/buildcache/pytest` |
| ruff | `[tool.ruff] cache-dir` in pyproject.toml | `/buildcache/ruff` |
| mypy | `[tool.mypy] cache_dir` in pyproject.toml | `/buildcache/mypy` |
| HuggingFace | `HF_HOME` env var | `/data/huggingface` |
| Transformers | `TRANSFORMERS_CACHE` env var | `/data/huggingface/hub` |

Environment variables are set in `devcontainer.json` → `containerEnv` so
they apply to all shells and processes inside the container. Tool-specific
config in `pyproject.toml` provides a fallback for contexts where env vars
may not be loaded.

### 2.3 Container Image

```
Base: runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

Layers added:
  1. System packages: git, curl, openssh-server, sudo
  2. uv: static binary copied from official image
  3. Non-root user: vscode (UID 1000), passwordless sudo
  4. Mount point: /buildcache directory (owned by vscode)
  5. SSH config: key-only auth for VS Code Remote
```

**Why RunPod's base image**: It bundles PyTorch + CUDA + cuDNN in a
tested combination. Building from `nvidia/cuda` and installing PyTorch
manually adds complexity and risks version mismatches.

### 2.4 Setup Script (setup.sh)

The post-create script runs in 7 ordered steps, each idempotent:

1. **Env var mapping** — exports tool-specific vars from generic ones
   (`VENV_DIR` → `UV_PROJECT_ENVIRONMENT`, `PKG_CACHE_DIR` → `UV_CACHE_DIR`)
2. **Volume permissions** — `chown` mount points to the `vscode` user
   (RunPod network volumes may be owned by root initially)
3. **Subdirectory creation** — create all `/buildcache/*` subdirectories
4. **uv sync** — installs dependencies to
   `/buildcache/venv/`; uses marker file
   `/buildcache/.uv-installed` to skip on subsequent runs
5. **Dataset download** — pre-caches OpenMathReasoning-mini and
   FineTome-100k to `/data/huggingface/hub/`; checks for existing
   cache directories before downloading
5. **GPU verification** — prints GPU name and VRAM via `torch.cuda`
6. **Environment check** — warns if `OPENAI_API_KEY` is not set, checks
   for trained model at `/workspace/phone_model` or `/data/phone_model`

### 2.5 VS Code Integration

```jsonc
// devcontainer.json settings
{
  "python.defaultInterpreterPath": "/buildcache/venv/bin/python",
  "extensions": ["ms-python.python", "ms-python.vscode-pylance", "charliermarsh.ruff", "ms-toolsai.jupyter"]
}
```

The interpreter path points into the volume-backed venv so Pylance,
test discovery, and terminal activation all use the correct environment
without manual configuration.

---

## 3. Design Decisions and Trade-offs

### Named volumes vs. bind mounts

| | Named volumes (chosen) | Bind mounts (rejected) |
|---|---|---|
| Cloud sync | Can be backed by RunPod network volumes | Only works on local host |
| Portability | Works on any Docker host | Requires specific host path |
| Performance | Docker-managed, overlay-optimized | OS filesystem, may be slower on macOS |
| Visibility | Opaque to host (`docker volume ls`) | Visible in host filesystem |
| Cleanup | `docker volume rm` | `rm -rf` on host |

**Decision**: Named volumes chosen because the primary deployment target
(RunPod) uses network volumes that map directly to Docker named volumes.

### Two volumes vs. one

A single volume would simplify configuration but conflates disposable
build artifacts with irreplaceable data. With two volumes, a corrupted
venv can be fixed by deleting `eval-buildcache` and re-running `setup.sh`
without touching datasets or eval results.

### uv vs. Poetry vs. pip + venv

uv is a Rust-based Python package manager (from Astral, the ruff team).
It replaces Poetry with faster resolution and installs — cold installs
that take minutes with Poetry complete in seconds with uv. Key advantages:

- **Speed**: 10–100× faster than pip/Poetry for resolution and install
- **Single binary**: Copied from a multi-stage Docker image (`COPY --from`),
  no installer script or runtime dependencies
- **PEP 621 native**: Uses standard `[project]` table in pyproject.toml
  instead of Poetry's proprietary `[tool.poetry]` format
- **`UV_PROJECT_ENVIRONMENT`**: Redirects the venv to the path set by `VENV_DIR`
- **`UV_CACHE_DIR`**: Controls all download/build caching, set from `PKG_CACHE_DIR`
- **Deterministic lockfile**: `uv.lock` (cross-platform, hash-verified)

### `PYTHONPYCACHEPREFIX` vs. `PYTHONDONTWRITEBYTECODE`

`PYTHONPYCACHEPREFIX` redirects bytecode to the build cache volume,
preserving import performance. `PYTHONDONTWRITEBYTECODE=1` would
prevent `.pyc` generation entirely, slowing every import. The redirect
approach keeps performance while maintaining workspace purity.

---

## 4. File Inventory

| File | Role | Key responsibility |
|------|------|--------------------|
| `.devcontainer/Dockerfile` | Image definition | Base image, uv, non-root user, SSH |
| `.devcontainer/devcontainer.json` | Container config | Volumes, env vars, GPU passthrough, extensions |
| `.devcontainer/setup.sh` | Post-create script | Idempotent dependency install, dataset caching, GPU check |
| `pyproject.toml` | Project/tool config | Dependencies (PEP 621), cache dir overrides for pytest/ruff/mypy |
| `tests/conftest.py` | Test fixtures | `QAT_MODEL_DIR` env var, session-scoped model loading |
| `training/RUNPOD_EVAL_WORKFLOW.md` | Workflow guide | Step-by-step RunPod deployment and evaluation procedure |

---

## 5. Cost Summary

| Resource | Cost |
|----------|------|
| `eval-buildcache` network volume (20 GB idle) | ~$1.40/month |
| `eval-datasets` network volume (50 GB idle) | ~$3.50/month |
| T4 GPU pod (per eval run, ~15 min) | ~$0.05–$0.10 |
| OpenAI API (LLM-as-judge metrics, ~210 tests) | ~$2–$5 per run |
