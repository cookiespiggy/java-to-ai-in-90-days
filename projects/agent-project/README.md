# 14 篇 · 真实 ReAct Agent（本地模型驱动）

> 配套《Java 转 AI 的 90 天》第 14 篇 · **作者已实测跑通**（2026-10-12，Apple M5 Pro / 本地 Unsloth Qwen3.5-4B-GGUF / 零 API 费用）

## 这是什么

一个**真的由 LLM 驱动决策**的 Agent：模型自己决定调哪个工具、传什么参数，
工具在本地执行，结果喂回模型，直到它给出最终答案。

**和书里实验 1 的 FakeModel 只有一个函数的差别。** 护栏、工具注册表、ReAct 循环，一行没改——
这就是"替身模式"的红利：测试用替身不烧钱，上线用真身不过期。

## 快速开始

```bash
# 1. 配置（本地模型；云端见下方）
cp .env.example .env && chmod 600 .env
# 编辑 .env，至少填 LOCAL_KEY

# 2. 跑
uv init --python 3.11 && uv add openai python-dotenv
uv run python agent_react.py

# 3. 亲手看护栏触发
TEST_GUARDRAIL=1 uv run python agent_react.py
```

## 作者的实测输出

```
后端: local  模型: unsloth/Qwen3.5-4B-GGUF
已注册工具: ['query_leaves', 'get_weather', 'calc_salary']

=== 问题1：需要调用工具 ===
  [第1轮] 调用工具 query_leaves({'q': '入职一年年假几天'})
根据规定，您入职满一年，年假为5天。

=== 问题2：需要多步推理 ===
  [第1轮] 调用工具 calc_salary({'days': '3', 'daily_wage': '500'})
根据您提供的信息，您请了3天年假，每天工资损失为500元。
3天 × 500元/天 = 1500元
所以，按每天500元算，您总共损失了 1500元。

=== 问题3：不需要工具 ===
我不会唱歌跳舞，但我可以陪你聊天、讲故事，或者帮你查天气、算工资损失等。

=== 实验3：护栏触发测试 ===
  [第1轮] 调用工具 query_leaves({'q': '死循环'})
  [第2轮] 调用工具 query_leaves({'q': '死循环'})
  [第3轮] 调用工具 query_leaves({'q': '死循环'})
[护栏触发] max_iterations 已达上限，强制终止（防止模型失控烧钱）
```

## 踩坑记录：4B 模型给字符串参数（作者实测撞到）

**症状**：问题 2 第一次跑，模型输出 `{"days": 3, "hourly": 500}`（正确），
但工具报参数错误，模型自己在答案里手算并道歉。

**排查**——同一个模型，同一个问题，直接单测却是对的：

```python
# 只挂一个工具 → 模型给整数
{"days": 3, "hourly": 500}      ✅

# 三个工具同时在场 → 模型给字符串
{"days": "3", "hourly": "500"}  ❌
```

**结论不是"模型笨"，是两个问题叠加：**

1. **JSON Schema 的约束在小模型上不够强**。`"type": "integer"` 写在 schema 里，
   但 4B 不一定遵守，尤其在工具数量变多、上下文变长时。
2. **工具描述有歧义**。`hourly`（时薪）和"每天 500 元"语义冲突，模型只能猜。

**作者的修法（两个都要做）：**

```python
# 修法①：工具描述消除歧义——参数名直接说清单位
def calc_salary(days: int, daily_wage: int) -> int:
    """按请假天数和【每天】工资估算损失金额。参数 daily_wage 是「日薪」，不是时薪。"""
    return days * daily_wage

# 修法②：参数类型强校验兜底（生产环境必备）
def _coerce_args(fn, args):
    for k, v in args.items():
        if 参数注解是 int and isinstance(v, str):
            out[k] = int(v.strip())     # "3" → 3
    return out

# 修法③：把失败原因喂回模型，让它自愈
try:
    result = TOOLS[name](**_coerce_args(TOOLS[name], args))
except Exception as e:
    result = f"工具执行失败：{e}。请检查参数后重试或直接作答。"
```

> **一句话**：**永远不要相信模型给的参数类型。** 工具边界是最后一道防线，
> 它必须假设上游是善意的、但会犯低级错误的。

## 协议坑：`tool_call_id` 不能省

这是书里强调、本项目代码里也踩准了的一点：

```python
messages.append(decision["raw_assistant"])          # 整个 message 对象回传，自带 tool_calls
messages.append({"role": "tool",
                 "tool_call_id": decision["tool_call_id"],   # ← 这个 id 必须带上
                 "content": result})
```

省掉 `tool_call_id`，或者只存 `{"role":"assistant","content":""}`，
API 直接返回 400。**那份 messages 列表不是随便拼的字符串，是有严格契约的协议数据。**

## 本地 vs 云端

```bash
# 本地（默认）：零成本、数据不出内网
LLM_BACKEND=local
LOCAL_BASE_URL=http://127.0.0.1:53967/v1
LOCAL_MODEL=unsloth/Qwen3.5-4B-GGUF

# 云端：需要更好的工具调用能力时切
LLM_BACKEND=api
DEEPSEEK_API_KEY=sk-xxx
```

详见第 13 篇实验 3.5（同一套 `LLM_BACKEND` 机制）与第 23 篇。

**诚实说明**：4B 模型能用，但工具调用的稳定性明显不如云端旗舰——
上例中参数类型错误就是 4B 的典型表现。**4B 适合本地跑通、演示、教学；
生产用请换更大的模型，或加更多类型校验。**

## 文件说明

- `agent_react.py` — 工具注册表 + 真身模型 + ReAct 循环 + 护栏 + 字符串参数兜底，一个文件读完