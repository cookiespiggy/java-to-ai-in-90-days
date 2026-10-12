import sys
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler

import os
MODEL = os.environ.get("MODEL") or __import__("glob").glob(
    os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen2.5-0.5B/snapshots/*/"))[0]
SYSTEM = "你是米宝公司的客服助手，语气亲切可爱，句末常用波浪号～"

def ask(q, adapter=None):
    kw = {"adapter_path": adapter} if adapter else {}
    model, tok = load(MODEL, **kw)
    # 完全复刻训练时模板：system + user
    prompt = f"system\n{SYSTEM}\nuser\n{q}\nassistant\n"
    return generate(model, tok, prompt=prompt, max_tokens=50,
                    sampler=make_sampler(temp=0.0), verbose=False)

mode = sys.argv[1]
for q in (sys.argv[2:] or ["打卡迟到了怎么办", "年假怎么休", "报销要什么发票"]):
    out = ask(q, "./adapters" if mode == "ft" else None)
    print(f"Q: {q}\nA: {out.strip()[:120]}\n")
