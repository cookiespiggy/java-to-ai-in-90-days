#!/bin/bash
# 作者实测通过：mlx-lm 0.32.0 + Qwen2.5-0.5B（bf16 safetensors）+ mlx-lm/lora
# 实测：loss 6.443 → 0.777，1794 tok/s，峰值内存 ~1.0GB，可训练参数 0.594%
set -e
MODEL="${MODEL:-$(echo ~/.cache/huggingface/hub/models--Qwen--Qwen2.5-0.5B/snapshots/*/)}"

echo "模型: $MODEL"
uv run mlx_lm.lora \
  --model "$MODEL" \
  --train \
  --data ./data \
  --iters 60 \
  --batch-size 1 \
  2>&1 | tee train.log
