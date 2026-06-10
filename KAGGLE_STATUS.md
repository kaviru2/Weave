# Kaggle Training & SFT Fine-Tuning Status Guide

This guide details what was set up to connect and run LoRA fine-tuning on Kaggle, the logic bugs resolved, and the commands required to continue.

---

## 1. Project Directory Structure

- **`dataset/train_lora.py`**: The core SFT script utilizing HuggingFace `trl` and `peft` to fine-tune 8B models (Llama-3-8B or DeepSeek-Coder-7B) on GPU instances (with double quantization configs, gradient checkpointing, paged optimizers, and a `--dry-run` flag).
- **`dataset/output/kaggle_upload/`**: Holds files packaged and uploaded to Kaggle as a private dataset.
  - `dataset-metadata.json` (ID: `kaviruhapuarachchi/weave-sft-dataset`)
  - `train_lora.py` (Copied from root `dataset/train_lora.py`)
  - `train_point_dups.jsonl` / `val_point_dups.jsonl` (SFT formatting)
- **`dataset/output/kaggle_kernel/`**: Holds metadata and the launch script for Kaggle execution.
  - `kernel-metadata.json` (ID: `kaviruhapuarachchi/weave-sft-training`)
  - `train_lora_kaggle.py` (Installs GPU libraries on the container, checks paths, and runs `train_lora.py`)

---

## 2. Kaggle Connection & Authentication Details

- **Kaggle API Token**: Configured at `~/.kaggle/access_token` (permissions `600`).
- **Python package**: Installed in the virtual environment. Accessible via `.venv/bin/kaggle`.

---

## 3. Kaggle CLI Commands Cheat Sheet

Run all commands from the workspace root:

- **Check Current Kernel Status**:
  ```bash
  .venv/bin/kaggle kernels status kaviruhapuarachchi/weave-sft-training
  ```
- **Fetch Kernel execution Logs**:
  ```bash
  .venv/bin/kaggle kernels logs kaviruhapuarachchi/weave-sft-training
  ```
- **Copy and Update Dataset Files**:
  ```bash
  cp dataset/train_lora.py dataset/output/kaggle_upload/train_lora.py
  .venv/bin/kaggle datasets version -p dataset/output/kaggle_upload -m "Commit message"
  ```
- **Push Kernel Changes / Restart Kernel Run**:
  ```bash
  .venv/bin/kaggle kernels push -p dataset/output/kaggle_kernel
  ```

---

## 4. Logical Bugs Resolved (Version 11 Patch)

### Error in Version 9/10:
```
TypeError: SFTTrainer.__init__() got an unexpected keyword argument 'max_seq_length'
```

### Cause:
In modern versions of `trl` (e.g. 0.12.0 / 0.13.0), direct constructor arguments like `max_seq_length` are deprecated and moved into `SFTConfig` under the renamed key `max_length`.
In `train_lora.py`, the code checked if `"max_seq_length" in sft_fields` to add it to config. Because it wasn't found under that key, it fell back to passing it directly to `SFTTrainer`, causing the `TypeError`.

### Patch Implemented:
Updated `dataset/train_lora.py` to check for both keys in `SFTConfig` fields:
```python
        if "max_seq_length" in sft_fields:
            extra_kwargs["max_seq_length"] = args.max_seq_length
            sft_config_has_max_seq = True
        elif "max_length" in sft_fields:
            extra_kwargs["max_length"] = args.max_seq_length
            sft_config_has_max_seq = True
```

---

## 5. Current Actionable Status

We have updated the Kaggle Dataset version and pushed **Version 11** of the Kaggle Kernel:
1. **Status**: Currently in `KernelWorkerStatus.RUNNING` state.
2. **Next Steps**:
   - Check the status via `.venv/bin/kaggle kernels status kaviruhapuarachchi/weave-sft-training`.
   - Once the logs become available, check progress via `.venv/bin/kaggle kernels logs kaviruhapuarachchi/weave-sft-training`.
   - If the training completes successfully, download the output adapter weights.
