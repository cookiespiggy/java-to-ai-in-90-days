# 企业知识库 RAG 最小实现

> 配套《Java 到 AI 的 90 天》第 13 篇 · **作者已实测跑通**（2026-10-12，Apple M5 Pro / pgvector 0.8.2 / PG 17.10）
>
> 实测分两轮：**检索层**用云端 embedding（0.136s/条）；**生成层默认走本地模型**（Unsloth Studio 的 Qwen3.5-4B-GGUF），全程不需要任何 DeepSeek 账号或余额。

## 这是什么

一个能在自己电脑上跑起来的"问公司制度"助手：文档灌进向量库 → 问题变向量 → pgvector 找最相关的几段 → 带着资料问大模型 → 返回带引用的答案。

**五个文件，三条命令，零框架**（只用 `openai` SDK + `psycopg`），刻意不用 LangChain——先看懂每一根管子，再上框架（15 篇）。

**生成层支持云端 / 本地双模式**，一个环境变量切换，业务代码零改动。

## 前置条件

- Python 3.10+（用 `uv` 管理）
- Docker / OrbStack / Colima 任一容器运行时
- embedding key：**阿里百炼**或硅基流动（检索必需，1 条 key）
- 生成层：**本地模型**（推荐，零成本）或云端 API key（二选一）

> embedding 建议走云端，因为小模型算 embedding 质量普遍不行；但**生成层完全本地就够了**，这一步最容易被误判成"必须付费"。

## 运行

```bash
# 1. 起数据库
docker run -d --name rag-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 pgvector/pgvector:pg17

# 2. 配 key
cp .env.example .env && chmod 600 .env
# 编辑 .env：至少填 AI_DASHSCOPE_API_KEY

# 3. 装依赖并跑
uv init --python 3.11 && uv add "psycopg[binary]" openai python-dotenv
uv run python schema.py     # 建表
uv run python ingest.py     # 灌入 6 篇制度文档（幂等，可重复跑）
uv run python query.py      # 提问 + 跑评测集
```

### 生成层：本地还是云端？

`.env` 里一行切换：

```bash
LLM_BACKEND=local   # 默认：本地模型，零成本、数据不出内网
LLM_BACKEND=api     # 云端大模型，没有能跑的本地内存时用
```

先自检连通性（切完模式第一件事跑这个）：

```bash
uv run python llm_backend.py
# ✅ 后端=local 可用，模型: ['unsloth/Qwen3.5-4B-GGUF']
# ❌ 后端=local 连不上: ConnectionError: ...   ← 本地推理服务没起
```

#### local 模式：方案 A — Unsloth Studio（作者实测的就是这个）

装了 Unsloth 桌面版，它**自带一个 llama-server**，本身就是 OpenAI 兼容服务，不用额外写任何代码：

```bash
# 1) 在 Unsloth Studio 界面里点开你的 GGUF 模型（服务会自动起）
# 2) 端口在界面里能看到，作者机器是 53967
# 3) key 在这个文件里：
cat ~/.unsloth/studio/auth/llama_api_key_*    # 前缀 llama_api_key_

# 4) 填进 .env
LOCAL_BASE_URL=http://127.0.0.1:53967/v1
LOCAL_KEY=<上一步 cat 出来的值>
LOCAL_MODEL=unsloth/Qwen3.5-4B-GGUF          # = 服务 /v1/models 里返回的 name
```

模型名必须和 `/v1/models` 返回的**完全一致**（GGUF 模型带 `unsloth/` 前缀，容易写错）：

```bash
curl -s -H "Authorization: Bearer $LOCAL_KEY" "$LOCAL_BASE_URL/models" | python3 -m json.tool
```

#### local 模式：方案 B — oMLX（Apple Silicon 首选，MLX 格式）

```bash
pip install omlx
omlx serve --model-dir ~/.omlx/models --port 8000 --memory-guard safe
# .env
LOCAL_BASE_URL=http://127.0.0.1:8000/v1
LOCAL_KEY=EMPTY                                   # oMLX 默认不校验，但字段必须存在
LOCAL_MODEL=Qwen2.5-0.5B                          # = ~/.omlx/models 下的目录名
```

**格式坑（作者踩过）**：oMLX 只吃 `config.json` + `*.safetensors` 的 **MLX 格式**，GGUF 喂不进去。想要 4B 效果就得下对应的 MLX 版本，不是把 GGUF 改名。

**内存坑**：oMLX 有 memory-guard，模型装不下会**主动拒绝**而不是卡死：

```
Error code: 507 - Model 'Qwen3.5-9B-MLX-4bit' (5.82GB) does not fit under
the dynamic memory ceiling (4.59GB). Close other apps to free RAM
(static cap is 16.00GB but only 4.31GB is reclaimable right now)
```

调档：`--memory-guard safe → balanced → aggressive`。但作者机器实测 aggressive 也拦住了 9B——**先算模型大小 vs 可用内存，再选模型**（第 23 篇）。

**模型不能太小**：0.5B 跑 RAG 问答会输出日文乱码（作者实测：`lijkeや。食堂の価格は…`），检索完全正常但生成全废。RAG 生成至少 4B 起，7B 更稳。

#### api 模式

```bash
LLM_BACKEND=api
DEEPSEEK_API_KEY=sk-xxx     # 任何 OpenAI 兼容服务都行，改 llm_backend.py 里的 base_url
```

⚠️ 云端余额不足会直接 `402 Insufficient Balance` 挂掉，作者第一次就踩了（见 13 篇"生成管道只验证到 Mock"那段）。**默认用 local 就没这个问题。**

## 作者的实测输出（你可以对照自己的）

**检索层**（pgvector 0.8.2 + PG 17.10 + text-embedding-v3，阈值 0.60）：

```
年假怎么休？          → 员工手册-年假     score=0.747  165ms ✓
住院了工资怎么算？     → 员工手册-病假     score=0.721  159ms ✓
出差发票有什么要求？    → 员工手册-报销     score=0.741  106ms ✓
迟到扣钱吗？          → 员工手册-考勤     score=0.688  164ms ✓
食堂有夜宵吗？         → 员工手册-食堂     score=0.713   93ms ✓
出差住宿多少钱一晚？    → 员工手册-差旅住宿  score=0.799  149ms ✓
公司健身房几点开？     → 员工手册-考勤     score=0.595  116ms ✓ 已拦截（低于 0.60）
──────────────────────────────────────────────────────
top1 命中率 7/7 ｜ 平均检索延迟 136ms
```

**生成层（本地 Unsloth Qwen3.5-4B-GGUF，零 DeepSeek）**：

```
后端模式: local  模型: unsloth/Qwen3.5-4B-GGUF

Q: 我入职三年了，年假几天？
A: 根据资料，入职满一年享有 5 天带薪年假，满十年 10 天，满十五年 15 天。
   您入职三年，属于"入职满一年"但未达到"满十年"的区间，因此享有 5 天带薪年假。
   [1200ms]

Q: 出差住酒店超标了能报吗？
A: 根据资料，出差住酒店超标不能全额报销。
   1. 超标部分由个人承担：即超标金额需员工自付，公司不予报销。
   2. 特殊情况需事前审批：只有在事前获得审批的特...
   [2267ms]

Q: 公司食堂周三有小龙虾吗？
A: 资料未提及
   [320ms]
```

第三个问题是故意设计的陷阱——资料里只写了"周四固定有小龙虾"。4B 本地模型**没有顺着问编周三**，阈值拦截 + 拒答模板双保险。这就是 RAG 防幻觉的实际价值。

## 踩坑记录（作者真实踩过的，别再踩）

| 坑 | 现象 | 解法 |
|---|---|---|
| **默认就得买 DeepSeek** | 以为 RAG 必须付费 API | 生成层切 `LLM_BACKEND=local`，本地 4B 完全够用 |
| **模块级读 env 拿到旧值** | 改了 `.env` 却仍走旧后端 | 惰性求值 + `llm_backend.py` 内部自己 `load_dotenv()`（import 时机早于调用方） |
| **env 变量名对不上** | 照抄 `.env.example` 直接 KeyError | 示例里写的就是代码读的 `AI_DASHSCOPE_API_KEY`，别自己改名字 |
| **oMLX 喂 GGUF** | 加载失败 | oMLX 只吃 MLX safetensors 格式 |
| **模型太小输出乱码** | 0.5B 答出日文 | RAG 生成至少 4B |
| **模型太大被 507 拦** | `does not fit under the dynamic memory ceiling` | 调 `--memory-guard` 或换小模型，先算内存 |
| **Docker context 指错** | `Cannot connect to the Docker daemon` | `docker context ls` 看看用的哪套 |
| **镜像拉不下来** | `TLS handshake timeout` | 先 `docker images \| grep pgvector` 看本地有没有 |
| **向量传参报错** | psycopg3 对 Python list 适配不稳 | 转字符串字面量 + `%s::vector`（`query.py` 里的 `lit`） |
| **阈值抄 0.35 幻觉** | 不在库的问题也拿到 0.5+ | **用自己的评测集扫阈值**，见下 |

## 关于阈值：本书最重要的一条实测教训

真实 embedding 的相似度分布**远高于**玩具版：

| 类别 | top1 分数区间 |
|---|---|
| 在库问题 | 0.688 ~ 0.799 |
| 不在库问题 | 0.406 ~ 0.595 |

| 阈值 | 保留在库 | 误收不在库 |
|---|---|---|
| **0.60（本项目采用）** | **6/6** | **0/3** |
| 0.35（常见默认值） | 6/6 | **3/3 全误收** |

**换语料、换 embedding 模型，这个数就要重扫。** 方法见第 16 篇评测、第 21 篇工程化。

## 收工

```bash
# 数据库
docker stop rag-pg        # 停止但保留数据
docker rm -f rag-pg       # 彻底删除
lsof -ti:5432             # 确认端口已释放

# 本地推理服务
omlx stop                 # oMLX（自己起的才需要停）
# Unsloth Studio 自带的 llama-server：在界面里停掉模型即可
lsof -ti:8000
```

⚠️ `lsof -ti:8000` 看到进程先别急着杀——**确认那是你自己起的**，Unsloth Studio 也在用 `llama-server`，误杀会打断你正在跑的模型。

## 文件说明

- `schema.py` — 建 pgvector 扩展和 `doc_chunks` 表（重复跑安全）
- `ingest.py` — 结构感知分块 + embedding + 幂等入库（先 DELETE 再 INSERT）
- `llm_backend.py` — **云端/本地双模式适配层**，`chat()` 是统一入口，带 `health()` 自检
- `query.py` — 检索（含阈值拦截）+ 问答 + 评测集，一次跑完