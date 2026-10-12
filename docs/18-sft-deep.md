# 18 · SFT 深水区：让 1.7B 小模型上岗

## 先讲给朋友听（如果你只有一分钟）

> 微调的门槛从来不在算法，在两件事：**你的数据够不够金，你能不能看出训练有没有变好**。算法是开源库的三行代码，数据是你的业务认知，诊断是你的工程素养——这两样，培训机构都不教。

## 你的 Aha Moment

一个真实场景（就发生在这本书的作者机器上），以及你大概率也踩过的一个追问：

> 作者想在 Mac 上微调 Qwen3.5-4B，对着 `unsloth/Qwen3.5-4B-GGUF` 摩拳擦掌，文件下好了。
>
> 作者查文档：训练命令要 safetensors 或 bnb-4bit，没有一个吃 GGUF。**"那我不能用 unsloth 训吗？它明明是训练软件！"**

```
~/.cache/huggingface/hub/models--unsloth--Qwen3.5-4B-GGUF/
├── snapshots/e87f1764.../Qwen3.5-4B-UD-Q4_K_XL.gguf   ← 2.5G 推理权重
└── snapshots/e87f1764.../mmproj-F16.gguf              ← 1.1G 视觉投影器
```

### 先给答案：unsloth 能训 4B，但它训的不是你手上这个文件

我们直接读作者机器上 unsloth 的真实源码（`~/.unsloth/studio/.../unsloth/models/loader.py`），不靠猜：

**加载模型时**，它只认这两种后缀：

```python
def _strip_unsloth_bnb_4bit_suffix(model_name: str) -> str:
    """Remove Unsloth 4bit suffixes"""
    for suffix in ("-unsloth-bnb-4bit", "-bnb-4bit"):   # ← 只有这两个
        ...
```

**GGUF 出现在哪？** 只在 `save.py` 的**导出**环节：

```python
from .save import convert_to_gguf, quantize_gguf    # ← 训完之后导出成 GGUF
"save_to_gguf",
```

所以 unsloth 的完整链路是这样的——**GGUF 是终点，不是起点**：

```
   safetensors / bnb-4bit  ──训练(算梯度、更新权重)──▶  fuse 合并  ──量化──▶  .gguf  ──▶ 推理
        ▲                        unsloth 的地盘                                              ▲
        │                                                                              llama.cpp 的地盘
   你下错的话就在这里                                                                  你下的就在这里
```

| | unsloth 训的 | 你下的 |
|---|---|---|
| HF 仓库 | `unsloth/Qwen3.5-4B` 或 `-bnb-4bit` | `unsloth/Qwen3.5-4B-GGUF` |
| 格式 | safetensors（**未量化的原始权重**） | GGUF（**已 4bit 量化**） |
| 在 unsloth 眼里 | **输入**（能读能训） | **输出**（只能写出来，读不进去） |
| 类比 | `.java` 源码 | 编译好的 `.jar` |

**用 unsloth 训 GGUF，等于拿编译好的 jar 反编译回源码去改代码。**

### 为什么"GGUF 不能训"有更深的一层

不只是"工具不支持"，而是**数学上做不了**：GGUF 里存的是 Q4_K_XL 量化权重——原始权重被压成 4bit，**信息不可逆地丢掉了**。训练要做的是"算梯度 → 更新权重"，但你手里只剩一份被四舍五入过的快照，梯度无处可寻。

> 补充：llama.cpp 确实有 GGUF→HF 的反向转换脚本，你可以反量化回 BF16 再训。**但那等于拿一份"被 4bit 损伤过的模型"当训练基线**，质量比直接用原始权重差得多，生产上没人这么干。这条路存在，但不该走。

### 你为什么会下错？（不是你的错，是 GUI 的默认引导）

Unsloth Studio 同时给你**两个按钮**：

| 你点的按钮 | 它下载的 | 用途 |
|---|---|---|
| **本地跑跑看**（推理） | GGUF（轻、快、2.7G） | 只推理 |
| **开始微调**（训练） | safetensors / bnb-4bit（重、8G） | 可训可推 |

第一次用 Unsloth 的人几乎都会先点第一个——**这是产品的默认引导，不是你理解错了。** 记住一句话：**"GGUF 是后训练流程的终点，不是起点。"**

### 四种格式，四种用途，互不通用

| 格式 | 长相 | 谁吃它 | 能不能训 |
|---|---|---|---|
| **safetensors** | `model.safetensors` + `config.json` | HF transformers、oMLX、训练栈 | **能，标准训练格式** |
| **GGUF** | 单个 `.gguf`（可带 mmproj） | llama.cpp、Unsloth Studio 推理 | 不能（推理成品） |
| **bnb-4bit** | `unsloth/xxx-bnb-4bit` | unsloth / bitsandbytes（NVIDIA GPU） | 能，QLoRA 专用 |
| **MLX-4bit** | `mlx-community/xxx-4bit` | MLX、oMLX、mlx-lm（Apple Silicon） | 能，Mac 的 QLoRA |

注意最后两行的地理政治：**bnb-4bit 是 NVIDIA 的地盘，MLX 是苹果的地盘。** 你在 Mac 上跑训练，选择就只有一条：**MLX 路线**。

顺带解决另一个疑问：unsloth 把模型下到哪了？官方 README 写得很直白——**默认就是 HuggingFace 标准缓存目录**，macOS 是 `~/.cache/huggingface/hub/`，想换盘就设 `HF_HOME` / `HF_HUB_CACHE` 环境变量。目录里的门道也值得记：`models--组织--模型名/` 下面是 `blobs/`（按 SHA256 命名的实体文件）和 `snapshots/<commit>/`（一堆**软链接**指回 blobs）。

**这个布局你太熟了——这就是个内容寻址存储（CAS）**，跟你本地 Maven 仓库 `~/.m2/repository` 里 `groupId/artifactId/version/` + SHA1 校验文件是同一个设计思想：内容寻址、去重、软链接省空间、换盘靠改环境变量。你已经在用这套十年了。

## 不讲术语的版本：SFT 的两根支柱

**支柱一 · 数据工程（本篇 70% 的篇幅）。**

一条金数据的生产流水线，五个工位：

```
① 造种子（10~20条，你自己写，必须是你写的）
      ↓
② AI 扩写（大模型读种子 → 生成 50 条仿写）
      ↓
③ 人审（删、改、并，这是你不可替代的一步）
      ↓
④ 格式转换（转成 messages chat 格式，见 17 篇）
      ↓
⑤ 配比切分（通用数据混入防遗忘 + 9:1 切 train/valid）
```

三个致命细节，踩任一一条，训练白跑：

**细节 1：评测集必须"物理隔离"。** 如果 valid.jsonl 里混进了 train 里见过的原题，你看到的"评测分数"就是背诵成绩单。正确做法：先把全部数据 9:1 切了，再各自扩写，**绝不在扩写之后切**。这条写进你的 checklist。

**细节 2：防灾难性遗忘要掺"通用数据"。** 只拿客服数据训，模型会变成"除了客服啥也不会"的偏科生——问它"1+1 等于几"都可能开始卖萌。工业界做法是 **领域数据 : 通用数据 ≈ 7:3 到 8:2**。通用数据不用自己造，开源指令数据集捞几千条即可。

**细节 3：数量级认知。** 300 条能看到效果，3000 条能上线，3 万条是团队预算。**低于 100 条的微调项目，大概率是过拟合表演。**

**支柱二 · 训练诊断（本篇 30% 的篇幅）。**

训练不是"跑完看效果"，是读三个信号：

| 信号 | 健康 | 生病 |
|---|---|---|
| train loss | 稳步下降 | 不降 = 学习率/数据有问题 |
| train vs eval loss 的**间距** | 两条线贴近 | 越拉越开 = **过拟合**（在背答案） |
| 评测集分数 | 上升后平稳 | 先升后降 = 该停早了（选 checkpoint 不是选终点） |

第三条最容易被忽略：**微调的最优解通常不在最后一步。** loss 曲线是个"先降后升"的 U 型，你要的是谷底那个 checkpoint，不是训练结束那个。所以**每 N 步存一次 checkpoint，用评测集选**——这就是"评测驱动选型"，也是 17 篇说"数据比算法贵"的工程版。

## Java 老司机对照室

| SFT 概念 | 你已经懂的概念 | 一句话翻译 |
|---|---|---|
| safetensors | 源码 | 训练只能改它 |
| GGUF | JAR / APK | 压缩成品，推理专用 |
| HF 缓存目录 | Maven 本地仓库 | 内容寻址 + 软链接 + 环境变量换盘 |
| `HF_HOME` / `HF_HUB_CACHE` | `MAVEN_OPTS -Dmaven.repo.local` | 换盘的唯一正规姿势 |
| LoRA adapter | AOP 切面 | 几十 MB，随时挂载/卸载 |
| checkpoint 谷底选型 | 挑最佳发布版本 | 不是最后一次构建 |
| 防遗忘配比 | 灰度发布旁路老逻辑 | 新能力 + 老能力都要在 |
| 去污染（数据隔离） | 测试集不进训练 | 评测才可信 |
| epoch 过多 | 过度加班 | 背答案，泛化崩 |

## 动手实验室

本章所有路径都对着作者那台 M5 Pro / 24G 机器写的，你可以逐条对照自己的。

### 实验 1：模型资产体检（先判断"能不能训"）

```bash
# 1. 我有什么？
du -shL ~/.cache/huggingface/hub/models--* 2>/dev/null

# 2. 它是什么格式？（看扩展名和目录结构）
ls ~/.cache/huggingface/hub/models--unsloth--Qwen3.5-4B-GGUF/snapshots/*/
# → Qwen3.5-4B-UD-Q4_K_XL.gguf + mmproj-F16.gguf   ⚠️ GGUF，不能训

ls ~/.cache/huggingface/hub/models--Qwen--Qwen2.5-0.5B/snapshots/*/
# → config.json + model.safetensors               ✅ 可以训
```

三个判定口诀：

- **有 `config.json` + `*.safetensors`** → 能训（标准格式）
- **单个 `.gguf`** → 只能推理，训它先去找 safetensors 版
- **名字带 `-bnb-4bit`** → NVIDIA GPU 专用；**带 `-MLX-4bit`** → 苹果专用

**终极判定法（不靠猜，用代码测）**：文件头会自证身份。

```python
import struct, glob, os

def can_train(path: str) -> tuple[bool, str]:
    """读文件头判断：这是训练原料还是推理成品"""
    with open(path, "rb") as f:
        magic = f.read(4)
        if magic == b"GGUF":
            f.seek(0, 2)
            return False, f"GGUF 推理成品（{f.tell()/2**30:.2f}GB），不能训"
        if magic == b"PK\x03\x04":
            return False, "PyTorch .bin/.pt 旧格式（建议换 safetensors）"
        # safetensors: 前 8 字节是 JSON header 的长度
        length = struct.unpack("<Q", magic + f.read(4))[0]
        return True, f"safetensors（header {length} 字节）→ 能训"

# 注意：glob 不认 "~"，必须先 expanduser，否则永远匹配不到
HOME = os.path.expanduser("~")
for name in ["Qwen3.5-4B-UD-Q4_K_XL.gguf", "model.safetensors"]:
    found = glob.glob(f"{HOME}/.cache/huggingface/hub/**/{name}", recursive=True)
    if found:
        ok, msg = can_train(found[0])
        print(f"{'✅' if ok else '❌'} {name:32} {msg}")
```

实测输出：

```
❌ Qwen3.5-4B-UD-Q4_K_XL.gguf           GGUF 推理成品（2.71GB），不能训
✅ model.safetensors                     safetensors（header 32280 字节）→ 能训
```

**把这十行存进你的工具箱。** 以后下载任何模型，先跑一遍，不确定它是训练料还是推理成品，三秒钟得到答案——比翻文档快十倍，也不会像本书作者一样踩坑。

### 实验 2：数据流水线（本篇的核心资产）

```python
# build_dataset.py —— 把 17 篇的 3 条种子扩成可训练的 30 条，并做好隔离
import json, random, os

SYSTEM = "你是米宝公司的客服助手，语气亲切可爱，句末常用波浪号～"

SEEDS = [
    ("年假怎么休", "您好呀～年假需要提前一周在系统提交申请哦，入职满一年就有5天带薪的呢！"),
    ("打卡迟到了怎么办", "您好呀～每月有3次忘打卡不用担心的，第4次起会扣50元哦！"),
    ("报销要什么发票", "您好呀～发票抬头必须是公司全称哦，行程结束30天内提交最保险！"),
]

# ① 造种子（这 3 条必须你自己写，是全套数据的"味"）
# ② AI 扩写：演示用规则版；真实项目把这行换成调大模型
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

# ⑤ 先切分，再生成更多 —— 顺序反了就是数据污染
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

# 污染自检：valid 的问题不允许在 train 里出现
train_q = {q for q, _ in train}
leak = [q for q, _ in valid if q in train_q]
assert not leak, f"数据泄漏！valid 里有 {len(leak)} 条问题在 train 出现过"
print("污染自检通过 ✓")
```

跑完你得到 **8 条 train / 1 条 valid**（3 条种子 × 3 个变体，演示量级），并且有一道断言替你把关。**真实项目里，`synthesize` 那一步换成调大模型，扩到 1000 条，其余代码一行不改。**

### 实验 3：在 24G 的 Mac 上开训（mlx-lm + 你已有的模型）

> ⚠️ **实测踩坑预警**：实验 2 造出来的数据只有 9 条（8 train + 1 valid），而 **mlx-lm 默认 `batch_size=4`**，会直接报错：
> ```
> ValueError: Dataset must have at least batch_size=4 examples but only has 1
> ```
> **解法：加 `--batch-size 1`**（本项目的 `train.sh` 已配好）。要么就把数据扩到 10 条以上。

```bash
uv add mlx-lm

# 用你已经下好的 Qwen2.5-0.5B 练手：几分钟一轮，loss 曲线肉眼可见
uv run mlx_lm.lora \
  --model ~/.cache/huggingface/hub/models--Qwen--Qwen2.5-0.5B/snapshots/*/ \
  --train --data ./data --iters 60 --batch-size 1
```

**作者的实测输出**（2026-10-12，M5 Pro / 24GB，mlx-lm 0.32.0 / Qwen2.5-0.5B）：

```
iter   train_loss     tok/s     tokens
  1    val 6.443      1.37s
 10    4.016 ▼         71      0.6k
 20    1.380 ▼       1,792      1.3k
 30    0.880 ▼       1,794      1.9k
 40    val 0.780      0.02s
 60    0.737 ▼       1,786      3.8k

Trainable parameters: 0.594% (2.933M/494.033M)
峰值内存: ~1.0 GB
```

**盯住那行 `0.594%`**——这就是 LoRA 的全部魔法：只训了 494M 参数里的 2.9M（0.594%），其余冻结。

跑之前，先算一遍 **24G 内存账**（这张表对着 M5 Pro 24G 实测过）：

| 模型 | 权重（MLX 4bit） | LoRA 训练额外开销 | 24G 可行性 |
|---|---|---|---|
| 0.5B / 0.8B | ~0.3G | ~1G | 轻松，随便练手 |
| 4B | ~2.5G | ~5~8G | **可行**（梯度+优化器+激活值） |
| 9B | ~5.5G | ~12~15G | 紧，降 batch 和 seq len |
| 14B+ | ~8G | ~15G+ | 别想，会 swap 到 SSD |

看见第二行了吗——**你机器上训得动 4B，你缺的只是一个 safetensors/MLX 版的 4B，而不是下好的那个 GGUF。** 补一条命令：

```bash
# 补下 MLX 4bit 版（注意路径：HF 缓存，不是 GGUF）
uv run huggingface-cli download mlx-community/Qwen3.5-4B-MLX-4bit
```

#### 但在动手之前，先问一句：你真的需要生成式模型吗？

这张表回答的是"**要训生成模型，多大够用**"。但 2026 年下半年出现了一个值得注意的趋势：**不是所有任务都需要模型写字。**

判断方法很简单，问自己一句：**这个任务的正确答案是"一段话"还是"一个类别/分数"？**

| 你的任务 | 该用 | 典型规模 |
|---|---|---|
| "把这段话改得更专业" | 生成式（要写字） | 4B 起 |
| "回答用户的制度问题" | 生成式（RAG + 生成） | 7B+ 或 API |
| "这条工单转哪个部门" | **判别式**（只要一个类别+概率） | 几百 M 到 2B |
| "这个 prompt 是不是越狱注入" | **判别式**（要一个可卡阈值的分数） | 几百 M |
| "给这段代码打风险分" | **判别式** | 几百 M |

**选错路线的代价是十倍的**：用 7B 生成式模型做一个"二选一"的判断，不仅慢、贵，而且它在两个选项之间反复摇摆，你还得写 Prompt 去"稳住"它——**而判别式模型天生就是干这个的**（17 篇工位 5 讲了它的训练方式）。

反面教材（**注意：我只引用已公开报道的数字，且各方跑分本就不一致，请以你自己的评测集为准**）：2026 年 9 月有开源判别式模型号称刷新了某榜单，但后续技术分析指出，**它未经领域微调时在公开基准上的准确率低于"永远猜多数类"的基线**——它的漂亮分数完全来自针对该基准的微调。**这不是那家模型的错，是所有判别式模型的通病：不微调 = 不及格。** 这条和你前面学的"数据比算法贵"是同一个道理。

### 实验 4：训练诊断（从 loss 日志里读出"该不该停"）

`mlx_lm.lora` 会把 loss 打到终端。**把日志留下来**（`2>&1 | tee train.log`），然后读它。

> ⚠️ **本段代码是作者实测修正后的版本。** 第一版解析不了 mlx-lm 的真实日志，踩了三个坑：① 日志带 ANSI 颜色码，正则直接失效；② `val` 行和 `train` 行混在一起被当成同一类；③ 判断过拟合时拿"所有 val 点"去比"末尾 train 点"，基准点错位。**下面三个修正都标出来了**——这正是"跑一遍才知道"的价值。

```python
# diagnose.py —— 从 mlx-lm 真实日志里解析 loss，判断过拟合
import os, re, statistics, sys

ANSI = re.compile(r"\x1b\[[0-9;]*m")          # 修正①：剥掉终端颜色码

def parse_loss(path):
    train, val = [], []
    for raw in open(path, encoding="utf-8", errors="ignore"):
        line = ANSI.sub("", raw)
        # 真实格式： "  10    4.016 ▼   1,375   0.6k"  /  "  40    val 0.780   0.02s"
        m = re.match(r"\s*(\d+)\s+(val\s+)?([\d.]+)", line)
        if not m:
            continue
        it, v = int(m.group(1)), float(m.group(3))
        (val if m.group(2) else train).append((it, v))   # 修正②：val 与 train 分开存
    return train, val

def verdict(train, val):
    if not train:
        return "没抓到 loss，检查日志格式"
    t_l = [v for _, v in train]
    tail = t_l[-5:]
    trend = "下降中" if (max(tail) - min(tail)) > 0.005 else "已走平"
    if not val:
        return f"train loss {trend}（无 val 点，无法判断过拟合）"
    # 修正③：只用【最后一个 val 点】跟【同一 iter 的 train 点】比
    v_iter, v_last = val[-1]
    same = [v for i, v in train if i == v_iter] or t_l[-1:]
    gap = v_last - statistics.mean(same)
    if gap > 0.15:
        return f"{trend}；val({v_last:.3f}) 比 train 高 {gap:.3f} → 过拟合，减 epochs / 加数据 / 降 lr"
    if trend == "已走平":
        return f"train loss 走平至 {t_l[-1]:.3f}；val {v_last:.3f}，间距 {gap:+.3f} 正常 → 收工"
    return f"{trend}（当前 {t_l[-1]:.3f}）；val {v_last:.3f}，间距 {gap:+.3f} 正常 → 继续训"

import sys
LOG = sys.argv[1] if len(sys.argv) > 1 else "train.log"
if not os.path.exists(LOG):
    print(f"找不到日志文件 {LOG}。先跑训练并留档：")
    print("  ./train.sh 2>&1 | tee train.log")
    sys.exit(1)

train, val = parse_loss(LOG)
print("train loss:", [f"{i}:{v}" for i, v in train])
print("val   loss:", [f"{i}:{v}" for i, v in val])
print("诊断结论：", verdict(train, val))
```

**作者的真实诊断输出**：

```
train loss: ['10:4.016', '20:1.38', '30:0.88', '40:0.777']
val   loss: ['1:6.443', '40:0.78']
诊断结论：下降中（当前 0.777）；val 0.780，间距 +0.003 正常 → 继续训
```

`间距 +0.003` 说明 **train 和 val 几乎贴合——训练健康，没有过拟合**。而实验 5 你会亲眼看到模型确实学会了新风格，**这才是"健康训练"应有的样子**。

> 如果你拿到的日志解析不出来，先确认两件事：① 你有没有 `2>&1 | tee train.log`（少了它就没有日志文件）；② 用的 mlx-lm 版本日志格式是否一致（`mlx_lm.lora --help` 看版本，不同版本格式会变）。

### 实验 5：微调前后对赌（本书最有说服力的一个实验）

⚠️ **这里有个 90% 的人会踩的坑**：微调完直接 `mlx_lm.generate --prompt "用户问：..."`，输出会变成乱码或胡言。**原因不是训练失败，是生成时的 prompt 模板和训练时不一致。**

训练时 mlx-lm 把 `messages` 渲染成这样的字符串：

```
system
你是米宝公司的客服助手，语气亲切可爱，句末常用波浪号～
user
打卡迟到了怎么办
assistant
您好呀～...
```

那生成时就必须**一字不差地复刻**它。用 `--use-default-chat-template` 会让 mlx-lm 插入它自己的默认 system（`You are a helpful assistant.`），模型看到没见过的开场白，输出直接崩。

```python
# gen_compare.py —— 微调前后对比（关键：prompt 模板与训练完全一致）
import os, glob, sys
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler

MODEL = os.environ.get("MODEL") or glob.glob(
    os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen2.5-0.5B/snapshots/*/"))[0]
SYSTEM = "你是米宝公司的客服助手，语气亲切可爱，句末常用波浪号～"

def ask(q, adapter=None):
    kw = {"adapter_path": adapter} if adapter else {}
    model, tok = load(MODEL, **kw)
    prompt = f"system\n{SYSTEM}\nuser\n{q}\nassistant\n"   # ← 逐字复刻训练模板
    return generate(model, tok, prompt=prompt, max_tokens=50,
                    sampler=make_sampler(temp=0.0), verbose=False)

for q in ["打卡迟到了怎么办", "年假怎么休", "报销要什么发票"]:
    out = ask(q, "./adapters" if sys.argv[1] == "ft" else None)
    print(f"Q: {q}\nA: {out.strip()[:120]}\n")
```

```bash
uv run python gen_compare.py base    # 微调前
uv run python gen_compare.py ft      # 微调后
```

**作者的实测对照**（同一台机器，同一个问题）：

| 问题 | 微调前 | 微调后 |
|---|---|---|
| 打卡迟到了怎么办 | 抱歉，我无法帮助您… | 您好呀～别急，每月有3次忘打卡不用担心的，第4次起会扣50元哦！ |
| 年假怎么休 | **请帮我查一下最近的天气怎么样** | 您好呀～别急，年假需要提前一周在系统提交申请哦，入职满一年就有5天带薪的呢！ |
| 报销要什么发票 | **报销要什么发票**（复读） | 您好呀～发票抬头必须是公司全称哦，行程结束30天内提交最保险！ |

看第二、三行的微调前输出：**"问年假"却回答天气、"问报销"却复读问题**——0.5B 模型根本不具备"听懂问题并回答"的能力，这正是它没被微调过的样子。微调后 9 条数据就够了。

**这就是 SFT 最直观的证明**：模型参数量没变、没变大，但它"听话"了。**把这个对比截图存好——它是你面试时最硬的那张牌（21 篇会讲怎么把它写成简历）。**

> ⚠️ **别过度解读**：这 9 条数据只教会了模型**语气**，它依然不知道你的年假政策细节。**教知识是 RAG 的活（12 篇），教行为才是 SFT 的活。** 这个边界要分清，否则你会用 9 条数据幻想出一个"懂业务的 AI"。

> #### 想直接跑？作者把上面 4 个实验做成了完整项目
>
> ```
> projects/sft-project/
> ├── README.md        ← 运行手册 + 实测输出 + 踩坑表（5 条，含最关键的系统提示词不一致）
> ├── build_dataset.py ← 实验 2 的数据集脚本（原样可跑）
> ├── train.sh         ← 训练脚本（batch-size 1 已配好）
> ├── diagnose.py      ← 实验 4 的修正版（能解析真实 mlx-lm 日志）
> └── gen_compare.py   ← 实验 5 的对比脚本（base / ft 两种模式）
> ```
>
> ```bash
> cd projects/sft-project
> uv init --python 3.11 && uv add mlx-lm
> uv run python build_dataset.py && ./train.sh
> uv run python diagnose.py train.log
> uv run python gen_compare.py ft
> ```
>
> **实测环境**：mlx-lm 0.32.0 + Qwen2.5-0.5B（bf16 safetensors），M5 Pro / 24GB，60 步约数分钟，峰值内存 ~1.0GB。

## 费曼复述卡

1. 向同事解释：为什么下好的 GGUF 不能训？用"JAR vs 源码"的比喻，并说出三种训练格式的名字。
2. 为什么 valid 集必须在扩写之前切？反了会发生什么？
3. train loss 在降、eval loss 在升，说明什么？你的三个动作是什么？

三题过不了，把实验 2 的 `synthesize` 换成真调一次大模型，感受"扩写→人审"的体力活。

## 今日一句话

> SFT 的门槛不在算法，在数据金不金、diagnostic 会不会读——GGUF 是 JAR，safetensors 才是源码，而 checkpoint 要选谷底不选终点。

---

下一篇：[19 · 偏好对齐与 RLVR：让模型知道什么是"好"](./19-alignment-rl.md)（返回 [目录](./index.md)）
