# 14 · Agent：让模型学会自己用工具

## 先讲给朋友听（如果你只有一分钟）

> 模型是个"没有手的学霸"——你问他天气，他只能瞎猜；你递给他一部手机（工具），告诉他"这按钮查天气"，他学会了自己按。Agent 就是给学霸配工具的车间：**它自己决定按哪个按钮，看结果，再决定下一步。** 危险与精彩都在"它自己决定"这四个字上。

## 你的 Aha Moment

回到 04 篇实验 5，你二十行代码手搓的玩具：

```python
@tool
def get_weather(city: str) -> str:
    """查询指定城市的天气"""
    ...
```

当时我把话说得很满："这是 Agent 框架的心脏机制。" 今天兑现。

**Function Calling（工具调用）的全部真相，一句话：你把函数的"说明书"（JSON Schema）递给模型，模型用它来输出结构化的"调用指令"，你的代码执行，结果回填，模型基于结果继续下一步。**

```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定城市的天气",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市"}},
            "required": ["city"]
        }
    }
}]
```

模型返回的不是自然语言，是：

```json
{"name": "get_weather", "arguments": "{\"city\": \"北京\"}"}
```

**你的代码拿到这段，转成 `get_weather(city="北京")` 真调用。** Aha 了吗？——**"说明书"是契约，"arguments" 是参数，"你的代码执行" 是 RPC 框架。** 你这些年拆过的 Dubbo/gRPC 接口，和这玩意的结构一模一样：一份 IDL（这里是 JSON Schema 自动生成）、一次序列化调用、一次响应回传。

只不过"客户端"是个概率模型，它偶尔会：编一个不存在的函数名（幻觉）、参数类型传错、或者该调工具时偏偏直接唠嗑。**所以 Agent 工程 80% 的课题是：怎么让这个不靠谱的"客户端"学会可靠调用。** 验证、重试、兜底、护栏——又是你的老本行。

## 不讲术语的版本：ReAct 循环的一次心跳

Agent 的主循环，就是一篇论文的名字：**ReAct（Reason + Act）**。一次完整的心跳：

1. **Reason（想）**：模型看当前局势（用户问题 + 已有工具结果），输出一段思考："要回答年假，我得先查制度库"
2. **Act（做）**：模型输出 tool_call 指令，而不是最终答案
3. **Observe（看）**：你的代码执行工具，把结果作为新消息追加回对话
4. 回到 1，直到模型认为信息够了，输出最终答案（不再调工具，循环终止）

把一次心跳写成人话："**想 → 调用 → 看结果 → 再想**"。你 RuleEngine 里规则逐条命中、结果反馈给下一条规则的环路？同款结构。区别只在**决策者从你的 if-else 变成了概率模型**。

三个必须知道的工程真相：

**真相一：状态就是消息列表，别无其他。**

每轮循环，你把完整历史（system + user + 所有 assistant + tool 消息）再发一遍。所以"Agent 断点续跑"在协议层几乎免费——**存一下历史，重新开个循环就行**。这也是为什么 LangGraph 把"状态管理"看得那么重：表面是图，底下还是消息列表的持久化。

**真相二：护栏是生死线。**

- `max_iterations`：最多循环几轮？不设上限，模型可能"查天气→查天气→查天气"烧你半个月工资
- 工具白名单：模型只能调注册过的函数——**永远别干 `getattr(module, name)` 这种按名动态找函数的事**，它今天调用 `delete_db` 你一点不意外
- Human-in-the-loop：有副作用的工具（发邮件、下单、删数据）必须弹人工确认。**这条不是建议，是事故预防**

**真相三：多 Agent 不是越多越好。**

单 Agent 能解决的别拆多 Agent——每拆一个，就多一份状态同步开销、多一份 prompt 漂移风险。**"先让一个 Agent 稳到能上线，再谈协作"**，这是 2026 年工业界的共识刹车。

## Java 老司机对照室

| Agent 概念 | Java 老本行 | 一句话翻译 |
|---|---|---|
| tools / function schema | Dubbo IDL / OpenAPI | 契约描述，机器可读 |
| tool_calls 返回 | RPC 服务端响应 | 序列化的调用指令 |
| 本地执行 + 回填 | 客户端 Stub 执行 | 参数 → 真函数 → 结果 |
| ReAct 循环 | 规则引擎 + 动作反馈环 | 决策者换了，结构没变 |
| 消息历史 = 全部状态 | 会话状态机 | 无状态服务 + 可重放日志 |
| max_iterations | 熔断器 / 限流 | 防失控烧钱 |
| 工具白名单 | 接口权限表 | 最小授权原则 |
| Human-in-the-loop | 审批流节点 | 副作用前的人工闸门 |
| 多 Agent | 微服务编排 | 能不拆就不拆 |

最后一行值得念叨：**很多人把"多 Agent 协作"当先进生产力，工业界用两年时间证明了它多数时候是先进事故源。** 你的简历上写"设计过 N 个 Agent 协作"不如写"设计过一个扛过线上流量的单 Agent"。

## 动手实验室

### 实验 1：零 API 跑通 ReAct 心跳（Mock 版）

先把循环骨架跑起来，再填真身。新建 `agent_min.py`：

```python
from typing import Callable

# ---- 工具注册表（04 篇 @tool 的注册表正式版） ----
TOOLS: dict[str, Callable] = {}

def register(names):
    def deco(fn):
        fn.schema = {"name": fn.__name__, "doc": fn.__doc__}
        TOOLS[fn.__name__] = fn
        return fn
    return deco

@register(["看年假制度", "查年假"])
def query_leaves(q: str) -> str:
    """查询年假制度"""
    return "年假：满1年5天，满10年10天，满15年15天。"

@register(["查天气"])
def get_weather(city: str) -> str:
    """查询指定城市天气"""
    return f"{city}今天晴，25度。"

# ---- 模型替身：按套路模仿 LLM 决策（重点看结构，别笑它傻） ----
class FakeModel:
    def decide(self, messages: list[dict]) -> dict:
        user_q = messages[0]["content"] if messages else ""
        # 第一轮：判断该调哪个工具
        if not any(m["role"] == "tool" for m in messages):
            if any(k in user_q for k in ["年假", "假"]):
                return {"type": "tool_call", "name": "query_leaves", "args": {"q": user_q}}
            if "天气" in user_q:
                return {"type": "tool_call", "name": "get_weather", "args": {"city": "北京"}}
            return {"type": "final", "content": "（这个玩具只会年假和天气）"}
        # 有工具结果了：收尾
        obs = [m for m in messages if m["role"] == "tool"][-1]["content"]
        return {"type": "final", "content": f"根据工具查询：{obs}"}

# ---- ReAct 循环本体（真身 Agent 也只是把 FakeModel 换成 API） ----
def run_agent(model, question: str, max_iterations: int = 5) -> str:
    messages = [{"role": "user", "content": question}]
    for i in range(max_iterations):
        decision = model.decide(messages)
        if decision["type"] == "tool_call":
            name, args = decision["name"], decision["args"]
            print(f"  [第{i+1}轮] 调用工具 {name}({args})")
            result = TOOLS[name](**args)           # 本地执行！
            messages.append({"role": "assistant", "tool_call": (name, args)})
            messages.append({"role": "tool", "content": result})
        else:
            return decision["content"]
    return "[护栏触发] max_iterations 已达上限，强制终止（防止模型失控烧钱）"

if __name__ == "__main__":
    print(run_agent(FakeModel(), "我入职一年了，年假几天？"))
    print(run_agent(FakeModel(), "北京天气如何"))
    print(run_agent(FakeModel(), "你会唱跳rap吗"))
```

跑起来，看清三件事：

1. **`decision["type"] == "tool_call"` 是心跳开关**——模型说"调工具"就走调用分支，说"final"就收工
2. **`messages.append({"role": "tool", ...})` 是把观察结果喂回去的关键一步**——漏了它，模型永远不知道工具返回了啥（经典事故）
3. **末尾的 `max_iterations` 返回的是兜底文案**——护栏不是装饰，是真会触发的

### 实验 2：真身版骨架（需要 key）

把 `FakeModel.decide` 换成 OpenAI 兼容调用即可，骨架一字不改：

```python
import os, json
from openai import OpenAI

class RealModel:
    def __init__(self):
        self.client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                             base_url="https://api.deepseek.com")
        # 从注册表自动生成 tools 说明（真实项目用 fn.schema 转 JSON Schema）
        self.tools = [
            {"type": "function", "function": {
                "name": "query_leaves",
                "description": "查询年假制度",
                "parameters": {"type": "object",
                               "properties": {"q": {"type": "string", "description": "用户问题"}},
                               "required": ["q"]}}},
            {"type": "function", "function": {
                "name": "get_weather",
                "description": "查询城市天气",
                "parameters": {"type": "object",
                               "properties": {"city": {"type": "string"}},
                               "required": ["city"]}}},
        ]

    def decide(self, messages):
        resp = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,        # 原样回传，别加工
            tools=self.tools,
            temperature=0,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            # 关键：把 SDK 的 message 对象整个塞回历史（它自带 tool_call_id）
            return {"type": "tool_call", "name": tc.function.name,
                    "args": json.loads(tc.function.arguments),
                    "tool_call_id": tc.id,
                    "raw_assistant": msg.model_dump(exclude_none=True)}
        return {"type": "final", "content": msg.content}
```

⚠️ **这里有个 90% 的人会踩的协议坑，值得单独说：**

`tool` 消息必须带 `tool_call_id`，而且必须跟在一条**带 tool_calls 的 assistant 消息**后面——否则 API 直接返回 400。所以：

1. **assistant 消息要原样回传**，不能只留 `{"role":"assistant","content":""}`（那样等于抹掉了 tool_calls）
2. **tool 消息要带 id**：`{"role": "tool", "tool_call_id": tc.id, "content": result}`

```python
# 循环里对应的两行（对照实验 1 看差异）：
messages.append(decision["raw_assistant"])
messages.append({"role": "tool", "tool_call_id": decision["tool_call_id"],
                 "content": result})
```

**这就是"状态就是消息列表"这句话的真实重量**：那份列表不是随便拼的字符串，是有严格契约的协议数据。14 篇的玩具版用本地 tuple 存 tool_call 所以没事，一旦换成真 API，契约立刻生效。

**改动只有 `decide` 一个函数 + 循环里存消息的两行**——护栏、工具注册全部不动。这就是"替身模式"的分红：**你的测试不烧钱，你的骨架不过期。**

### 实验 2.5：真身跑通（作者实测，本地 4B 模型）

> 实验 2 那段`RealModel` 你可能存疑——**"真的能跑吗？"** 下面是一份作者实测跑通的完整项目，
> 模型用本地 Unsloth `Qwen3.5-4B-GGUF`，**零 API 费用**。

```
projects/agent-project/
├── README.md        ← 完整运行手册 + 踩坑记录
├── agent_react.py   ← 工具注册表 + 真身模型 + ReAct 循环 + 护栏
└── .env.example     ← 本地/云端双模式配置
```

作者实测输出（`uv run python agent_react.py`）：

```
后端: local  模型: unsloth/Qwen3.5-4B-GGUF
已注册工具: ['query_leaves', 'get_weather', 'calc_salary']

=== 问题1：需要调用工具 ===
  [第1轮] 调用工具 query_leaves({'q': '入职一年年假几天'})
根据规定，您入职满一年，年假为5天。

=== 问题2：需要多步推理 ===
  [第1轮] 调用工具 calc_salary({'days': '3', 'daily_wage': '500'})
3天 × 500元/天 = 1500元
所以，按每天500元算，您总共损失了 1500元。

=== 问题3：不需要工具 ===
我不会唱歌跳舞，但我可以陪你聊天、讲故事，或者帮你查天气、算工资损失等。
```

护栏也真触发过（`TEST_GUARDRAIL=1`）：

```
  [第1轮] 调用工具 query_leaves({'q': '死循环'})
  [第2轮] 调用工具 query_leaves({'q': '死循环'})
  [第3轮] 调用工具 query_leaves({'q': '死循环'})
[护栏触发] max_iterations 已达上限，强制终止（防止模型失控烧钱）
```

#### ⚠️ 这里有个 4B 模型才会犯的真实错误，值得你亲眼看一遍

问题 2 第一次跑的时候，**工具报参数错误**，模型自己在答案里手算并道歉："计算工具在处理参数时出现了错误"。

作者去排查，发现一个很有意思的现象——**同一个模型、同一个问题，单独测却是对的**：

```python
# 只挂一个工具 → 模型给整数
{"days": 3, "hourly": 500}      # ✅

# 三个工具同时在场 → 模型给字符串
{"days": "3", "hourly": "500"}  # ❌ Python: int 参数收到 str
```

**这才是本节最有价值的部分。** 先说清楚：**这不是"模型笨"，是两个问题叠加。**

**问题一：JSON Schema 的约束在小模型上不够强。** 你在 schema 里写了 `"type": "integer"`，
但 4B 不一定遵守——尤其在**工具数量变多、上下文变长**时，注意力被稀释，格式约束就松了。

**问题二：工具描述有歧义。** 参数名叫 `hourly`（时薪），用户问的却是"每天 500 元"。
语义冲突，模型只能猜。

**作者的修法（两个都要做，缺一不可）：**

```python
# 修法①：工具描述消除歧义——参数名直接说清单位
def calc_salary(days: int, daily_wage: int) -> int:
    """按请假天数和【每天】工资估算损失金额。参数 daily_wage 是「日薪」，不是时薪。"""
    return days * daily_wage

# 修法②：参数类型强校验兜底（生产环境必备）
def _coerce_args(fn, args):
    for k, v in args.items():
        if 参数注解是 int and isinstance(v, str):
            out[k] = int(v.strip())          # "3" → 3

# 修法③：把失败原因喂回模型，让它自愈
try:
    result = TOOLS[name](**_coerce_args(TOOLS[name], args))
except Exception as e:
    result = f"工具执行失败：{e}。请检查参数后重试或直接作答。"
```

> **一句话记住**：**永远不要相信模型给的参数类型。**
> 工具边界是最后一道防线，它必须假设上游是善意的、但会犯低级错误的。
>
> 这和 04 篇的 `@retry`、22 篇的熔断是同一个思路：**你永远不知道上游会不会抽风，
> 所以防线要建在自己这一侧。** 模型只是又一个不可靠的上游。

**顺便回答一个你一定会问的问题：4B 能上生产吗？**
作者实测下来——**能用，但稳定性明显不如云端旗舰**，参数类型错误就是典型表现。
**4B 适合本地跑通、演示、教学；真上生产，要么换更大的模型，要么把类型校验、护栏、兜底一层层补厚。**
这句话本身就是本书想教你的东西：**能力可以小，防线不能薄。**

### 实验 3：亲手让护栏触发

*（继续用实验 1 里那个 `agent_min.py`，在文件末尾追加下面这段——`StubbornModel` 要继承 `FakeModel` 才能用）*

```python
class StubbornModel(FakeModel):
    def decide(self, messages):
        return {"type": "tool_call", "name": "query_leaves", "args": {"q": "死循环"}}

print(run_agent(StubbornModel(), "测试护栏"))
```

输出应该是 `[护栏触发] max_iterations 已达上限...`。**亲手看过一次失控的现场，你以后给每个 Agent 加护栏都有了肌肉记忆。**

## 费曼复述卡

1. 用"没有手的学霸"比喻，向同事讲清 Function Calling 的四步：说明书→调用指令→本地执行→结果回填。
2. ReAct 循环的心跳四步是什么？为什么"消息历史就是全部状态"对架构师是个好消息？
3. `max_iterations` 防的是什么事故？还有哪两个护栏是上线 Agent 的必选项？

三题过不了，重跑实验 1 并逐行加注释。**下一篇把它画成流程图——LangGraph 登场，你会看到"图不过是这个循环的施工图"。

*想知道这个 Demo 离生产还差多远？第 20 篇专门回答：记忆、压缩、混合检索、MCP 工具、审计——一个都跑不掉。*

## 今日一句话

> Agent = 工具注册表 + ReAct 心跳 + 护栏三件套——你的规则引擎换了决策者，循环结构三十年没变。

---

下一篇：[15 · LangGraph：画一张会思考的流程图](./15-langgraph.md)（返回 [目录](./index.md)）
