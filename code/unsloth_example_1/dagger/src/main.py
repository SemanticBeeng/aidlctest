import os

import dagger
from dagger import function, object_type


@object_type
class UnslothEvalSetup:
    """Dagger-based setup pipeline for the Unsloth + DeepEval RunPod workflow.

    This models the setup as explicit components:
    - Image build (from the devcontainer Dockerfile)
    - Dependency sync (uv) with cache volumes
    - Dataset prefetch (HuggingFace datasets) with cache volumes
    - Environment/config checks (judge endpoint variables)

    Notes:
    - GPU validation is not reliably available inside Dagger runners. Treat GPU
      checks as informational only.
    - This pipeline is designed to be run from a machine with the Dagger CLI.
    """

    @function
    def eval_runner_image(
        self,
        workdir: str = "/workspace",
    ) -> dagger.Container:
        """Build the eval-runner container image from the devcontainer Dockerfile."""

        repo = dagger.host().directory("..")
        return (
            dagger.container()
            .build(context=repo, dockerfile=".devcontainer/Dockerfile")
            .with_workdir(workdir)
        )

    @function
    def python_env(
        self,
        venv_dir: str = "/buildcache/venv",
        pkg_cache_dir: str = "/buildcache/pkg-cache",
        pycache_dir: str = "/buildcache/pycache",
    ) -> dagger.Container:
        """Create a container with uv configured to use cache volumes."""

        buildcache = dagger.cache_volume("eval-buildcache")
        data = dagger.cache_volume("eval-datasets")

        return (
            self.eval_runner_image()
            .with_mounted_cache("/buildcache", buildcache)
            .with_mounted_cache("/data", data)
            .with_env_variable("VENV_DIR", venv_dir)
            .with_env_variable("PKG_CACHE_DIR", pkg_cache_dir)
            .with_env_variable("PYTHONPYCACHEPREFIX", pycache_dir)
            .with_env_variable("UV_PROJECT_ENVIRONMENT", venv_dir)
            .with_env_variable("UV_CACHE_DIR", pkg_cache_dir)
        )

    @function
    def sync_deps(self) -> dagger.Container:
        """Sync Python dependencies (uv). Uses uv.lock if present, else falls back."""

        c = self.python_env()

        # Keep behavior aligned with .devcontainer/setup.sh.
        # We do not assume uv.lock exists.
        return c.with_exec(
            [
                "bash",
                "-lc",
                "set -euo pipefail; "
                "cd /workspace/code/unsloth_example_1; "
                "if [ -f uv.lock ]; then uv sync --locked; else uv sync; fi",
            ]
        )

    @function
    def prefetch_datasets(self) -> dagger.Container:
        """Pre-download evaluation datasets into the /data cache volume."""

        c = self.sync_deps()
        return c.with_exec(
            [
                "bash",
                "-lc",
                "set -euo pipefail; "
                "cd /workspace/code/unsloth_example_1; "
                "python -c \"\n"
                "from datasets import load_dataset\n"
                "load_dataset('nvidia/OpenMathReasoning-mini', split='cot')\n"
                "load_dataset('mlabonne/FineTome-100k', split='train')\n"
                "print('datasets cached')\n"
                "\"",
            ]
        )

    @function
    def config_report(self) -> str:
        """Return a short config report (judge endpoint and model)."""

        base_url = os.environ.get("DEEPEVAL_JUDGE_BASE_URL", "<unset>")
        judge_model = os.environ.get("DEEPEVAL_JUDGE_MODEL", "<unset>")
        api_key_set = bool(os.environ.get("DEEPEVAL_JUDGE_API_KEY") or os.environ.get("OPENAI_API_KEY"))

        return (
            "Judge config (eval runner):\n"
            f"- DEEPEVAL_JUDGE_BASE_URL: {base_url}\n"
            f"- DEEPEVAL_JUDGE_MODEL: {judge_model}\n"
            f"- judge API key set: {api_key_set}\n"
        )

    @function
    def setup(self) -> dagger.Container:
        """End-to-end setup: deps + datasets."""

        return self.prefetch_datasets()
