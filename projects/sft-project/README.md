# SFT 最小实现：让 0.5B 小模型学会你的客服语气

> 配套《Java 到 AI 的 90 天》第 18 篇 · **作者已实测跑通**（2026-10-12，Apple M5 Pro / 24GB）

## 这是什么

用 **9 条数据**（8 训练 + 1 验证）在 **Qwen2.5-0.5B** 上跑一次真实的 LoRA 微调，看一个"连话都说不完整"的小模型，是怎么在一分钟里学会你家客服的话术的。

**不用 GPU，不用 API key，不花钱。** 全部在你自己电脑上完成。

## 效果（作者的实测对照）

**微调前**（同一个问题）：

```
Q: 打卡迟到了怎么办
A: 抱歉，我无法帮助您。请告诉我您需要帮助的事项，我会尽力为您提供帮助。

Q: 年假怎么休
A: 请帮我查一下最近的天气怎么样          ← 答非所问

Q: 报销要什么发票
A: 报销要什么发票                        ← 复读
```

**微调后**：

```
Q: 打卡迟到了怎么办
A: 您好呀～别急，每月有3次忘打卡不用担心的，第4次起会扣50元哦！

Q: 年假怎么休
A: 您好呀～别急，年假需要提前一周在系统提交申请哦，入职满一年就有5天带薪的呢！

Q: 报销要什么发票
A: 您好呀～发票抬头必须是公司全称哦，行程结束30天内提交最保险！
```

**这就是 SFT 最直观的证明**：模型权重没变大、参数量没变，但它"听话"了。

## 训练实测数据

```
iter   train_loss     tok/s     tokens
  1    val 6.443      1.37s
 10    4.016 ▼         71      0.6k
 20    1.380 ▼       1,792      1.3k
 30    0.880 ▼       1,794      1.9k
 40    val 0.780      0.02s
 60    0.737 ▼       1,786      3.8k

Trainable parameters: 0.594% (2.933M/494.033M)
峰值内存: ~1.0 GB ｜ 60 步耗时: 数分钟
```

**注意 loss 从 6.443 一路降到 0.777**——这就是 18 篇讲的"loss 曲线往下走"，现在它是你自己机器上的真实数字。

## 运行

### 前置条件

- Apple Silicon Mac（作者实测 M5 Pro / 24GB；8GB 也能跑）
- Python 3.10+（用 uv）
- 已下载的模型（见下）

### 步骤

```bash
# 1. 环境
uv init --python 3.11
uv add mlx-lm

# 2. 准备模型（二选一）
#    A. 用已有的（改成本地路径）
export MODEL=$(echo ~/.cache/huggingface/hub/models--Qwen--Qwen2.5-0.5B/snapshots/*/)
#    B. 现下载（需要网络）
# uv run huggingface-cli download Qwen/Qwen2.5-0.5B && export MODEL=Qwen/Qwen2.5-0.5B

# 3. 造数据（8 train + 1 valid，自带污染自检）
uv run python build_dataset.py

# 4. 训练（60 步，日志留档）
./train.sh

# 5. 读 loss 曲线（自动诊断是否过拟合）
uv run python diagnose.py train.log

# 6. 前后对比
uv run python gen_compare.py base    # 微调前
uv run python gen_compare.py ft      # 微调后（带 adapter）
```

## 作者踩过的坑（别再踩）

| 坑 | 现象 | 解法 |
|---|---|---|
| **valid 数据太少** | `ValueError: Dataset must have at least batch_size=4 examples but only has 1` | 加 `--batch-size 1`，或把数据扩到 10 条以上 |
| **生成时 system 不一致** | 输出乱码/胡言 | **训练和生成的 system prompt 必须逐字一致**（见下方代码注释） |
| **API 参数名** | `generate() got unexpected keyword 'temp'` | 用 `make_sampler(temp=0.0)`，不是 `temp=0.0` |
| **默认 chat template 污染** | 生成的 prompt 里混入 `You are a helpful assistant.` | 手动拼 `system\n...\nuser\n...\nassistant\n`，别用 `--use-default-chat-template` |
| **日志有 ANSI 颜色码** | 正则解析 loss 失败 | 先 `re.sub(r"\x1b\[[0-9;]*m", "", line)` 剥掉 |

### 最关键的一个坑（值得单独强调）

微调后如果输出乱码或胡言，**99% 是训练和生成时的 prompt 模板不一致**。

训练时 mlx-lm 把你的 `messages` 渲染成：

```
system
你是米宝公司的客服助手，语气亲切可爱，句末常用波浪号～
user
打卡迟到了怎么办
assistant
您好呀～...
```

那生成时就必须**一字不差地复刻**这个格式（本项目的 `gen_compare.py` 就是这么做的）。用 `--use-default-chat-template` 会让 mlx-lm 插入它自己的默认 system，导致模型看到"没见过的开场白"，输出直接崩。

## 文件说明

- `build_dataset.py` — 数据流水线（种子→扩写→切分→污染自检）
- `train.sh` — 训练脚本（batch-size 1 已在脚本里配好）
- `diagnose.py` — 解析 loss 日志，判断过拟合（已按真实日志格式修正）
- `gen_compare.py` — 微调前后对比生成（`base` / `ft` 两个模式）

## 关于数据量：9 条够学风格，不够学知识

本项目用 **9 条**数据，是因为要让你在几分钟内看到完整流程。**真实的风格微调建议 200~2000 条**（18 篇讲过：300 条能看到效果，3000 条能上线）。

**但注意**：这 9 条数据能教会模型"语气"，教不了它"知识"。它现在依然不知道你的年假政策细节——**那是 RAG 的活（12 篇），不是 SFT 的活。**

## 清理

```bash
rm -rf adapters train.log      # adapter 几十 MB，不用了就删
```