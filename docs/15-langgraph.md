# 15 · LangGraph：画一张会思考的流程图

## 先讲给朋友听（如果你只有一分钟）

> 你 14 篇用二十行写的 while 循环，LangGraph 帮你做成了带图纸的流水线：每个环节是个盒子，连线决定往哪流，图纸能画出来、能存档、断电能续跑。更重要的是——**图纸本身，就是你和 PM 沟通 Agent 行为的语言**。

## 你的 Aha Moment

Stripping LangGraph，只剩下一个核心等式：

```
LangGraph = 14 篇的 while 循环 + 状态持久化 + 可视化图纸
```

先看"一行版"，直观感受代差：

```python
from langgraph.prebuilt import create_react_agent
agent = create_react_agent(model, tools=[query_leaves])   # 三行
```

**三行，就是你 14 篇整个 `run_agent` 的工业发行版。** ReAct 循环、工具调用、消息追加、终止判断，全在里面——因为 ReAct 已经是 Chat 接口暴露出来的通用模式，不需要你自己拼。

再看"手写版"，照照镜子：

```python
builder = StateGraph(MessagesState)
builder.add_node("model", call_model)                          # 14 篇的 model.decide
builder.add_node("tools", ToolNode([query_leaves]))            # 14 篇的 TOOLS[name](**args)
builder.add_edge(START, "model")
builder.add_conditional_edges("model", should_continue, ...)   # 14 篇的 if tool_call
builder.add_edge("tools", "model")                             # 回填消息后回到 model
graph = builder.compile()
```

**对照着 14 篇的 `run_agent` 逐行走：node = 循环体里的一个动作，conditional edge = `if decision["type"] == "tool_call"`，`add_edge("tools","model")` = 循环回跳。** 心跳结构一模一样。

那 LangGraph 多给了什么？三样你自己写循环时挠头的东西：

1. **状态容器 `MessagesState`**：消息列表的 append 合并规则内置了（reducer），你不再手写 `messages.append`
2. **Checkpointer**：图每次跑完一步，状态快照落库。进程重启、服务重启、换个节点跑，靠 `thread_id` 原样恢复——**这就是工作流引擎的"流程实例持久化"**
3. **中断与人审**：`interrupt()` 一句话让图暂停在某个节点，等人类审批，收到信号再 `Command(resume=...)` 续跑——审批流开箱即得

**Aha 的最后一层：如果你做过 Activiti/Camunda，这一幕很熟悉——BPMN 图纸上的方框是节点，箭头是流转，流程变量是状态，实例表是 checkpointer。** LangGraph 就是 LLM 时代的轻量工作流引擎，而这次，流程里的"人"变成了模型。

## 不讲术语的版本：三个新概念，三个老熟人

**概念一 · 图（Graph）= 节点 + 边。**

节点是函数（输入 state，输出 state 增量），边是流转规则。**有环**——这是它和 ETL 工具（DAG）的根本分水岭：LLM 的循环"想-做-看"就是环，DAG 画不出来。

**概念二 · 状态（State）= 全局变量。**

LangGraph 用 typing 定义的 TypedDict 当 state（最常用的是内置的 `MessagesState`：只有 `messages` 一个字段）。节点函数的入参出参就是 state 的读写。**它的 reducer 决定"增量怎么合进全局"**——`add_messages` reducer 就是"追加式合并"，新消息挂尾巴，不覆盖。

**概念三 · Checkpointer = 流程实例表。**

`compile(checkpointer=saver)` 之后，每次 `invoke(..., config={"configurable": {"thread_id": "user-42"}})`，这个 thread 的全部历史都进可恢复状态。**换服务器、重启、甚至三个月后回来接着聊，都是合法场景。** 无状态 HTTP 服务 + 有状态流程实例，这套结构你在 Camunda 里见过一万次。

## Java 老司机对照室

| LangGraph | Camunda/Activiti | LLM 特色差异 |
|---|---|---|
| StateGraph.builder | 流程定义器 | 节点是 LLM 决策 |
| Node（函数） | ServiceTask | LLM 可当节点本身 |
| Conditional Edge | 排他网关 XOR | 判断"要不要调工具" |
| Cycle（环） | BPMN 不太鼓励 | **核心特性**，ReAct 全靠它 |
| MessagesState | 流程变量 Map | 消息追加有专属 reducer |
| Checkpointer | 流程实例持久化 | 按 thread_id 隔离 |
| interrupt/Command | UserTask 人工任务 | 审批后 resume 续跑 |
| Subgraph | 子流程 CallActivity | 多 Agent 的官方组织方式 |
| Send / Fan-out | 并行网关 | 并行 fan-out 任务 |
| Command(goto=...) | 流程跳转 | 动态改流向 |

最后两行先眼熟，本篇用不上——**但多 Agent、并行任务、子图这些"高级玩具"的全家福，就是这张表。**

## 动手实验室

### 实验 0：安装（比你想的小）

```bash
uv add langgraph langchain-openai langchain-core
```

注意一个 2026 年的常识：**LangGraph 是编排层，模型调用层随便挑**——这里用 `langchain-openai`，改 `base_url` 即切 DeepSeek/通义/本地 Ollama。

### 实验 1：三行版先跑起来

```python
# agent_express.py
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

load_dotenv()

@tool
def query_leaves(q: str) -> str:
    """查询年假制度，输入是用户的原始问题"""
    return "年假：满1年5天，满10年10天，满15年15天。"

model = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com",
    api_key=os.environ["DEEPSEEK_API_KEY"],
    temperature=0,                      # 工具调用场景必须低温（14 篇的经验）
)

agent = create_react_agent(model, tools=[query_leaves])

result = agent.invoke({"messages": [("user", "我入职两年了，年假几天？")]})
print(result["messages"][-1].content)
```

跑完先干一件事：**把 Agent 的思考轨迹打出来看**。不加任何追踪工具，图自带的流式输出就能做到：

```python
for event in agent.stream({"messages": [("user", "我入职两年了，年假几天？")]},
                          stream_mode="updates"):
    for node_name, delta in event.items():
        print(f"[节点 {node_name}] {delta}")
```

你会看到一条完整轨迹：`agent` 节点输出 tool_call → `tools` 节点执行 query_leaves → 结果回填 → `agent` 再生成答案。**把这段输出截图发给 14 篇的自己看——这就是你二十行循环的 X 光片。**（想看更细的调用链再上 LangSmith/LangChain 追踪，代价是注册 key；日常调试用 `stream` 就够。）

### 实验 2：手写图版（这篇的正课）

```python
# agent_graph.py
import os
from typing import Literal
from dotenv import load_dotenv
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

load_dotenv()

@tool
def query_leaves(q: str) -> str:
    """查询年假制度，输入是用户的原始问题"""
    return "年假：满1年5天，满10年10天，满15年15天。"

model = ChatOpenAI(model="deepseek-chat", base_url="https://api.deepseek.com",
                   api_key=os.environ["DEEPSEEK_API_KEY"], temperature=0)
model_with_tools = model.bind_tools([query_leaves])   # 挂上"工具说明书"

# --- 节点：等价于 14 篇循环里的 model.decide ---
def call_model(state: MessagesState) -> dict:
    return {"messages": [model_with_tools.invoke(state["messages"])]}

# --- 条件边：等价于 14 篇的 if decision["type"] == "tool_call" ---
def should_continue(state: MessagesState) -> Literal["tools", END]:
    last = state["messages"][-1]
    return "tools" if last.tool_calls else END

builder = StateGraph(MessagesState)
builder.add_node("model", call_model)
builder.add_node("tools", ToolNode([query_leaves]))
builder.add_edge(START, "model")
builder.add_conditional_edges("model", should_continue, {"tools": "tools", END: END})
builder.add_edge("tools", "model")      # 回到 model = 循环回跳
graph = builder.compile()

print(graph.get_graph().draw_ascii())    # 打印 ASCII 图纸！

result = graph.invoke({"messages": [HumanMessage(content="我入职两年了，年假几天？")]})
print(result["messages"][-1].content)
```

`draw_ascii()` 那一行务必跑：**你会看到一张活的图纸——model 和 tools 两个盒子、一条双向箭头、一个条件分叉。** 那个环，就是 ReAct。这张图可以直接贴进 PPT 给 PM 讲架构，比任何文字都直观。

### 实验 3：持久化 + 人审（企业级日常）

```python
from langgraph.checkpoint.postgres import PostgresSaver

# 复用 13 篇的 PG！checkpoint 表和业务表共库
with PostgresSaver.from_conn_string(os.environ["PG_DSN"]) as saver:
    saver.setup()

    graph_with_cp = builder.compile(checkpointer=saver)
    config = {"configurable": {"thread_id": "employee-42"}}   # 会话隔离键

    # 第一次：跑到一半，进程OVER
    # 第二次：同样 config，从断点续跑，历史全在
    r1 = graph_with_cp.invoke({"messages": [("user", "年假几天？")]}, config)
    r2 = graph_with_cp.invoke({"messages": [("user", "那病假呢？")]}, config)
```

**多轮对话"服务器忘性大"的问题，在 LangGraph 里是一个 `checkpointer` 的问题。** 而审批流版本（`interrupt()`）等你 17 篇工程化时跟"副作用工具确认"一起用——现在的你，先记住图纸上可以画一个"等人"的盒子。

## 费曼复述卡

1. 对照 14 篇的 `run_agent`，说出 LangGraph 里 node / conditional edge / cycle 各自对应循环里的哪一行。
2. 为什么说 LangGraph 是"LLM 时代的轻量工作流引擎"？从 Camunda 的三个概念映射。
3. Checkpointer 解决什么问题？为什么 `thread_id` 是设计上的必需品而不是摆设？

三题过不了，把实验 2 的图纸对照实验 1 的代码逐行比。**下一篇开始收口工程化——你 Java 的老本行，最后的战场。**

## 今日一句话

> LangGraph 把 while 循环画成施工图：节点是动作，环是思考，checkpoint 是存档点——而流程图，本来就是工程师的世界语。

---

下一篇：[16 · 生产级检索：混合检索、RRF、Rerank 与权重](./16-advanced-retrieval.md)（返回 [目录](./index.md)）
