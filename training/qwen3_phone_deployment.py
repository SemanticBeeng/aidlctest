"""
Qwen3-0.6B QAT Phone Deployment Training Pipeline
===================================================
Extracted from Unsloth Colab notebook:
https://colab.research.google.com/github/unslothai/notebooks/blob/main/nb/Qwen3_(0_6B)-Phone_Deployment.ipynb

This script trains Qwen3-0.6B with Quantization-Aware Training (QAT)
using Unsloth's phone-deployment scheme (INT8 dynamic activations + INT4 weights),
then saves the model in TorchAO format ready for ExecuTorch export.

Usage:
  - As plain Python:  python qwen3_phone_deployment.py
  - With marimo:       marimo edit qwen3_phone_deployment.py
  - In VS Code:        Run individual cells via '# %%' markers

Requirements: See pyproject.toml (managed by Poetry)
GPU: Requires CUDA GPU (tested on Tesla T4, ~10.5 GB peak VRAM)
"""

# %% [markdown]
# ## 1. Environment Setup

# %%
import os
import subprocess
import sys


def install_dependencies():
    """Install all required packages. Skip if already installed."""
    # Check if unsloth is already available
    try:
        import unsloth  # noqa: F401

        print("Unsloth already installed, skipping dependency installation.")
        return
    except ImportError:
        pass

    is_colab = "COLAB_" in "".join(os.environ.keys())

    if not is_colab:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "unsloth"])
    else:
        import re

        import torch

        v = re.match(r"[\d]{1,}\.[\d]{1,}", str(torch.__version__)).group(0)
        xformers = (
            "xformers=="
            + {
                "2.10": "0.0.34",
                "2.9": "0.0.33.post1",
                "2.8": "0.0.32.post2",
            }.get(v, "0.0.34")
        )
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "sentencepiece",
                "protobuf",
                "datasets==4.3.0",
                "huggingface_hub>=0.34.0",
                "hf_transfer",
            ]
        )
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "unsloth_zoo",
                "bitsandbytes",
                "accelerate",
                xformers,
                "peft",
                "trl",
                "triton",
                "unsloth",
            ]
        )

    # Pin specific versions for compatibility
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "transformers==4.57.3"]
    )
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--no-deps", "trl==0.25.1"]
    )
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "torchao==0.14.0",
            "optimum==1.24.0",
            "pytorch-tokenizers",
            "executorch",
        ]
    )
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "git+https://github.com/huggingface/optimum-executorch.git@v0.1.0",
            "--no-deps",
        ]
    )
    print("All dependencies installed successfully.")


install_dependencies()


# %% [markdown]
# ## 2. Load Model with QAT

# %%
import torch  # noqa: E402
from unsloth import FastLanguageModel  # noqa: E402

# Record initial GPU memory for stats later
start_gpu_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
max_memory = round(torch.cuda.get_device_properties(0).total_mem / 1024 / 1024 / 1024, 3)

# Models supported for Phone Deployment via Unsloth QAT
SUPPORTED_MODELS = [
    "unsloth/Qwen3-4B",
    "unsloth/Qwen3-32B",
    "unsloth/Llama-3.1-8B-Instruct",
    "unsloth/Llama-3.2-1B-Instruct",
    "unsloth/Llama-3.2-3B-Instruct",
    "unsloth/Llama-3.3-70B-Instruct",
    "unsloth/Qwen3-0.6B",
    "unsloth/Qwen3-1.7B",
    "unsloth/Qwen3-8B",
    "unsloth/Qwen3-14B",
]

# Load Qwen3-0.6B with QAT phone-deployment scheme
# full_finetuning=True: all params trainable (not LoRA)
# qat_scheme="phone-deployment": INT8 dynamic activations + INT4 weights
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen3-0.6B",
    max_seq_length=1024,
    full_finetuning=True,
    qat_scheme="phone-deployment",
)

print(f"Model loaded. GPU memory: {start_gpu_memory} GB / {max_memory} GB")


# %% [markdown]
# ## 3. Prepare Training Data
#
# Two datasets are mixed:
# 1. **Reasoning** (75%): OpenMathReasoning-mini COT traces (verifiable, >95% accuracy)
# 2. **Non-reasoning** (25%): FineTome-100k in ShareGPT format (general chat)

# %%
from datasets import Dataset, load_dataset  # noqa: E402

# Load reasoning dataset (Chain-of-Thought math traces)
reasoning_dataset = load_dataset("unsloth/OpenMathReasoning-mini", split="cot")
print(f"Reasoning dataset: {reasoning_dataset}")

# Load non-reasoning dataset (general chat in ShareGPT format)
non_reasoning_dataset = load_dataset("mlabonne/FineTome-100k", split="train")
print(f"Non-reasoning dataset: {non_reasoning_dataset}")


# %%
def generate_conversation(examples):
    """Convert math problem/solution pairs into conversation format."""
    problems = examples["problem"]
    solutions = examples["generated_solution"]
    conversations = []
    for problem, solution in zip(problems, solutions):
        conversations.append(
            [
                {"role": "user", "content": problem},
                {"role": "assistant", "content": solution},
            ]
        )
    return {"conversations": conversations}


# Apply chat template to reasoning dataset
reasoning_conversations = tokenizer.apply_chat_template(
    list(
        reasoning_dataset.map(generate_conversation, batched=True)["conversations"]
    ),
    tokenize=False,
)
print(f"Reasoning conversations: {len(reasoning_conversations)}")


# %%
from unsloth.chat_templates import standardize_sharegpt  # noqa: E402

# Standardize ShareGPT format and apply chat template to non-reasoning dataset
dataset = standardize_sharegpt(non_reasoning_dataset)
non_reasoning_conversations = tokenizer.apply_chat_template(
    list(dataset["conversations"]),
    tokenize=False,
)
print(f"Non-reasoning conversations: {len(non_reasoning_conversations)}")


# %%
import pandas as pd  # noqa: E402

# Mix ratio: 75% reasoning, 25% non-reasoning
chat_percentage = 0.25

# Sample non-reasoning subset to match target ratio
non_reasoning_subset = pd.Series(non_reasoning_conversations)
non_reasoning_subset = non_reasoning_subset.sample(
    int(len(reasoning_conversations) * (chat_percentage / (1 - chat_percentage))),
    random_state=2407,
)

# Combine and shuffle
data = pd.concat([pd.Series(reasoning_conversations), pd.Series(non_reasoning_subset)])
data.name = "text"

combined_dataset = Dataset.from_pandas(pd.DataFrame(data))
combined_dataset = combined_dataset.shuffle(seed=3407)
print(f"Combined dataset: {combined_dataset}")


# %% [markdown]
# ## 4. Train the Model
#
# Training uses SFTTrainer with QAT-aware settings.
# Default: 100 steps for demo. Set `num_train_epochs=1` and `max_steps=None` for full run.

# %%
from trl import SFTConfig, SFTTrainer  # noqa: E402

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=combined_dataset,
    eval_dataset=None,  # Can set up evaluation
    args=SFTConfig(
        dataset_text_field="text",
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,  # Effective batch size = 2 * 4 = 8
        warmup_steps=5,
        # num_train_epochs = 1,  # Set this for 1 full training run
        max_steps=100,
        learning_rate=5e-5,
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.001,
        lr_scheduler_type="linear",
        seed=3407,
        report_to="none",  # Use TrackIO/WandB etc
    ),
)

trainer_stats = trainer.train()


# %% [markdown]
# ## 5. Training Stats

# %%
# Show final memory and time stats
used_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
used_memory_for_training = round(used_memory - start_gpu_memory, 3)
used_percentage = round(used_memory / max_memory * 100, 3)
training_percentage = round(used_memory_for_training / max_memory * 100, 3)

print(f"{trainer_stats.metrics['train_runtime']} seconds used for training.")
print(f"{round(trainer_stats.metrics['train_runtime'] / 60, 2)} minutes used for training.")
print(f"Peak reserved memory = {used_memory} GB.")
print(f"Peak reserved memory for training = {used_memory_for_training} GB.")
print(f"Peak reserved memory % of max memory = {used_percentage} %.")
print(f"Peak reserved memory for training % of max memory = {training_percentage} %.")


# %% [markdown]
# ## 6. Save Model (TorchAO format)
#
# Saves the QAT-trained model in TorchAO format, ready for ExecuTorch conversion.
# Output directory: `phone_model/`

# %%
model.save_pretrained_torchao("phone_model", tokenizer=tokenizer)
print("Model saved to phone_model/ in TorchAO format.")


# %% [markdown]
# ## 7. Export to ExecuTorch (.pte)
#
# Three steps to convert to a deployable .pte file:
# 1. Convert weight checkpoint keys to ExecuTorch format
# 2. Download model config from ExecuTorch repo
# 3. Export to .pte with XNNPACK backend
#
# For automated export, run: `bash export_executorch.sh`

# %%
def export_to_executorch(
    model_dir: str = "phone_model",
    output_name: str = "qwen3_0.6B_model.pte",
    config_url: str = "https://raw.githubusercontent.com/pytorch/executorch/main/examples/models/qwen3/config/0_6b_config.json",
    config_file: str = "0.6B_config.json",
    converted_weights: str = "pytorch_model_converted.bin",
    max_context_length: int = 1024,
    max_seq_length: int = 128,
):
    """Export the saved TorchAO model to ExecuTorch .pte format."""
    import shutil

    # Step 1: Convert weight checkpoint state dict keys
    print("Step 1/3: Converting weight checkpoint keys...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "executorch.examples.models.qwen3.convert_weights",
            model_dir,
            converted_weights,
        ],
        check=True,
    )

    # Step 2: Download model config from ExecuTorch repo
    print("Step 2/3: Downloading model config...")
    curl_path = shutil.which("curl")
    if curl_path:
        subprocess.run(
            ["curl", "-L", "-o", config_file, config_url],
            check=True,
        )
    else:
        # Fallback: use Python urllib
        from urllib.request import urlretrieve

        urlretrieve(config_url, config_file)

    # Step 3: Export to .pte
    print("Step 3/3: Exporting to .pte (this may take several minutes)...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "executorch.examples.models.llama.export_llama",
            "--model",
            "qwen3_0_6b",
            "--checkpoint",
            converted_weights,
            "--params",
            config_file,
            "--output_name",
            output_name,
            "-kv",
            "--use_sdpa_with_kv_cache",
            "-X",
            "--xnnpack-extended-ops",
            "--max_context_length",
            str(max_context_length),
            "--max_seq_length",
            str(max_seq_length),
            "--dtype",
            "fp32",
            "--metadata",
            '{"get_bos_id":199999, "get_eos_ids":[200020,199999]}',
        ],
        check=True,
    )

    # Verify output
    if os.path.exists(output_name):
        size_mb = os.path.getsize(output_name) / 1024 / 1024
        print(f"Export complete: {output_name} ({size_mb:.1f} MB)")
    else:
        print(f"WARNING: Expected output {output_name} not found!")


export_to_executorch()
