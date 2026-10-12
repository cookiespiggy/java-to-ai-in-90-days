import re, statistics

ANSI = re.compile(r"\x1b\[[0-9;]*m")

def parse_loss(path):
    """解析 mlx-lm 训练日志（按作者实测格式修正：val 行与 train 行必须分开）"""
    train, val = [], []
    for raw in open(path, encoding="utf-8", errors="ignore"):
        line = ANSI.sub("", raw)
        # 实测格式： "  10    4.016 ▼   1,375   0.6k"   /   "  40    val 0.780    0.02s"
        m = re.match(r"\s*(\d+)\s+(val\s+)?([\d.]+)", line)
        if not m:
            continue
        it, v = int(m.group(1)), float(m.group(3))
        (val if m.group(2) else train).append((it, v))
    return train, val

def verdict(train, val):
    if not train:
        return "没抓到 loss，检查日志格式"
    t_l = [v for _, v in train]
    t_tail = t_l[-5:]
    trend = "下降中" if (max(t_tail) - min(t_tail)) > 0.005 else "已走平"
    if not val:
        return f"train loss {trend}（无 val 点，无法判断过拟合）"
    # 关键：只用【最后一个 val 点】跟【同一 iter 的 train 点】比
    v_iter, v_last = val[-1]
    same_iter = [v for i, v in train if i == v_iter] or t_l[-1:]
    gap = v_last - statistics.mean(same_iter)
    if gap > 0.15:
        return f"{trend}；val({v_last:.3f}) 比 train 高 {gap:.3f} → 过拟合，减 epochs / 加数据 / 降 lr"
    if trend == "已走平":
        return f"train loss 走平至 {t_l[-1]:.3f}；val {v_last:.3f}，间距 {gap:+.3f} 正常 → 收工"
    return f"{trend}（当前 {t_l[-1]:.3f}）；val {v_last:.3f}，间距 {gap:+.3f} 正常 → 继续训"

train, val = parse_loss("train_raw.log")
print("train loss:", [f"{i}:{v}" for i, v in train])
print("val   loss:", [f"{i}:{v}" for i, v in val])
print("\n诊断结论：", verdict(train, val))
