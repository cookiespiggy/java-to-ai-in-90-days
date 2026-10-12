# 与《Java 到 AI 的 90 天》18 篇实验 2 完全一致的脚本
import json, random, os

SYSTEM = "你是米宝公司的客服助手，语气亲切可爱，句末常用波浪号～"

SEEDS = [
    ("年假怎么休", "您好呀～年假需要提前一周在系统提交申请哦，入职满一年就有5天带薪的呢！"),
    ("打卡迟到了怎么办", "您好呀～每月有3次忘打卡不用担心的，第4次起会扣50元哦！"),
    ("报销要什么发票", "您好呀～发票抬头必须是公司全称哦，行程结束30天内提交最保险！"),
]

def synthesize(q, a):
    variants = [
        (f"我想问下，{q}", f"您好呀～{a[3:] if a.startswith('您好呀') else a}"),
        (f"{q}？急", f"您好呀～别急，{a[3:] if a.startswith('您好呀') else a}"),
        (q, a),
    ]
    return variants

pairs = []
for q, a in SEEDS:
    pairs += synthesize(q, a)

random.seed(42)
random.shuffle(pairs)
n_valid = max(1, len(pairs) // 5)
valid, train = pairs[:n_valid], pairs[n_valid:]

def dump(rows, path):
    os.makedirs("data", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for q, a in rows:
            f.write(json.dumps({"messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": q},
                {"role": "assistant", "content": a},
            ]}, ensure_ascii=False) + "\n")
    print(f"{path}: {len(rows)} 条")

dump(train, "data/train.jsonl")
dump(valid, "data/valid.jsonl")

train_q = {q for q, _ in train}
leak = [q for q, _ in valid if q in train_q]
assert not leak, f"数据泄漏！valid 里有 {len(leak)} 条问题在 train 出现过"
print("污染自检通过 ✓")
