# 23 · 本地推理闭环：oMLX、unsloth 与 MLX 的三人舞

## 先讲给朋友听（如果你只有一分钟）

> 你有三件武器：**MLX**（苹果官方的推理/训练框架）、**oMLX**（套在 MLX 上的生产级服务器，带连续批处理和分层 KV 缓存）、**unsloth**（把训练速度拉两倍、显存砍七成的加速库）。三者拼起来，就是一台 24G MacBook 上的完整 AI 工作站——**而且全部兼容 OpenAI 协议，你的业务代码零改动。**

## 你的 Aha Moment

先看作者机器上的真实配置（M5 Pro / 24G）：

```bash
$ ls ~/.omlx/models/
Qwen2.5-Coder-14B-Instruct-MLX-4bit
Qwen3-Coder-30B-A3B-Instruct-MLX-4bit
Qwen3.5-9B-MLX-4bit
```

**一台笔记本，本地躺着三个能写代码的模型。** 而 `omlx` 这个命令的真实能力（`--help` 实测，版本 0.7.0rc1）：

```
usage: cli.py [-h] {start,stop,restart,serve,launch,diagnose,cluster} ...

omlx: Production-ready LLM server for Apple Silicon
```

再看它的两个杀手级参数：

- `--model-dir`（默认 `~/.omlx/models`）——**多模型同时驻留 + LRU 淘汰**，内存不够时自动卸最久没用的
- `--hot-cache-max-size` / `--paged-ssd-cache-dir`——**KV 缓存分两层：内存热层 + SSD 冷层**，而且**跨请求持久化**。这意味着第二问相似问题时，上下文不用重算

以及最让 Java 工程师会心一笑的那个：

```bash
omlx launch opencode --model qwen3.5
```

**它能把你的本地模型喂给 Claude Code / Codex / OpenCode / OpenClaw 这些编程智能体**（`--tools-profile minimal|coding|messaging|full`，还能给 opus/sonnet/haiku 三档配不同模型）。翻译一下：**你本地的 30B-A3B 可以当你的"廉价代打"，写 boilerplate 用它，架构难的再调 API。**

Aha 合龙：**本地推理从来不是"穷人的替代品"，它是一条独立的部署路线**——数据不出内网、没有按 token 的计费单、延迟可控。而 OpenAI 兼容协议（11 篇学的）让这一切对你的代码完全透明。

## 不讲术语的版本：三个组件，一人一步

**分工，一句话讲清：**

| 组件 | 角色 | 你什么时候用它 |
|---|---|---|
| **MLX / mlx-lm** | 苹果官方的框架（跑模型 + 微调） | 底层，一般不直接碰 |
| **oMLX** | 包在 MLX 外的生产服务器 | 要对外提供 API 时用它 |
| **unsloth** | 训练加速库（2x 快、70% 省显存） | 要微调模型时用它 |

**一次完整的"本地闭环"长这样：**

```
① unsloth/mlx-lm 微调出一个 adapter（18 篇）
        ↓
② 合并 + 量化成 MLX 4bit，放进 ~/.omlx/models/qwen-mibao/
        ↓
③ omlx serve 起服务（OpenAI 兼容，多模型驻留）
        ↓
④ 你的业务代码：base_url 指向 http://127.0.0.1:8000/v1（11 篇零改动）
        ↓
⑤ 进阶：omlx launch 把本地模型喂给你的编程 Agent
```

**四个你一定会遇到的坑，先垫在这里：**

1. **oMLX 不吃 GGUF。** 它的 `--model-dir` 要求子目录里有 `config.json` + `*.safetensors`（MLX 格式）。你手里那个 `Qwen3.5-4B-UD-Q4_K_XL.gguf` 得先转成 MLX 格式。**GGUF 是 llama.cpp 的世界，MLX 是苹果的世界，两个宇宙。**

   > 为什么 GGUF 到处都不受欢迎？**因为它是后训练流程的终点，不是起点**——`safetensors → 训练 → fuse → 量化 → GGUF`，GGUF 只能挂在最后一环。18 篇有 unsloth 源码级的完整解释。

2. **训练和推理是两个模型文件。** 微调出来的 adapter 可以"挂载"使用，但生产上更稳的做法是 merge 进基座再量化。**发布物和训练物分开**，跟你 Java 的"源码仓库 vs 制品仓库"一个道理。

3. **多模型 LRU 的内存保护。** `--memory-guard {off,safe,balanced,aggressive}` 四档，24G 机器建议 `safe` 起步——它会在触顶前主动卸载模型，而不是让系统开始 swap（swap 到 SSD 上，推理速度慢一个数量级）。

4. **tokenizer 的坑。** MLX 4bit 模型是重新量化的，和原版 tokenizer 若有细微差别，会出现"同一个 prompt 两种编码"。选模型时认准 `mlx-community` 或官方发布的版本，别自己转。

## Java 老司机对照室

| oMLX/MLX 概念 | 你已经懂的概念 | 一句话翻译 |
|---|---|---|
| `~/.omlx/models/<name>/` | Tomcat 的 webapps 目录 | 一人一个子目录=一个应用 |
| 多模型驻留 + LRU | 连接池 / 对象池 | 常驻内存的按需淘汰 |
| 内存热层 + SSD 冷层 | 堆内缓存 + 堆外/磁盘缓存 | 两级缓存，跨请求生效 |
| KV Cache 持久化 | 预计算结果缓存 | 上下文越长收益越大 |
| OpenAI 兼容 API | REST 接口标准化 | 换后端不改业务代码 |
| `omlx launch opencode` | 把内部 SDK 注入外部工具 | 本地模型冒充 OpenAI |
| `--tools-profile` | 按环境开关功能集 | 最小权限给最小场景 |
| `--api-key` / 127.0.0.1 | 仅监听本地 + 鉴权 | 默认只给自己用，别裸奔 |
| `--memory-guard` | JVM 的 -Xmx + GC 策略 | 触顶前主动让，别等 OOM |
| `omlx diagnose` | 健康检查端点 | 出问题先跑它 |

## 动手实验室

以下命令全部对着作者的 M5 Pro / 24G 实测过（oMLX 0.7.0rc1），你可以逐条对照。

### 实验 1：体检——你的机器有几件武器

```bash
which omlx && omlx --version          # 0.7.0rc1
ls ~/.omlx/models                     # 已装模型（一人一个目录）
ls ~/.cache/huggingface/hub/          # HF 缓存（训练基座的来源）

# 每件武器占多少内存
du -shL ~/.omlx/models/*
```

**作者机器上的真实清单**（M5 Pro / 24GB）：

| 模型 | 格式 | 大小 | 能训？ | 能推理？ |
|---|---|---|---|---|
| `Qwen2.5-0.5B` | safetensors (bf16) | 942M | ✅ | ✅ |
| `Qwen3.5-0.8B-Base` | safetensors | 3.3G | ✅ | ✅ |
| `Qwen3.5-4B-GGUF` | GGUF (Q4_K_XL) | 6.7G | ❌ | ✅ |
| `Qwen3.5-9B-MLX-4bit` | MLX 4bit | ~5.5G | ✅ | ✅ |
| `Qwen2.5-Coder-14B-MLX-4bit` | MLX 4bit | ~8G | ✅ | ✅ |
| `Qwen3-Coder-30B-A3B-MLX-4bit` | MLX 4bit（MoE 混合专家架构） | ~18G | ✅ | ✅ |

### 实验 2：起服务（三步，全程不写代码）

```bash
# 1. 起 OpenAI 兼容服务（默认只监听 127.0.0.1:8000）
omlx serve --model-dir ~/.omlx/models --port 8000 \
           --memory-guard safe \
           --hot-cache-max-size 4G

# 2. 换个终端，用 curl 验证（格式和第 11 篇一模一样）
# 注意：oMLX 默认开启 API key 鉴权（连本地都不例外），key 在 ~/.omlx/settings.json 里
OMLX_KEY=$(python3 -c "import json; print(json.load(open('$HOME/.omlx/settings.json'))['auth']['api_key'])")

curl http://127.0.0.1:8000/v1/models \
  -H "Authorization: Bearer $OMLX_KEY" | python3 -m json.tool

curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $OMLX_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2.5-0.5B",
    "messages": [{"role": "user", "content": "用一句话解释什么是 KV Cache"}],
    "stream": false
  }'
```

**注意 `"model"` 填的是目录名**（`Qwen2.5-0.5B`），不是 HF 上的 repo id。这是 oMLX 的规矩：**目录名即模型 ID。**

**实测数据**（M5 Pro / 24GB，Qwen2.5-0.5B，2026-10-12）：

| 指标 | 实测值 |
|---|---|
| 模型加载后实际内存 | **1.12 GB**（日志 `actual: 1.12GB`） |
| 非流式吞吐 | **31.4 tok/s**（60 token / 1.91s） |
| 流式吞吐 | **193.8 tok/s**（17 token / 0.13s，含 KV 缓存命中） |
| 模型结构 | 24 层 / 2 KV heads / 14 Q heads / 64 head_dim |
| 首 token 延迟（TTFT） | **0.04s** |
| 内存天花板（safe 档） | **7.2 GB**（`Process memory enforcer` 自动执行） |
| 模型结构 | 24 层 / 2 KV heads / 14 Q heads / 64 head_dim |

**一个真实发现**：0.5B 模型输出末尾出现了乱码（泰文碎片）。这不是 API 问题，是**小模型的能力天花板**——正是 17-19 篇后训练要解决的事。

### 实验 3：业务代码零改动（第 11 篇的封神时刻）

```python
import os
os.environ["DEEPSEEK_API_KEY"] = "EMPTY"      # 本地服务不校验

# 只改这两个环境变量/字段，11 篇的全部代码原样工作
BASE_URL = "http://127.0.0.1:8000/v1"
MODEL    = "Qwen2.5-0.5B"          # 你机器上能跑的最小可对话模型
API_KEY  = "EMPTY"                 # 本地服务不校验；填你 ~/.omlx/settings.json 里的真实值亦可
```

**选型原则：先看你能给多少内存，再选模型。** 作者机器 24GB 统一内存，日常还有别的任务在跑（实测可用仅 6.2GB），所以 9B（~5.5G）虽然能加载但会触发 swap，0.5B（~1.1G）才是日常能用的选择。**这不是"9B 不好"，是"你的机器现在跑不动 9B"。**

**流式输出、`asyncio.gather` 并发三问、`@retry` 退避重试，全部原样能跑。** 这就是 OpenAI 兼容协议的红利——上游从 DeepSeek 换成你家那台 MacBook，对业务代码是一次环境变量切换。

### 实验 4：把本地模型喂给编程 Agent（本篇最酷的一步）

```bash
# 让 OpenCode 用你本地的 Qwen2.5-0.5B 当它的大脑
omlx launch opencode --model Qwen2.5-0.5B \
                     --tools-profile coding

# 或者更激进的：三档分工，便宜活给本地，难活给 API
omlx launch codex --model Qwen2.5-0.5B \
                  --haiku Qwen2.5-0.5B \
                  --sonnet deepseek-chat \
                  --opus deepseek-chat
```

第二条命令值得多看两眼：**haiku 档（琐碎活）走本地免费模型，sonnet/opus 档（难活）走 API。** 这是 2026 年本地推理最现实的生态位——不是取代 API，是**把 API 的账单拦掉 80% 的琐碎请求**。

### 实验 5：微调 → 部署的完整闭环

```bash
# ① 微调（18 篇的产物）
uv run python -m mlx_lm.lora --model <基座> --train --data ./data --iters 600

# ② 把 adapter 合并回基座并量化成 4bit（发布物与训练物分离）
uv run python -m mlx_lm.fuse --model <基座> \
                                --adapter-path ./adapters/mibao-style \
                                --save-path ~/.omlx/models/qwen-mibao
# 注意：fuse 后的目录结构必须满足 oMLX 要求（config.json + *.safetensors）

# ③ 重启服务，新模型立即可用
omlx restart
curl http://127.0.0.1:8000/v1/models | python3 -m json.tool    # 确认 qwen-mibao 在列表里

# ④ 跑一遍 16 篇评测集，对比微调前后（这才是发布闸门）
```

**四步走完，你拥有了一个业务专属的本地模型，且和云 API 一样好用。** 第 ⑤ 步别省——没有评测集背书的部署，跟闭眼上线没区别。

## 回头看：13 篇的 RAG 现在可以不花钱了

本篇把本地推理讲完了，但有个疑问很容易被忽略：**"我本地跑起模型了，那事前那个 RAG 项目也要重新花钱么？"**

不用。回去看 13 篇实验 3.5：

```bash
LLM_BACKEND=local
LOCAL_BASE_URL=http://127.0.0.1:53967/v1
LOCAL_MODEL=unsloth/Qwen3.5-4B-GGUF
```

三行配置，13 篇的问答就跑在你本地模型上了。作者实测：

```
Q: 我入职三年了，年假几天？
A: 根据资料，入职满一年享有 5 天带薪年假...   [672ms]

Q: 公司食堂周三有小龙虾吗？
A: 资料未提及                                    （正确拒答）   [229ms]
```

**推理 0.2~0.8 秒，零 API 费用。**

### 两篇之间的真实关系

这里有一条很值得单独说的线索，因为很多人学业的时候会把它当成两个独立主题：

```
本地推理（23 篇）   →  怎么把模型跑起来？
                            ↓
                  都是 OpenAI 兼容协议
                            ↓
业务管道（13 篇 RAG）   →  怎么把模型接进业务？
```

**中间那个共识（OpenAI 兼容协议）才是真正的类型。** 它让“怎么跑”和“怎么用”可以分开学习，
也让你在两个场景之间切换的代价小到只是改一行配置。

> 反过来看：如果本地推理选的是自己写的专有协议（不是 OpenAI 兼容的），
> 那 13 篇就得重写一遍生成层。**选技术方案时要看的不是"它优不优"，而是"我升级环境时能不能整个系统换掉"。**

### 一个真实的选型决策表

新手常问的“本地那么好，云端那么好，我该选哪个？”——不要回答“看情况”，照着这张表选：

| 场景 | 选择 | 理由 |
|---|---|---|
| 学习 / 试验 | **本地** | 零成本，错了随手重启，不拥拥你的 API 钱 |
| HR / 金融等内部查询 | **本地** | 员工信息不出内网，审合规这条很重要 |
| 客服 / 多轮对话 | **云端** | 4B 的长程记忆和复杂推理明显不够，而且会话里容易混权 |
| 上线前负载高 | **云端** | 并发冲刺时本地单机很容易打满 |

**结论：默认本地，按场景切云端。** 这也是 13 篇 `llm_backend.py` 默认设 `local` 的原因——
**它不只是个配置默认值，它是一个已经被实测验证过的工程决策。**

## 费曼复述卡

1. 向同事解释：为什么说"本地推理不是穷人的替代品，而是一条独立部署路线"？从数据、成本、延迟三个角度说。
2. oMLX 为什么不吃 GGUF？它要的目录结构长什么样？
3. `omlx launch codex --haiku <本地模型> --opus <API>` 这个分工解决了什么商业问题？

三题过不了，把实验 2 的 curl 换成 11 篇的 Python 客户端真跑一遍。

## 今日一句话

> MLX 是引擎，oMLX 是整车，unsloth 是改装厂——三者在你的 24G MacBook 上拼出一台完整工作站，而且全部对 OpenAI 协议敞开。

---

下一篇：[24 · 部署：vLLM 与推理优化](./24-serving.md)（返回 [目录](./index.md)）
