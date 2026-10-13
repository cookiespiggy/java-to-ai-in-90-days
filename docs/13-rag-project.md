# 13 · 实战：搭一个会读公司文档的助手

## 先讲给朋友听（如果你只有一分钟）

> 上一篇的 RAG 是纸飞机，这一篇是造飞机。同样的六工位，每一个都换成工业件：文档切块上流水线，embedding 模型负责把段落变成真实向量，pgvector 负责百万级向量检索——而你的 SQL 基本功，在这里突然变得极其值钱。

## 你的 Aha Moment

先立一个工程判断，这是本篇的魂：

**上 RAG 项目，先别碰 LangChain。**

对，就是那个刷屏的框架。理由有三，你听完大概率会同意：

1. **你刚在 12 篇手搓过内核**——裸装版你能看清每一根管子；先框架后原理的人，调 bug 时连"检索结果从哪来的"都追不到
2. **Java 老工程师的尊严就是拆得动机理**——你的知识结构是自底向上的，LangChain 这种自顶向下设计出来的抽象，对你恰恰是理解负担
3. **企业里 RAG 最难的不是搭 pipeline，是调优**——召回率上不去、切块切烂了、embedding 不适配中文——这些坑，框架只会替你藏得更深

所以本篇的架构：**只用两个库**——`openai`（调 embedding + 对话）和 `psycopg`（连数据库）。数据存 pgvector（PostgreSQL 的向量插件）。

**而这个选型本身，就是你的 Aha：**

| 传统方案 | 本 |
|---|---|
| 新上一个 Milvus/ES 集群 | 装 pgvector 插件，**一个 PG 全搞定** |
| 向量库和业务库两地同步 | 同样的表，SQL join 直接查 |
| 学一套新 DSL | `ORDER BY embedding <=> %s LIMIT 5` |
| 运维加一份 K8s spec | 你的 PG 备份/监控/权限体系原样复用 |

**你做了十年的数据库运维经验，在 AI 管道里不仅没过期，还直接免掉了一整个中间件。** 这就是"老本行"兑现的实感——**PG + pgvector 在建了 HNSW 索引后单表撑千万级向量完全可行**，中小公司的文档问答根本用不着专用向量库。（注意"建了索引"这个前提，见下面决策 3 的口径。）

## 不讲术语的版本：装配一台真机器

架构图（ASCII 省流版）：

```
            ┌──────────── 离线上库（一次性）────────────┐
目录/PDF/飞书 │→ loader 抽取文本 → 按标题分块 → BGE 向量化 │
            └──────────────────┬──────────────────────┘
                               ▼
                    pgvector 表（id, content, embedding, source）

            ┌──────────── 在线问答（每次）────────────┐
用户提问 → 同一个模型把问题向量化 → SQL 最近邻 top5 → 拼 Prompt → LLM 流式回答
```

四个关键决策，每个给你"为什么"：

**决策 1 · Embedding 模型选 BGE-M3。**

中文开源圈子里口碑最好的一个（智源出品，Apache 2.0 可商用）：中英文混合能力强、支持 8192 长文本、多语言检索一把抓。**别用 OpenAI 的 text-embedding-ada——中文场景它性价比和效果都不行**，这是国内团队的集体踩坑结论。

获取方式两条路：本地部署（`uv add FlagEmbedding`，有 GPU 才顺）或走 API（阿里百炼/硅基流动都有 OpenAI 兼容的 embedding 端点，零本地开销）。**本篇教程用 API 模式**——你的 Mac 24G 内存跑得动，但 API 更省心。

**决策 2 · 分块按文档结构，不按固定字数。**

员工手册这种有明确标题层级的文档，按"章/节"天然成块最干净；无结构的纯文本才退回 512 token + 10% 重叠。**切块是 RAG 的第一深坑：切太碎丢上下文，切太大稀释语义**——12 篇说过，这里再钉一次。

**决策 3 · pgvector 索引类型，十万行以下不建。**

暴力精确检索够快了；上量再建 IVFFlat 或 HNSW 索引（内存换召回速度）。**别一上来就建索引**——小数据量上是负优化，跟你给查询加了个用不上的位图索引一个道理。

**决策 4 · 检索 SQL 用余弦距离 `<=>`。**

pgvector 支持三种距离算子，embedding 模型页面会标推荐哪一种，BGE 系列认准 `<=>`（余弦）。细节错一次，召回率能掉两成——这种bug最阴，因为"能跑"。

## Java 老司机对照室

| RAG 工业件 | Java 老本行 | 一句话翻译 |
|---|---|---|
| pgvector | PG 插件如 PostGIS | 数据库生态的插件化install |
| vector(1024) 列 | BLOB 特化列类型 | 定长向量，索引友好 |
| `ORDER BY emb <=> q LIMIT k` | 带排序的翻页 SQL | kNN 查询，仅此而已 |
| HNSW / IVFFlat | B-Tree / 位图索引 | 近似最近邻，牺牲精度换速度 |
| embedding API | 远程特征服务 | HTTP 调用，结果缓存 |
| 分块 + 元数据表 | ETL 清洗入仓 | 文档表 + chunk 表一张 schema |
| LangChain/LlamaIndex | Spring 式全家桶框架 | 本篇先不引入，看裸装 |

最后一行是教学立场，不是宗教立场——**看懂裸装之后，框架自然是你的效率工具**，15 篇的 LangGraph 会请回框架，届时你会庆幸今天打过这套底。

## 动手实验室

### 实验 0：环境三件套（含完整启动/停止流程）

> ⚠️ **先读这段**：作者实测时踩了三个坑（镜像拉不下来、docker context 指错、端口被占）。下面把**每一步的验证方式和失败处理**都写出来了——照着抄，不要跳步。

#### 第 0 步：容器运行时自检（10 秒）

```bash
docker info --format '{{.ServerVersion}} / {{.OperatingSystem}}'
```

**必须输出版本号**。如果报 `Cannot connect to the Docker daemon`，先解决它，再往下走：

```bash
# macOS 上你有两套运行时，作者机器两套都装了（context 容易指错，这是个大坑）
docker context ls                 # 看当前用的是哪个
docker context use orbstack      # OrbStack：快、安静、推荐
docker context use colima        # 或者 Colima（需先 colima start）
docker info                      # 确认这次通了
```

> **实测记录**：作者机器当前 context 指向 `colima`，但 colima 守护进程没运行，于是 `docker run` 直接失败。`docker context use orbstack` 之后立刻通了。**报连接错误时，第一件事是查 context，不是查镜像。**

#### 第 1 步：镜像预检——先看本地有没有，别急着拉

```bash
docker images | grep -E "pgvector|postgres"
```

有输出就直接用（**作者就是这样避开了 Docker Hub 超时的**）。没有输出再拉：

```bash
docker pull pgvector/pgvector:pg16        # 拉不到就换 pg17，两个都行
```

> **实测记录**：Docker Hub 在作者网络下 `TLS handshake timeout`。**如果你也拉不动，改用本地已有的 pg17，或者换国内镜像源**——`pg16`/`pg17` 对本篇代码完全等价（实测 pgvector 0.8.2 + PG 17.10 跑通全链路）。

#### 第 2 步：起容器 + 立即验证

```bash
# 启动（后台）
docker run -d --name rag-pg \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# ↓↓↓ 下面三条验证必须全过才能继续 ↓↓↓

docker ps --filter name=rag-pg              # 1) 状态必须是 Up，端口显示 0.0.0.0:5432->5432/tcp
docker exec rag-pg pg_isready                # 2) 必须输出 "accepting connections"
docker exec rag-pg psql -U postgres -c \
  "SELECT default_version FROM pg_available_extensions WHERE name='vector';"   # 3) 必须有一行输出（版本号）
```

第 3 条是最容易被忽略的：容器起来了**不等于** pgvector 扩展装了（如果你用的是 vanilla postgres 镜像就会缺）。

#### 第 3 步：Python 侧依赖

```bash
uv init --python 3.11          # 在项目目录里建虚拟环境
uv add "psycopg[binary]" openai python-dotenv
```

#### 第 4 步：配置（key 别提交 git）

```bash
cat > .env <<EOF
PG_DSN=postgresql://postgres:postgres@localhost:5432/postgres
DEEPSEEK_API_KEY=sk-你的key            # 对话用（DeepSeek 平台申请）
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v3
EOF
chmod 600 .env                          # 只给自己读写
```

代码里两个 SDK 读**各自的变量名**。完整版见项目里的 `llm_backend.py`（第 3.5 节会用它切本地模型），这里先认脸：

```python
import os
from openai import OpenAI

emb_client = OpenAI(
    api_key=os.environ["AI_DASHSCOPE_API_KEY"],        # 读这个
    base_url=os.environ["EMBEDDING_BASE_URL"],
)
llm_client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],            # 读这个
    base_url="https://api.deepseek.com",               # 切本地时换成 oMLX 的地址（3.5 节）
)
```

> 说明：embedding 端点以你实际平台为准，百炼控制台→模型广场搜 `text-embedding-v3`（1024 维）复制 base_url 和 key。**硅基流动的 `BAAI/bge-m3` 也可，照着改 `.env` 即可。**

#### 第 5 步：用完怎么停（收工别忘）

```bash
# 方式 A：停止但保留数据（下次还能接着用，推荐）
docker stop rag-pg

# 方式 B：停止并彻底删除（数据没了，重来）
docker rm -f rag-pg

# 确认真的停了（顺手检查端口有没有释放）
docker ps -a --filter name=rag-pg          # 应为空
lsof -ti:5432                              # 应无输出
```

> **实测记录**：作者用 `docker rm -f rag-pg` 清理后，`docker ps` 已空、5432 端口无占用。**别让测试容器在后台裸奔占着 5432**，否则你本机原有的 postgres 服务会起不来，而且这类"幽灵占用"极难排查。

### 实验 1：建库（一段 SQL 的事）

```python
# schema.py
import psycopg
from dotenv import load_dotenv
import os

load_dotenv()

def init_db():
    with psycopg.connect(os.environ["PG_DSN"]) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS doc_chunks (
                    id        BIGSERIAL PRIMARY KEY,
                    source    TEXT NOT NULL,                -- 来自哪个文档
                    content   TEXT NOT NULL,                -- chunk 原文
                    embedding vector(1024) NOT NULL,       -- BGE-M3/text-embedding-v3
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
            conn.commit()
    print("doc_chunks 表就绪")

if __name__ == "__main__":
    init_db()
```

```bash
uv run python schema.py
```

熟悉的 `CREATE TABLE`，只多两样东西：`vector` 扩展和 `vector(1024)` 列。**你的 PG DBA 经验全盘复用，只是列类型多认一个。**

### 实验 2：文档入库（ETL 出厂）

```python
# ingest.py
import os, re
from dotenv import load_dotenv
import psycopg
from openai import OpenAI

load_dotenv()
emb_client = OpenAI(
    api_key=os.environ["EMBEDDING_API_KEY"],
    base_url=os.environ["EMBEDDING_BASE_URL"],
)

RAW_DOCS = {
    "员工手册-年假": "年假制度：入职满一年享有5天带薪年假，满十年10天，满十五年15天。年假最小申请单位为半天。",
    "员工手册-病假": "病假制度：需提供二级以上医院诊断证明，病假期间工资按基本工资的80%发放，全年累计不超过30天。",
    "员工手册-报销": "差旅报销需在行程结束后30天内提交，发票抬头必须为公司全称，超标部分需分管副总裁特批。",
    "员工手册-考勤": "考勤制度：标准工时早9晚6。每月允许3次忘打卡豁免，第4次起每次扣款50元。季度全勤奖200元。",
}

def chunk_by_section(source: str, text: str, max_chars=200):
    """结构感知分块：按句号切，超过 max_chars 再合并成块（简易版）
    真实项目：按 Markdown 标题层级递归切"""
    sentences = [s for s in re.split(r"(?<=。)", text) if s.strip()]
    chunks, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) > max_chars and buf:
            chunks.append(buf); buf = s
        else:
            buf += s
    if buf: chunks.append(buf)
    return [(source, c) for c in chunks]

def embed(text: str) -> list[float]:
    resp = emb_client.embeddings.create(model=os.environ["EMBEDDING_MODEL"], input=text)
    return resp.data[0].embedding

def ingest():
    pairs = []
    for src, text in RAW_DOCS.items():
        pairs += chunk_by_section(src, text)

    with psycopg.connect(os.environ["PG_DSN"]) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM doc_chunks WHERE source LIKE '员工手册-%';")   # 幂等重灌
        for src, chunk in pairs:
            cur.execute(
                "INSERT INTO doc_chunks (source, content, embedding) VALUES (%s, %s, %s)",
                (src, chunk, embed(chunk)),
            )
        conn.commit()
    print(f"已入库 {len(pairs)} 个 chunk")

if __name__ == "__main__":
    ingest()
```

```bash
uv run python ingest.py
```

三个工程细节请划笔记：

1. **先 DELETE 再 INSERT**——重跑不堆重复数据，ETL 的幂等基操
2. **embedding 逐条调**——15 条 demo 无所谓；真项目必须批量（openai SDK 一次 input 传 list）+ 失败重试，成本直接差一个数量级
3. **chunk 带 source 元数据**——引用溯源靠它，没有 source 的 RAG 等于匿名举报

### 实验 2.5：AI 数据处理三件套——pandas / numpy / DuckDB（Java 老司机的第二现场）

上面这段 ETL 里，你迟早会撞到一个问题：**"我想看看这批 chunk 到底长什么样"**——按 source 数一数、把分数分布拉出来看看阈值该定多少、某条文档为什么没被召回。

Java 老司机的肌肉记忆是"导 CSV 回 Excel"或者"再连一次库写段 SQL"。Python 给的是第三条路，也是 AI 圈默认的土话：**不起服务、不建表，直接对内存里的对象和手边的 CSV 开算**。三件套各管一段，五分钟入个门：

```python
# 安装：uv add numpy pandas duckdb（裸 Python 就 pip install -U）
import numpy as np, pandas as pd, duckdb
from dataclasses import dataclass

@dataclass(slots=True)
class Chunk:
    content: str
    source: str
    score: float

chunks = [
    Chunk("年假制度：入职满一年享有5天带薪年假，满十年10天，满十五年15天。年假最小申请单位为半天。", "员工手册-年假", 0.71),
    Chunk("病假制度：需提供二级以上医院诊断证明，病假期间工资按基本工资的80%发放，全年累计不超过30天。", "员工手册-病假", 0.58),
    Chunk("差旅报销需在行程结束后30天内提交，发票抬头必须为公司全称，超标部分需分管副总裁特批。", "员工手册-报销", 0.81),
    Chunk("考勤制度：标准工时早9晚6。每月允许3次忘打卡豁免，第4次起每次扣款50元。季度全勤奖200元。", "员工手册-考勤", 0.42),
    Chunk("年假最小申请单位为半天，半天=4小时，不足半天按半天计。", "员工手册-年假", 0.66),
]

# 1) numpy：向量就是数组，"语义相似"根本不是玄学
#    假装 embedding：把每个 chunk 压成 4 维"伪向量"（真实是 1024 维）
vecs = np.array([[1.0, 0.0, 0.2, 0.0], [0.0, 1.0, 0.0, 0.1], [0.3, 0.0, 1.0, 0.0], [0.0, 0.1, 0.0, 1.0], [0.9, 0.0, 0.3, 0.0]])
query = np.array([1.0, 0.0, 0.25, 0.0])

def cosine(a, b):
    """支持 (d,) 或 (n,d) 两种输入，返回相似度或相似度向量"""
    a, b = np.atleast_2d(a), np.atleast_2d(b)
    num = a @ b.T
    den = np.linalg.norm(a, axis=1, keepdims=True) * np.linalg.norm(b, axis=1, keepdims=True)
    sims = num / den
    return float(sims[0, 0]) if sims.shape == (1, 1) else sims[:, 0]

print("numpy 算余弦相似度（query=年假）:")
for c, v in zip(chunks, vecs):
    print(f"  {cosine(query, v):.3f}  {c.source}  {c.content[:18]}...")
sims = cosine(vecs, query)          # 一次算全部：矩阵 × 向量
print("top1 是第", int(np.argmax(sims)), "条 chunk（上面决策 4 那个 `<=>` 算的就是它）")

# 2) pandas：一张表看清 chunk 分布，RAG 排障的第一步
df = pd.DataFrame({"source": [c.source for c in chunks],
                   "score": [c.score for c in chunks],
                   "chars": [len(c.content) for c in chunks]})
print("\npandas 统计 chunk:")
print(df.groupby("source")["score"].agg(["count", "max", "min"]).round(3).to_string())
df.to_csv("chunks.csv", index=False)

# 3) DuckDB：不起服务直接对 CSV 跑 SQL
con = duckdb.connect()
print("\nDuckDB 直接查 CSV:")
print(con.execute("select source, count(*) as n, round(max(score),3) as top from 'chunks.csv' "
                  "group by source order by top desc").df().to_string(index=False))
con.close()
```

作者机器实测输出（numpy 2.5.4 / duckdb 1.5.6 / CPython 3.13.13）：

```text
numpy 算余弦相似度（query=年假）:
  0.999  员工手册-年假  年假制度：入职满一年享有5天...
  0.000  员工手册-病假  病假制度：需提供二级以上医院...
  0.511  员工手册-报销  差旅报销需在行程结束后30天内...
  0.000  员工手册-考勤  考勤制度：标准工时早9晚6。...
  0.997  员工手册-年假  年假最小申请单位为半天...
top1 是第 0 条 chunk（第 13 篇 SQL 里 () <=> 干的就是这件事）

pandas 统计 chunk:
         count   max   min
source                    
员工手册-年假      2  0.71  0.66
员工手册-报销      1  0.81  0.81
员工手册-病假      1  0.58  0.58
员工手册-考勤      1  0.42  0.42

DuckDB 直接查 CSV:
 source  n  top
员工手册-报销  1  0.81
员工手册-年假  2  0.71
员工手册-病假  1  0.58
员工手册-考勤  1  0.42
```

三条要点，对应三个"以后再也不用问人"的能力：

1. **numpy 让你看懂 pgvector 的存根。** 上面这个 `cosine` 就是 `<=>`（余弦距离）的全部数学。PG 里你写 `1 - (a <=> b)` 拿到的分数，和这里算的 0.999 是同一个东西——**调阈值 0.6 时心里有底了**。第 16 篇讲 Rerank 时这条会返场。
2. **pandas 是"看数据"的显微镜。** 上面 `groupby().agg()` 三行，等价于先导 Excel 再拖透视表。RAG 排障九成时间是看数据：哪批文档没切好、分数是不是全挤在 0.5 附近、某类问题为什么召回为 0。第 21 篇做评测集会正式用它。
3. **DuckDB 是"本机 OLAP 的偷渡船"。** 嵌入式（`pip install` 完事，不用像 PG 那样起服务）、直接吃 CSV/Parquet/JSON、SQL 语法基本就是 PG 的亲兄弟——**你那条 SQL 经验非但没废，还多了一个不用运维的战场**。日志归档、几十万行明细、RAG 评测结果回溯，都是它的甜区。

**边界要划清楚，不然会走火入魔：** PG + pgvector 是唯一权威存储，写入、事务、权限都归它管；这三件套是**第二现场**，只做本机探索、特征计算、离线统计，不进生产链路。谁要拿 pandas 当数据库用，谁就会在某个深夜发现自己得手写一套事务和权限。

### 实验 3：查询管道（11 篇的 chat_stream 回来啦）

> **先看一眼全局**，免得copy 完不知道谁先跑。本篇一共要建 **4 个文件**，按这个顺序执行：

| 顺序 | 文件 | 作用 | 跑一次还是多次 |
|---|---|---|---|
| 1 | `.env` | 配置（key + DSN） | 一次 |
| 2 | `schema.py` | 建扩展和表 | 一次（重复跑安全） |
| 3 | `ingest.py` | 灌文档 + 向量化 | 改文档就重跑（幂等，会先 DELETE） |
| 4 | `query.py` | 检索 + 问答 | **每次提问都跑** |

```
rag-project/
├── .env              ← 配置（记得 chmod 600，别提交 git）
├── schema.py         ← 建库
├── ingest.py         ← 灌数据
├── query.py          ← 查询
└── pyproject.toml    ← uv init 自动生成
```

```bash
# 标准执行顺序
uv run python schema.py     # 建表
uv run python ingest.py     # 灌 6 篇制度文档
uv run python query.py      # 提问，看效果
```

```python
# query.py
import os
from dotenv import load_dotenv
import psycopg
from openai import OpenAI
from llm_backend import chat      # ← 云端/本地双模式适配层，见实验 3.5

load_dotenv()

emb_client = OpenAI(
    api_key=os.environ["AI_DASHSCOPE_API_KEY"],
    base_url=os.environ["EMBEDDING_BASE_URL"],
)

TOP_K = 3
SCORE_THRESHOLD = 0.60      # 军令状阈值——⚠️ 这个数字不是拍脑袋来的，是实测扫出来的（见下方"实测记录"）

# 实测数据（作者机器，pgvector 0.8.2 + PG 17.10 + text-embedding-v3）：
#   在库问题 top1 分数区间: 0.688 ~ 0.799
#   不在库问题 top1 分数区间: 0.406 ~ 0.595
#   → 阈值 0.6：6/6 正确拦截，0/3 误收
#   → 阈值 0.35（很多人抄的默认值）：会把"公司健身房几点开"当成命中，幻觉从这里开始

def retrieve(question: str):
    q_vec = embed(question)
    # 稳妥写法：把向量转成字符串再让 PG 解析成 vector。
    # （直接传 Python list 依赖 psycopg3 的数组适配 + PG 的数组转 vector 强转，
    #  不同驱动/版本组合下行为不一致，报错信息还很难懂——踩过一次就记住了）
    q_literal = "[" + ",".join(f"{x:.6f}" for x in q_vec) + "]"
    with psycopg.connect(os.environ["PG_DSN"]) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT source, content,
                   1 - (embedding <=> %s::vector) AS score
            FROM doc_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (q_literal, q_literal, TOP_K))
        return cur.fetchall()        # [(source, content, score), ...]

def answer(question: str) -> str:
    hits = [(s, c) for s, c, score in retrieve(question) if score >= SCORE_THRESHOLD]
    if not hits:
        return "资料未提及（检索相似度不足，已拦截编造）"

    context = "\n".join(f"资料{i+1}（{src}）：{content}" for i, (src, content) in enumerate(hits))
    prompt = f"""你是公司HR制度助手。仅根据以下资料回答，资料未覆盖就明说，禁止编造，条理用条目列出。

    {context}

    员工问题：{question}"""
    # 就是 11 篇那一行：流式复用之（但 base_url 换成本地服务也能跑，见实验 3.5）
    return chat(prompt)

if __name__ == "__main__":
    for q in ["年假怎么休？", "住院了工资怎么算？", "公司健身房几点开？"]:
        print(f"\nQ: {q}")
        print("检索:", [(s, round(sc, 3)) for s, _, sc in retrieve(q)])
        print("A:", answer(q)[:150])
```

跑三个问题，对照 12 篇的玩具版：

**作者实测输出**（2026-10-12，Apple M5 Pro / pgvector 0.8.2 / PG 17.10 / text-embedding-v3；生成层用**本地 Unsloth Qwen3.5-4B-GGUF**）：

```
年假怎么休？          → 员工手册-年假     score=0.747  165ms ✓
住院了工资怎么算？     → 员工手册-病假     score=0.721  159ms ✓
出差发票有什么要求？    → 员工手册-报销     score=0.741  106ms ✓
迟到扣钱吗？          → 员工手册-考勤     score=0.688  164ms ✓
食堂有夜宵吗？         → 员工手册-食堂     score=0.713   93ms ✓
出差住宿多少钱一晚？    → 员工手册-差旅住宿  score=0.799  149ms ✓
公司健身房几点开？     → 员工手册-考勤     score=0.595  116ms ✓ 已拦截（0.595 < 0.60）
──────────────────────────────────────────────────────
top1 命中率 7/7 ｜ 平均检索延迟 136ms ｜ 入库 155ms/chunk

后端模式: local  模型: unsloth/Qwen3.5-4B-GGUF
Q: 我入职三年了，年假几天？
A: 根据资料，入职满一年享有 5 天带薪年假，满十年 10 天，满十五年 15 天。
   您入职三年，属于"入职满一年"但未达到"满十年"的区间，因此享有 5 天带薪年假。   [1200ms]
Q: 出差住酒店超标了能报吗？
A: 不能全额报销。1. 超标部分由个人承担；2. 特殊情况需事前审批…                      [2267ms]
Q: 公司食堂周三有小龙虾吗？
A: 资料未提及                                                                   [320ms]
```

> ⏱️ **第三个问题是故意设的陷阱**：6 篇制度文档里只写了"周四固定有小龙虾"，"周三"根本没提。
> 本地 4B 模型**没有顺着问编一个周三有**——阈值拦截先挡一层，拒答模板再挡一层。
> 这才是 RAG 防幻觉的**实际价值**：不是"检索更准"，而是**答不出来时能理直气壮地说答不出来**。

> ⏱️ **那最后一行是本篇最有价值的一行。** "公司健身房几点开"在库里根本没有，但它拿到了 **0.595 的高分**——**真实 embedding 的相似度分布远高于玩具版**。如果沿用很多教程抄来的 0.35 阈值，这个幻觉请求就会被放行：拿一份"考勤制度"去回答"健身房"，一路错到底。
>
> 完整阈值扫描（3 条不在库的负样本）：
>
> | 阈值 | 正确保留在库问题 | 误收不在库问题 |
> |---|---|---|
> | **0.60** | **6/6** | **0/3** |
> | 0.70 | 5/6 | 0/3 |
> | 0.35（默认值） | 6/6 | **3/3 全误收** |
>
> **结论：阈值必须用你自己的评测集扫出来**（方法见 16 篇）。本篇的 0.6 是在 6 篇中文制度文档上实测的——**你的语料不同、embedding 模型不同，这个数一定要自己重扫。** 附录 B 讲了怎么区分"真经验值"和"抄来的数字"：这个 0.6 是前者，因为它附带可复现的分布区间。

对照 12 篇的玩具版：

- 前两问命中 → 引用来源清清楚楚（**"（员工手册-年假）"就是 source 字段**），答案质量从"模型瞎接"升级为"照读+组织语言"
- 第三问被 `SCORE_THRESHOLD` 拦截——**12 篇说的军令状，在这里是一行 if**

**整条管道你现在能拆开了给别人讲了**：切块、向量化、SQL 检索、阈值兜底、流式生成。五个面试高频问题，你亲手实现过一遍，和背过答案的候选人不是一个物种。

### 实验 3.5：生成层放本地，零成本（作者被读者问出来的）

> 这节是被一个真实问题逼出来的：**"我本机装了 Unsloth，还有下载好的 Qwen3.5-4B-GGUF，为什么还要 DeepSeek？"**

作者第一版确实写死云端 API，理由是"复用 11 篇代码一致性"。这个理由**技术上成立，工程上是错的**——
它把一个**可选**的选择，写成了**必选**的依赖。读者抄完代码发现要注册、要充值、余额一不足就 `402` 挂掉，**这不叫教学**。

#### 3.5.1 先把话说透：DeepSeek 从来不是 RAG 的必需品

RAG 这条管道里，两个环节的性质完全不同：

| 环节 | 干什么 | 能不能本地 | 为什么 |
|---|---|---|---|
| **Embedding**（检索层） | 把问题和文档变成同一空间里的向量 | ⚠️ **建议云端** | 小模型算 embedding 质量普遍不行，检索直接崩。这步值得花钱 |
| **Generation**（生成层） | 拿着检索到的资料写答案 | ✅ **本地完全够** | 4B 模型就能把"照着资料复述并组织语言"这件事做对 |

**钱应该花在检索层，不是生成层。** 你的文档不进外网（RAG 本来就是为了这个），答案也不用外发。

#### 3.5.2 为什么切换成本几乎为零：都是 OpenAI 兼容协议

云端和本地都暴露同一套接口（`/v1/chat/completions`、`/v1/models`、`/v1/embeddings`），
所以**换后端 = 换 `base_url` + `api_key` + `model` 三个值，业务代码一行不改**。

这就是"适配层"存在的意义——把差异关在一个文件里：

```python
# llm_backend.py —— 全篇只有这个文件知道云和本地不一样
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()          # ← 坑点①：必须在本文件里加载，见下

def backend() -> str:
    """惰性读取：api | local（默认 local）"""
    return os.environ.get("LLM_BACKEND", "local")

def _client():
    if backend() == "local":
        return OpenAI(
            api_key=os.environ.get("LOCAL_KEY", "EMPTY"),
            base_url=os.environ.get("LOCAL_BASE_URL", "http://127.0.0.1:8000/v1"),
        )
    return OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )

def get_model_name() -> str:
    if backend() == "local":
        return os.environ.get("LOCAL_MODEL", "Qwen2.5-0.5B")
    return "deepseek-chat"

def chat(prompt: str, max_tokens: int = 500) -> str:
    """统一入口——调用方不需要知道背后是云还是本地"""
    resp = _client().chat.completions.create(
        model=get_model_name(),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens, temperature=0.3,
    )
    return resp.choices[0].message.content

def health() -> str:
    """连通性自检：刚切完模式第一件事跑这个"""
    try:
        ids = [m.id for m in _client().models.list().data]
        return f"✅ 后端={backend()} 可用，模型: {ids}"
    except Exception as e:
        return f"❌ 后端={backend()} 连不上: {type(e).__name__}: {e}"
```

`.env` 里一行切换：

```bash
LLM_BACKEND=local   # 默认：本地模型，零成本、数据不出内网
LLM_BACKEND=api     # 云端大模型

LOCAL_BASE_URL=http://127.0.0.1:53967/v1
LOCAL_KEY=omlx-你的key
LOCAL_MODEL=unsloth/Qwen3.5-4B-GGUF
```

**坑点①（作者自己踩的）**：`load_dotenv()` 写在**调用方**是不够的。

`from llm_backend import chat` 这行在 `query.py` 顶部执行，**比 `query.py` 里的 `load_dotenv()` 更早**——
如果 `llm_backend.py` 在模块级用 `os.environ.get("LLM_BACKEND")` 取值，拿到的还是空字符串，直接回落成 `api`。

症状是：**`.env` 里明明写了 `local`，跑起来还是打到了云端，余额不足报错。**

修法两个，作者用了第一个：
1. `llm_backend.py` 自己调 `load_dotenv()`（放在 import 后第一行）
2. 或者干脆别在模块级取值，改成函数里惰性读取（`backend()`）

> Python 老手看到这儿应该笑了：这坑的本质是**导入时机（import-time）早于调用时机**。
> 凡是"模块级读配置"的代码，都要警惕——它测的是导入那一刻的环境，不是你写代码那一刻的环境。

#### 3.5.3 方案 A：Unsloth Studio（最省事，GGUF 白送）

**关键事实：Unsloth 桌面版自己就起了一个 llama-server，它本身就是 OpenAI 兼容服务**，你什么都不用写：

```bash
# 1) 界面里点开你的 GGUF 模型，服务自动起
# 2) 端口在界面里能看到（作者机器 53967，随机端口）
# 3) key 在这个文件里：
cat ~/.unsloth/studio/auth/llama_api_key_*

# 4) 确认模型名（必须和这里返回的完全一致）
curl -s -H "Authorization: Bearer $LOCAL_KEY" "$LOCAL_BASE_URL/models" | python3 -m json.tool
```

```
{"models":[{"name":"unsloth/Qwen3.5-4B-GGUF","model":"unsloth/Qwen3.5-4B-GGUF",...}]}
```

⚠️ **模型名带 `unsloth/` 前缀**，很容易写成 `Qwen3.5-4B-GGUF` 然后报"model not found"。**以 `/v1/models` 的返回值为准，别猜。**

#### 3.5.4 方案 B：oMLX（Apple Silicon 首选，但格式和内存是两个坑）

```bash
pip install omlx
omlx serve --model-dir ~/.omlx/models --port 8000 --memory-guard safe
```

**坑点②：oMLX 不吃 GGUF。** 它要求 `config.json` + `*.safetensors` 的 MLX 格式。
你从 Hugging Face 下的是 GGUF（那是**导出/推理产物**，不是训练原料），**不是改名就能用**。

**坑点③：模型装不下会被主动拒绝，而不是卡死。** 这其实是很优秀的工程设计：

```
Error code: 507 - Model 'Qwen3.5-9B-MLX-4bit' (5.82GB) does not fit under
the dynamic memory ceiling (4.59GB). Close other apps to free RAM
(static cap is 16.00GB but only 4.31GB is reclaimable right now)
```

调档 `--memory-guard safe → balanced → aggressive`。但作者机器实测 aggressive 依然拦住了 9B（可用 4.5GB < 需要 5.82GB）。

**教训：选模型之前先算内存，别等报错**（第 23 篇）。报错信息其实把账算得很清楚，照着做决定即可。

#### 3.5.5 坑点④：模型不能太小——0.5B 会输出日文乱码

作者用 `Qwen2.5-0.5B`（953MB）跑通了链路，延迟 398ms，**但答案是这样的**：

```
Q: 食堂周三有小龙虾吗？
A: lijkeや。
   lijkeや食堂の価格は、一般的处分のみですので、3月に独立する試験に使用されていません。
   lijkeや配送週明けのお知らせはこちら。
```

检索完全正常（阈值判断对了），**但生成彻底崩了**。

**"链路通了"不等于"能用"。** RAG 的生成任务本质是"照着资料复述并组织语言"，
0.5B 模型的指令遵循和中文能力不够，拼出了日文。

**RAG 生成至少 4B 起步，7B 更稳。** 0.5B 适合 23 篇里那种"证明本地能跑"的链路验证，不适合放进业务管道。

#### 3.5.6 本地 4B 的真实效果（同样三个问题）

```
后端模式: local  模型: unsloth/Qwen3.5-4B-GGUF

Q: 我入职三年了，年假几天？
A: 根据资料，入职满一年享有 5 天带薪年假，满十年 10 天，满十五年 15 天。
   您入职三年，属于"入职满一年"但未达到"满十年"的区间，因此享有 5 天带薪年假。   [1200ms]

Q: 出差住酒店超标了能报吗？
A: 根据资料，出差住酒店超标不能全额报销。
   1. 超标部分由个人承担：即超标金额需员工自付，公司不予报销。
   2. 特殊情况需事前审批：只有在事前获得审批的特...                                [2267ms]

Q: 公司食堂周三有小龙虾吗？
A: 资料未提及                                                                       [320ms]
```

**结论很直接：本地 4B 够用。** 推理耗时 0.3~2.3 秒，对内部知识库问答完全可接受，
而且**免费、无延迟抖动、数据不出内网**。

唯一诚实的短板：复杂推理或多轮改写场景，4B 明显不如云端旗舰。
**所以默认本地、需要时切云端**，而不是"只能二选一"。

#### 3.5.7 Java 老司机对照室：适配层就是 Strategy 模式

```java
interface ChatBackend { String chat(String prompt); }

class CloudBackend implements ChatBackend { /* base_url=api.deepseek.com */ }
class LocalBackend implements ChatBackend { /* base_url=127.0.0.1:8000  */ }

// .env 里的 LLM_BACKEND 就是配置文件里的一行策略选择
ChatBackend backend = "local".equals(cfg.get("LLM_BACKEND"))
        ? new LocalBackend() : new CloudBackend();
```

你其实**在 Java 里天天写这个**——`application.yml` 里 `spring.datasource.url` 切 MySQL/PG/Oracle，
换库不换业务代码。**适配层的价值从来不是技术含量，是"让变化只发生在一个地方"。**

> 一句话带走：**依赖要分层，可选项不能写成必选项。** 你给读者一个"必须充值才能跑完的教程"，
> 他没余额，这一篇就白读了。

#### 想直接跑？这里有作者实测过的完整项目

上面 4 个实验的代码可以直接抄，但如果你不想一行行拼，本书仓库里放了一份**作者实测跑通的完整版**：

```
projects/rag-project/
├── README.md        ← 完整运行手册（含本文全部踩坑记录 + 本地/云端双模式配置）
├── schema.py        ← 建库（与实验 1 一致）
├── ingest.py        ← 灌数据（与实验 2 一致，含 6 篇制度原文）
├── llm_backend.py   ← 云端/本地双模式适配层（与实验 3.5 一致，带 health 自检）
└── query.py         ← 检索+问答+评测集（与实验 3、4 合并，含真实阈值 0.60）
```

**教学版 vs 实测版的三点关键差异**（实测版是跑通过的，教学版是讲解用的）：

| 差异点 | 教学版（书里） | 实测版（projects/） | 为什么 |
|---|---|---|---|
| 向量传参 | 直接传 Python list | 转成字符串字面量 + `%s::vector` | psycopg3 对 list 的适配跨版本不稳，字符串写法永远可跑（见上文注释） |
| 阈值 | `0.35`（很多教程的默认） | `0.60`（实测扫出来的） | 0.35 会让 3/3 不在库问题全部误收 |
| 文档数 | 4 篇 | 6 篇（多了差旅住宿） | 够跑出有意义的阈值分布 |

**用法**：

```bash
cd projects/rag-project
cp .env.example .env          # 项目目录里自带模板，填你的 key
uv run python schema.py && uv run python ingest.py && uv run python query.py
```

### 实验 4：把召回率变成数字（21 篇的楔子）

*（继续用实验 3 的 `query.py`，那里已经定义了 `retrieve`——需要 `.env` 里的 key 和跑着的 pgvector）*

```python
EVAL_SET = [
    ("年假怎么休？", ["员工手册-年假"]),
    ("住院了工资怎么算？", ["员工手册-病假"]),
    ("出差发票有什么要求？", ["员工手册-报销"]),
]

def hit_rate():
    good = 0
    for q, expected in EVAL_SET:
        got = [s for s, _, _ in retrieve(q)]
        if any(g in expected for g in got[:1]):   # top1 命中就算对
            good += 1
    return good / len(EVAL_SET)

print(f"top1 命中率: {hit_rate():.0%}")
```

**十行代码的评测集**——它现在只有 3 条，第 21 篇会把它升级成“正常/模糊/盲区/对抗”四类分层的正式评测套件，并教你扩到 50 条以上。**没有评测集的 RAG 项目，等于闭眼开车。**

## 费曼复述卡

1. 向架构师汇报：为什么小团队选 pgvector 而不是 Milvus？（提示：从运维成本、join、复用 PG 体系三个角度）
2. 说出 RAG 管道的六个工位本篇各自的工业件是什么，以及和 12 篇玩具版的对应关系。
3. `SCORE_THRESHOLD` 拦的是什么问题？为什么说它比"把 top3 全塞进去"更专业？

三题过不了，把实验 2、3 重跑一遍。**实战篇的真理：跑通之前，看再多遍都是 spectators。**

## 今日一句话

> 裸装 RAG 五件套：结构分块、BGE 向量化、pgvector 一行 SQL、阈值军令状、流式复用——全是你旧手艺的新组合。

---

下一篇：[14 · Agent：让模型学会自己用工具](./14-agent.md)（返回 [目录](./index.md)）
