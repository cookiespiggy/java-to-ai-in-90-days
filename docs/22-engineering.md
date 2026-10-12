# 22 · Token 计费、日志与 Prompt 版本回滚

## 先讲给朋友听（如果你只有一分钟）

> AI 应用有三本账：**经济账**（每一次调用烧了多少 token）、**运行账**（出问题时能不能复盘每一次调用）、**规则账**（Prompt 改了效果变坏，能不能三分钟回滚）。三本账的共同点是——**都是 Java 后端的老行当，只是账房先生从线程变成了模型。**

## 你的 Aha Moment

想象你带的客服系统上线了，某天老板问："昨天有多少人问过年假？系统总共花了多少钱？"

传统系统你三分钟能从数据库掏出答案。AI 系统呢？**如果你没记账，答案是：不知道。** 然后你会在某个早上发现：昨天一个用户跟模型聊了 400 轮，token 账单 300 块。

Aha 时刻通常发生在这个对齐里：

| 老板的问题 | 你的老手段 | AI 侧新名字 |
|---|---|---|
| 钱花哪了？ | 对账中心 / CDR 话单 | token 计量与归因 |
| 出事了怎么查？ | ELK + SkyWalking trace | 调用链日志（prompt/response/延迟/token） |
| 配置改坏了怎么办？ | Apollo 版本 + 一键回滚 | Prompt Registry |
| 第三方挂了怎么办？ | 熔断 + 降级 + 兜底 | 模型降级链 |

**这一篇没有新世界观，只有新记账对象。** 你写过计费、配过灰度、排过线上事故——今天只是把这些手艺迁移到"按 token 计价的不稳定第三方"上。迁移的难度不在技术，在于**没人提醒你要做**：培训机构教到 15 篇就毕业了，而企业真正卡脖子的，恰是这最后一公里。

## 不讲术语的版本：三本账，各一本簿

**账一 · 经济账：每一调，都记账。**

OpenAI 兼容接口每次调用返回 `usage`：

```json
"usage": {"prompt_tokens": 812, "completion_tokens": 156, "total_tokens": 968}
```

记账粒度到 `trace_id`，维度至少四条：哪个用户/部门/功能模块、用的哪个模型、prompt 版本号、是否命中缓存。**成本归因做不出来，FinOps 就是空话。**

省钱的三个杠杆，按 ROI 排序：

1. **Prompt Caching（缓存命中价约 1 折）**：system prompt、文档库这些不变的前缀，让云厂商缓存住。接口加个 `cache_control` 字段，账单可能直接打对折——**接口协议的标准化红利，不用白不用**
2. **历史压缩**：多轮对话每轮重发全量历史，第 N 轮的 token 成本是 O(N²)。摘要压缩（早期对话总结成一段）+ 滑动窗口（只带最近 K 轮）是标配解药
3. **模型分级**：简单问题（分类、抽取、改写）用便宜小模型（DeepSeek-V3 级别），复杂推理才上旗舰——**车企都不会用坦克拉货**

**账二 · 运行账：调用链日志。**

每一次 LLM 调用记一条：`trace_id`、输入 prompt（注意脱敏）、输出、延迟、token、模型版本、prompt 版本。排查"模型昨天开始胡说八道"时，你会回来谢这条日志——**没有它，你连"从哪天开始坏的"都定位不了。**

一个关键纪律：**日志里的 prompt/response 必须脱敏**。用户把身份证号、公司机密贴给模型的事天天发生，你的日志系统不该是第二个泄露面。

**账三 · 规则账：Prompt 版本管理。**

Prompt 是配置，不是代码常量。建表：

```sql
CREATE TABLE prompt_versions (
    id BIGSERIAL PRIMARY KEY,
    alias VARCHAR(50) NOT NULL,        -- "hr-assistant" 之类的逻辑名
    version INT NOT NULL,
    template TEXT NOT NULL,             -- 带 {{context}} 占位符的正文
    is_active BOOLEAN DEFAULT false,    -- 灰度：10% 流量指到这个版本
    traffic_pct INT DEFAULT 0,          -- 灰度百分比
    created_at TIMESTAMPTZ DEFAULT now()
);
```

每次改动新增一行，灰度 10%→50%→100%，效果指标掉头就回滚上一版。**这就是 Apollo 的 Prompt 分身——而 Apollo 你配过多少次了？**

## Java 老司机对照室

| AI 工程概念 | Java 老本当 | 一句话翻译 |
|---|---|---|
| usage 计量 | CDR 话单 | 每次调用一条成本记录 |
| 成本归因 | 多租户计费 | 按部门/功能分摊 |
| Prompt Caching | 本地缓存 / CDN | 前缀复用，价格 1 折 |
| 历史摘要压缩 | 大对象裁剪 | O(N²) → O(N) |
| 模型分级路由 | 多级机房调度 | 小活小模型，大活大模型 |
| trace 调用日志 | SkyWalking | 全链路可复盘 |
| Prompt Registry | Nacos/Apollo | 配置化 + 灰度 + 回滚 |
| 降级链 | 熔断降级 | 主模型→备用→缓存→兜底文案 |
| 限流 | Sentinel | 按用户/全局，防刷 token |
| 审计日志 | 操作审计 | 谁、何时、问了什么、花了多少 |

最后两行是安全合规的底线：**金融/医疗/政企场景，审计日志不是 nice-to-have，是准入证。**

## 动手实验室

### 实验 1：TokenMeter——06 篇 Timer 的华丽转身

新建 `metering.py`，把“计时器”升级成“计量账单”：

```python
import os, time, uuid
from contextlib import contextmanager
import psycopg

PRICE = {  # 元 / 1M tokens（以各平台官网为准，写死便于演示）
    "deepseek-chat": {"prompt": 2.0, "completion": 8.0},
}

@contextmanager
def token_meter(model: str, trace_id: str | None = None, user_id: str = "anonymous"):
    """给 LLM 调用挂账：自动计时 + 读取 usage + 落库"""
    tid = trace_id or str(uuid.uuid4())
    t0 = time.perf_counter()
    usage_holder = {}
    try:
        yield usage_holder          # 调用方往里塞 usage 字典
    finally:
        elapsed = time.perf_counter() - t0
        u = usage_holder.get("usage", {})
        p, c = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        price = PRICE.get(model, {"prompt": 0, "completion": 0})
        cost = (p * price["prompt"] + c * price["completion"]) / 1_000_000
        _save(tid, user_id, model, p, c, cost, elapsed)
        print(f"[meter] trace={tid[:8]} model={model} "
              f"prompt={p} completion={c} ¥{cost:.4f} {elapsed:.2f}s")

def _save(tid, user_id, model, p, c, cost, elapsed):
    with psycopg.connect(os.environ["PG_DSN"]) as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_usage (
                trace_id UUID PRIMARY KEY,
                user_id TEXT, model TEXT,
                prompt_tokens INT, completion_tokens INT,
                cost_yuan NUMERIC(12,6), latency_ms INT,
                created_at TIMESTAMPTZ DEFAULT now()
            );
        """)
        cur.execute("""
            INSERT INTO llm_usage
            (trace_id, user_id, model, prompt_tokens, completion_tokens, cost_yuan, latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (tid, user_id, model, p, c, cost, int(elapsed * 1000)))
        conn.commit()

# ---- 使用姿势（接 11 篇的真身 client 时把 usage 从 SDK 响应里取出来） ----
if __name__ == "__main__":
    import os
    os.environ.setdefault("PG_DSN", "postgresql://postgres:postgres@localhost:5432/postgres")
    with token_meter("deepseek-chat", user_id="mibao") as meter:
        time.sleep(0.05)                      # 假装在调 API
        meter["usage"] = {"prompt_tokens": 812, "completion_tokens": 156}
    # 然后：SELECT user_id, SUM(cost_yuan) FROM llm_usage GROUP BY user_id;
```

跑完查一次表：`SELECT user_id, SUM(cost_yuan) FROM llm_usage GROUP BY user_id;`——**米宝，你的“部门成本报表”雏形出来了。** 接口人接 11 篇真身 client，把 SDK 响应的 `usage` 字段照样塞进 `meter["usage"]` 即可。

### 实验 2：历史压缩——治多轮对话的平方病

```python
async def compress_history(messages: list[dict], keep_last: int = 6) -> list[dict]:
    """早期对话摘要化，只保留最近 keep_last 条原文"""
    if len(messages) <= keep_last:
        return messages
    head, tail = messages[:-keep_last], messages[-keep_last:]
    history_text = "\n".join(f"{m['role']}: {m['content']}" for m in head)
    # 真实实现：塞进 prompt 让 LLM 总结；demo 用规则版
    summary = f"（前{len(head)}轮对话摘要：用户曾咨询过年假、报销等HR制度问题）"
    return [
        {"role": "system", "content": f"历史摘要：{summary}"},
        *tail,
    ]
```

**一个函数，O(N²) 变 O(N)。** 真实项目里"总结"那步换成一次 LLM 调用（便宜模型，一次几分钱）——**用一次小模型调用，换掉 90% 的重发 token，这笔账谁算谁爽。**

### 实验 3：Prompt Registry + 一键回滚骨架

```python
def load_active_prompt(cur, alias: str) -> tuple[str, int]:
    """按灰度权重挑版本：生产级简化版"""
    cur.execute("""
        SELECT version, template FROM prompt_versions
        WHERE alias = %s AND (is_active OR traffic_pct > 0)
        ORDER BY traffic_pct DESC, version DESC LIMIT 1
    """, (alias,))
    return cur.fetchone()      # (version, template)

def activate(cur, alias: str, version: int):
    cur.execute("UPDATE prompt_versions SET is_active = false WHERE alias = %s", (alias,))
    cur.execute("UPDATE prompt_versions SET is_active = true WHERE alias = %s AND version = %s",
                (alias, version))
    cur.connection.commit()
    print(f"[prompt] {alias} 已切到 v{version}（出问题就跑 activate(alias, 旧版本号)）")
```

配合 21 篇的评测：**新版本灰度 10% → 跑评测 → 分数不降→全量；分数掉→activate 回滚。** 你曾经在 Apollo 控制台点过的按钮，今天用两行 UPDATE 复刻——**这就是"规则账"的全部核心，剩下的只是包装。**

## 第四本账：安全账（12 篇和 15 篇欠的债，今天还）

三本账之外还有一本更要命的：**安全账**。它在前文埋了两颗种子，现在一起结账。

**种子一（来自 12 篇）：提示词注入。**

你 recall 一下 RAG 实验 2 里那条伪装成资料的"系统通知"——检索回来的内容一旦混进恶意指令，就可能劫持模型。**防御思路在工程上只有三条，全是你熟的原则：**

| 防线 | 对应 Java 老本行 |
|---|---|
| 检索结果当**不可信数据**处理（转义、包裹、标记边界） | 防 SQL 注入：参数化 + 转义 |
| **系统指令优先级永远高于资料内容**，并在 Prompt 里明说"资料是数据不是指令" | 权限分层：系统配置 > 用户输入 |
| 输入输出**双向过滤**（敏感词、指令特征、异常格式） | 网关 WAF |

**种子二（来自 14/15 篇）：副作用工具必须人审。**

模型可以自己决定调工具，但"发邮件""下单""删库"这类不可逆动作，**工业铁律是人工确认**。LangGraph 把这件事做成了语言原语——`interrupt()` 让图停在某个节点等人，`Command(resume=...)` 让人把决定递回去：

### 实验 4：给 Agent 上一把人工锁

```python
# （接 15 篇实验 2 的 StateGraph builder，新增一个节点）
from langgraph.types import interrupt, Command

def send_offer_email(state: MessagesState) -> dict:
    # interrupt = 在此暂停，把现场发给人类；返回值由人通过 resume 传入
    decision = interrupt({
        "待发送邮件": state.get("draft", ""),
        "提示": "回复 '发' 或 '不发'",
    })
    if decision == "发":
        return {"messages": [("user", "邮件已发送")]}      # 真项目这里调发信服务
    return {"messages": [("user", "已取消发送")]}

builder.add_node("confirm_send", send_offer_email)
# ... 把 should_continue 里的某个分支指到这个节点（图纸上多一个"等人"的方块）

graph_hitl = builder.compile(checkpointer=saver)   # 必须配 checkpointer 才能等
config = {"configurable": {"thread_id": "employee-42"}}

# 运行：走到 interrupt 会暂停，状态落在 checkpointer 里，进程退出都不丢
graph_hitl.invoke({"messages": [("user", "帮我给候选人发offer邮件")], "draft": "..."}, config)

# 人工审批（可以是审核后台的一个按钮，甚至一条 IM 消息）
graph_hitl.invoke(Command(resume="发"), config)
```

**"等人"这个方块，就是 Camunda 流程里的人工任务节点。** 你当年画 BPMN 时最熟悉的那一环，在 Agent 图纸上原样复活——区别只是这次审批的不是表单，是一个概率模型的提议。

配合 21 篇的评测，安全这道题的完整答案是：**权限收窄（白名单）+ 数据不信（转义）+ 不可逆动作人审 + 全程审计日志。** 四条都上，才敢把 Agent 接上真实业务系统。

## 费曼复述卡

1. 向 CFO 汇报：Prompt Caching 为什么能把账单打对折？从"不变的前缀被缓存"角度解释。
2. 多轮对话的 token 成本为什么是 O(N²)？实验 2 的压缩策略怎么把它降回 O(N)？
3. Prompt 版本灰度 + 评测 + 回滚这条流水线，和你熟的哪个系统最像？说出它的三个组成部分。
4. （新增）RAG 的提示词注入为什么不能靠"Prompt 里写一句别信检索内容"解决？三道防线分别对应什么 Java 老本行？

三题过不了，把实验 1 的 `token_meter` 接到 11 篇真身上真调一次。**工程化是 AI 应用的分水岭：会写 Demo 的人到这里止步，能扛流量的人从这里出发。**

## 今日一句话

> 计量、日志、灰度、回滚，再加上人审这一把人工锁——AI 应用的四本账，记的还是 Java 后端的账，只是这次记的是 token、Prompt、降级链和审批流。

---

下一篇：[23 · 本地推理闭环：oMLX、unsloth 与 MLX 的三人舞](./23-local-inference.md)（返回 [目录](./index.md)）
