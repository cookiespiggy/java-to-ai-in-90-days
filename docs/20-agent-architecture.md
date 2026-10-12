# 20 · 生产级 Agent 架构：记忆、压缩与武器库

## 先讲给朋友听（如果你只有一分钟）

> 第 14 篇的 Agent 是个"失忆的打工人"：每轮对话都把全部历史重发一遍，干三个小时就撑爆上下文。生产级 Agent 架构要解决的就是这件事：**给它记忆、给它档案柜、教它忘掉废话，再配上一整套工具和护栏。** 这些模块你全都见过——只是换了名字。

## 你的 Aha Moment

先看一组 2026 年的实测数字（Mem0 官方基准，LoCoMo 数据集）：

| 方案 | 每次查询消耗 token |
|---|---|
| 全量上下文（把所有历史都塞进去） | **26,000+** |
| Mem0 式外部记忆（检索相关事实） | **~7,000** |

**同样的效果，四分之一的成本。** 在每天万级交互的生产系统里，这不是优化，是生死线。

但更值得你 Aha 的是另一件事：**这两个数字背后，是两个完全不同的设计哲学。**

- **上下文压缩**（compression）：历史太长了？摘要一下、截断一下、把工具输出删掉。**它不记住任何东西，它只是忘得更慢。** 单会话内有效，跨会话归零，失败模式是"静默的有损退化"——你根本不知道丢了什么。
- **外部记忆**（memory）：在信息消失**之前**把事实抽出来，存到上下文窗口外面，用的时候按相关性取回来。**存的是原子事实，跨会话有效，成本是恒定的。**

工业界 2025-2026 的共识是**三层架构**，把两者都用上：

```
Tier 1  工作记忆（in-context）    当前会话原样保留，无损，最贵
Tier 2  会话压缩（compression）   会话变长 → 锚定式增量摘要，省钱但有损
Tier 3  长期记忆（external）      跨会话原子事实，检索式取回，成本恒定
```

Aha 落点：**这三层就是你熟悉的存储金字塔**——Tier 1 是内存，Tier 2 是换出到磁盘的页面缓存，Tier 3 是数据库。连淘汰策略都眼熟：记忆的"过期"用 0.3~1.5 倍的**新近度衰减因子**做软重排（不硬删，只是排得靠后），活脱脱一个 LRU 的软评分版。

## 不讲术语的版本：生产级 Agent 的六个模块

画一张架构图，你就能看出它跟你做过的系统多么同构：

```
                    ┌──────────────┐
   用户请求 ───────▶│  接入/网关层  │  多租户、限流、鉴权、审计
                    └──────┬───────┘
                           ▼
        ┌─────────────────────────────────────┐
        │          编排层（LangGraph）          │  状态机 / 工作流 / 人审节点
        │  ┌─────────┐  ┌────────┐  ┌───────┐ │
        │  │ 短期记忆 │  │ 长期   │  │ 压缩  │ │ ◀── Tier1/2/3
        │  │ (buffer)│  │ 记忆库 │  │ 引擎  │ │
        │  └─────────┘  └────────┘  └───────┘ │
        └───┬──────────────┬──────────────┬───┘
            ▼              ▼              ▼
      ┌──────────┐  ┌────────────┐  ┌──────────┐
      │ 知识检索  │  │ 工具/MCP   │  │ 代码沙箱 │
      │ ES+向量  │  │ 副作用闸门 │  │ 隔离执行 │
      └──────────┘  └────────────┘  └──────────┘
            └──────────────┴──────────────┘
                           ▼
                    ┌──────────────┐
                    │ 观测/评测/计费 │  全链路 trace + 评测集 + token 账
                    └──────────────┘
```

**模块一 · 接入/网关层。** 多租户隔离（A 公司的问题不能看到 B 公司的记忆）、按用户限流（防刷 token）、全量审计（谁在什么时候问了什么）。**这就是你的 API Gateway，加了一套 AI 特有的计费维度。**

**模块二 · 编排层。** LangGraph 的图。生产上和 Demo 的区别在两点：**checkpointer 必须用持久化实现**（断电恢复，对应 Camunda 的流程实例表）；**副作用工具必须过人审**（17 篇的 `interrupt()`）。

**模块三 · 记忆三层。**

- **Tier 1 短期记忆**：消息缓冲区，原样保留最近 N 轮
- **Tier 2 压缩**：锚定式增量摘要（anchored summarization）——**不是每次都重新总结全文**，而是在既有摘要上追加增量。行业里有个狠案例：某团队分析 36000 条工程会话消息，发现"锚定式"在准确率上**优于完全重建**，也优于 Anthropic 和 OpenAI 的摘要方案
- **Tier 3 长期记忆**：每轮对话后，用一个便宜模型抽取原子事实存库（"用户是 3 年工龄的产品经理""他偏好表格而非长文"），按 user_id / agent_id / org_id 三维度做**作用域隔离**。注意 Mem0 的工程细节：抽取是 **ADD-only**（只加不覆盖），历史不会被静默改写；过期靠软衰减而非硬删除

**模块四 · 知识检索。** 就是 16 篇那套混合检索。企业场景多一个维度：**知识库（wiki）的接入**——飞书/Confluence/Notion 文档。工程上关注两件事：**增量同步**（文档更新了，索引要跟得上，ETL 的活）和**权限过滤**（检索时按用户权限裁剪文档集，别把财务制度推给实习生）。

**模块五 · 工具与 MCP。** 2026 年的生产标准是 **MCP（Model Context Protocol）**：工具不再在每个 Agent 里各写一遍，而是做成标准 server，任何 Agent 都能挂。你机器上的 oMLX 就原生支持 `--mcp-config`。副作用工具（写库、发信、下单）走白名单 + 人工闸门；**代码执行必须进沙箱**（容器/微虚拟机，禁网、限时、限内存），否则模型的"我来帮你跑一下"就是你的线上事故。

**模块六 · 观测与评测。** 16 篇的评测集、17 篇的 token 账，在这里汇总成看板。生产级 Agent 的运维三件套：**每次调用的 trace**（Prompt/工具/延迟/token）、**任务完成率**（不是"感觉还行"）、**成本看板**（按租户/功能分摊）。

## Java 老司机对照室

| Agent 架构模块 | 你做过的系统 | 一句话翻译 |
|---|---|---|
| 三层记忆 | 内存 / 页面缓存 / 数据库 | 存储金字塔原样搬 |
| 锚定式增量摘要 | 增量 ETL / CDC | 别每次全量重算 |
| ADD-only 记忆 | 事件溯源（append-only log） | 只追加不改写，历史可追 |
| 新近度软衰减 | LRU 变体 | 软评分，不硬删 |
| 记忆作用域隔离 | 多租户数据隔离 | 按 user/agent/org 三维切 |
| wiki 增量同步 | Binlog → ES 同步 | ETL 老活 |
| 检索权限过滤 | 行级权限（RLS） | 检索时裁剪候选集 |
| MCP 工具 | 微服务注册中心 + SDK | 工具标准化，随处挂载 |
| 沙箱执行 | 容器隔离 / SecurityManager | 模型生成的代码 = 不可信输入 |
| 人审节点 | 审批流 UserTask | 17 篇的 `interrupt()` |
| 成本看板 | 多租户计费 | 按维度归因 |

最后一行值得念叨：**记忆的"作用域"是生产事故高发区**——把用户 A 的记忆喂给用户 B，不只是 bug，是合规事故。Mem0 官方专门列了五个作用域维度，你设计时至少要有 user / agent / org 三个。

## 动手实验室

### 实验 1：三层记忆的最小实现（零依赖，跑得动）

```python
from collections import deque
import re

class MemoryAgent:
    """三层记忆：Tier1 原文缓冲 / Tier2 摘要压缩 / Tier3 事实库"""

    def __init__(self, buffer_size=4, budget=12):
        self.tier1 = deque(maxlen=buffer_size)   # 工作记忆：最近 N 条原文
        self.tier2_summary = ""                  # 会话摘要（增量追加）
        self.tier3: dict[str, str] = {}          # 长期记忆：key -> 事实
        self.budget = budget                     # 上下文预算（token 数）

    def observe(self, role: str, content: str):
        self.tier1.append({"role": role, "content": content})

    def extract_fact(self, text: str) -> str:
        """Tier3：抽取原子事实。真实实现是调一次便宜小模型，
        这里用正则演示'什么样的事实值得抽'——右侧是可复用的抽取模式"""
        patterns = {
            "工龄": r"工龄([一二三四五六七八九十\d]+年)",
            "城市": r"(北京|上海|深圳|广州|杭州)",
            "角色": r"(后端|前端|产品经理|测试|运维)",
        }
        found = []
        for key, pat in patterns.items():
            m = re.search(pat, text)
            if m and key not in self.tier3:      # ADD-only：先到先得，不覆盖
                self.tier3[key] = m.group(1)
                found.append(f"{key}={m.group(1)}")
        return "，".join(found)

    def build_context(self) -> str:
        parts = []
        if self.tier2_summary:
            parts.append(f"[会话摘要] {self.tier2_summary}")
        if self.tier3:
            facts = "；".join(f"{k}:{v}" for k, v in self.tier3.items())
            parts.append(f"[长期记忆] {facts}")
        for m in self.tier1:
            parts.append(f"[{m['role']}] {m['content']}")
        ctx = "\n".join(parts)
        # Tier2 触发：超出预算就把最老的一段压成摘要
        if len(ctx) > self.budget and self.tier1:
            oldest = self.tier1.popleft()
            delta = f"{oldest['role']}说过：{oldest['content'][:15]}…"
            self.tier2_summary = (self.tier2_summary + " " + delta).strip()  # 锚定式追加
        return ctx

a = MemoryAgent(buffer_size=3, budget=120)
for i, msg in enumerate([
    ("user", "我入职三年了，工龄三年，在北京做后端"),
    ("assistant", "您好！三年经验正是黄金期呢～"),
    ("user", "帮我查下年假"),
    ("assistant", "年假是5天哦"),
    ("user", "那我病假呢"),
    ("assistant", "病假需要医院证明"),
]):
    a.observe(*msg)
    fact = a.extract_fact(msg[1])
    print(f"第{i+1}条 → 上下文 {len(a.build_context())} 字｜抽取到事实: {fact}")
print("\n最终上下文（注意摘要和记忆是怎么挤进来的）:")
print(a.build_context())
```

跑这个，你能亲眼看到：**缓冲区的旧消息被压成一行摘要（Tier2），"工龄=三年"被抽进事实库（Tier3）**，而 context 长度始终没炸。这就是生产 Agent 每天跑几万次的那个循环。

### 实验 2：上下文压缩 vs 外部记忆的成本曲线

```python
def simulate(turns=20, mode="compress"):
    """模拟 20 轮对话的上下文体积增长"""
    per_turn = 60                       # 每轮问答约 60 token
    if mode == "compress":              # 只压缩，不建外部记忆
        ctx = 0; summary_cap = 200
        for _ in range(turns):
            ctx = min(ctx + per_turn, summary_cap)
        return ctx
    if mode == "memory":                # 外部记忆：恒定开销
        return 400 + 7                  # 固定检索窗口
    if mode == "full":                  # 全量历史
        return turns * per_turn

print(f"{'方案':<14}{'20轮后上下文':>12}")
for m in ("full", "compress", "memory"):
    print(f"{m:<14}{simulate(mode=m):>10} token")
```

输出会显示：全量线性增长、压缩触顶、外部记忆恒定。**把这三条曲线画给你老板看，比任何架构图都有说服力**——它同时解释了钱花在哪和体验差在哪。

### 实验 3：MCP 工具注册的开放格式

```python
# 一个 MCP server 的声明长这样（简化版）：工具自描述，随处可挂
MCP_SERVER = {
    "name": "hr-knowledge",
    "version": "1.0.0",
    "tools": [
        {"name": "search_policy", "description": "检索公司制度",
         "inputSchema": {"type": "object",
                         "properties": {"q": {"type": "string"}},
                         "required": ["q"]}},
        {"name": "submit_leave", "description": "提交请假申请（副作用，需人审）",
         "inputSchema": {"type": "object",
                         "properties": {"days": {"type": "integer"},
                                        "type": {"type": "string"}},
                         "required": ["days", "type"]}},
    ],
}

# 你的 Agent 只要认这个格式，就能挂上任何 MCP server
def mount(server, allowed: list[str]):
    """只挂载白名单内的工具——副作用工具默认不挂"""
    return [t for t in server["tools"] if t["name"] in allowed]

print("默认挂载:", [t["name"] for t in mount(MCP_SERVER, allowed=["search_policy"])])
print("申请后挂载:", [t["name"] for t in mount(MCP_SERVER, allowed=["search_policy", "submit_leave"])])
```

**注意默认白名单里没有 `submit_leave`。** 这个函数就是"Agent 的权限模型"——和你的系统里"按钮级权限"是完全一样的设计。

## 费曼复述卡

1. 用"存储金字塔"向上司解释三层记忆：工作记忆 / 会话压缩 / 长期记忆各解决什么、各花多少钱。
2. 上下文压缩和外部记忆的区别是什么？为什么说压缩"只是忘得更慢"？
3. 生产级 Agent 比你 14 篇的 Demo 多了哪六个模块？其中哪三个是你的 Java 老本行直接平移的？

三题过不了，把实验 1 的 `extract_fact` 换成真调一次小模型——你会发现 Tier3 的真实成本在于"抽取得准不准"。

## 今日一句话

> 生产级 Agent = 网关 + 编排 + 三层记忆 + 混合检索 + MCP 工具 + 观测六件套——除模型外，每个模块你都在 Java 里造过。

---

下一篇：[21 · 评测：别问三个问题就说"还行"](./21-evaluation.md)（返回 [目录](./index.md)）
