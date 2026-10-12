"""14 篇 · 真实 ReAct Agent（本地模型驱动，零 API 费用）

和书里实验 1 的 FakeModel 唯一的差别：decide() 从"按套路模仿"换成真模型调用。
护栏、工具注册表、循环骨架，一行没改。

这就是"替身模式"的分红：测试用替身不烧钱，上线用真身不过期。
"""
from __future__ import annotations

import json
import os
from typing import Callable

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ---- 工具注册表（04 篇 @tool 的注册表正式版）----
TOOLS: dict[str, Callable] = {}


def register(names: list[str]):
    """注册一个工具。names 是给模型看的中文别名。"""
    def deco(fn: Callable) -> Callable:
        fn.schema = {"name": fn.__name__, "doc": fn.__doc__, "aliases": names}
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


@register(["算工资损失", "算钱"])
def calc_salary(days: int, daily_wage: int) -> int:
    """按请假天数和【每天】工资估算损失金额。参数 daily_wage 是「日薪」，不是时薪。"""
    return days * daily_wage


# ---- OpenAI 兼容客户端：云端 / 本地双模式（与 13 篇 llm_backend.py 同构）----
BACKEND = os.environ.get("LLM_BACKEND", "local")


def _client() -> OpenAI:
    if BACKEND == "local":
        return OpenAI(
            api_key=os.environ.get("LOCAL_KEY", "EMPTY"),
            base_url=os.environ.get("LOCAL_BASE_URL", "http://127.0.0.1:8000/v1"),
        )
    return OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )


def _model_name() -> str:
    if BACKEND == "local":
        return os.environ.get("LOCAL_MODEL", "Qwen2.5-0.5B")
    return "deepseek-chat"


def _coerce_args(fn: Callable, args: dict) -> dict:
    """把模型给的字符串数字转成 int（4B 模型经常给 "3" 而不是 3）。

    实测：单独调用时模型给整数；三个工具同时在场时经常给字符串。
    这不是模型的错，是 JSON Schema 约束在小模型上不够强——生产环境必须兜这一层。
    """
    import inspect
    out = {}
    for k, v in args.items():
        expect = inspect.signature(fn).parameters[k].annotation
        if expect is int and isinstance(v, str):
            try:
                out[k] = int(v.strip())
                continue
            except ValueError:
                pass
        out[k] = v
    return out


def _params(fn: Callable) -> dict[str, str]:
    """从签名推出参数类型（够用的极简版，生产项目用 pydantic）"""
    import inspect
    out = {}
    for p in inspect.signature(fn).parameters.values():
        out[p.name] = "integer" if p.annotation is int else "string"
    return out

# 从注册表自动生成 JSON Schema——加工具只改装饰器，这里不用动
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": (fn.__doc__ or "").strip(),
            "parameters": {
                "type": "object",
                "properties": {
                    p: {"type": t} for p, t in _params(fn).items()
                },
                "required": list(_params(fn).keys()),
            },
        },
    }
    for name, fn in TOOLS.items()
]




class RealModel:
    """真身：把书里实验 2 那段原封不动搬过来"""

    def __init__(self) -> None:
        self.client = _client()
        self.model = _model_name()
        self.tools = TOOL_SCHEMAS

    def decide(self, messages: list[dict]) -> dict:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,        # 原样回传，别加工
            tools=self.tools,
            tool_choice="auto",
            temperature=0,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            return {
                "type": "tool_call",
                "name": tc.function.name,
                "args": json.loads(tc.function.arguments),
                "tool_call_id": tc.id,
                # 关键：整个 message 对象回传，它自带 tool_calls 和 id
                "raw_assistant": msg.model_dump(exclude_none=True),
            }
        return {"type": "final", "content": msg.content}


def run_agent(model, question: str, max_iterations: int = 5) -> str:
    """ReAct 循环本体——和书里实验 1 完全一致"""
    messages = [{"role": "user", "content": question}]
    for i in range(max_iterations):
        decision = model.decide(messages)
        if decision["type"] == "tool_call":
            name, args = decision["name"], decision["args"]
            print(f"  [第{i + 1}轮] 调用工具 {name}({args})")
            try:
                result = TOOLS[name](**_coerce_args(TOOLS[name], args))
            except Exception as e:
                # 把失败原因喂回模型，让它自己纠正——这是 Agent 的自愈能力
                result = f"工具执行失败：{type(e).__name__}: {e}。请检查参数后重试或直接作答。"
            # ⚠️ 协议坑：tool 消息必须带 tool_call_id，且跟在带 tool_calls 的 assistant 之后
            messages.append(decision["raw_assistant"])
            messages.append({"role": "tool", "tool_call_id": decision["tool_call_id"],
                             "content": result})
        else:
            return decision["content"]
    return "[护栏触发] max_iterations 已达上限，强制终止（防止模型失控烧钱）"


if __name__ == "__main__":
    print(f"后端: {BACKEND}  模型: {_model_name()}")
    print(f"已注册工具: {list(TOOLS)}")

    # 1. 该调工具的问题
    print("\n=== 问题1：需要调用工具 ===")
    print(run_agent(RealModel(), "我入职一年了，年假几天？"))

    # 2. 需要计算的问题（多步：先查制度再算钱）
    print("\n=== 问题2：需要多步推理 ===")
    print(run_agent(RealModel(), "我入职10年，请了3天年假，按每天500元算损失我多少钱？"))

    # 3. 不该调工具的问题——护栏不该触发，模型该直接答或说不知道
    print("\n=== 问题3：不需要工具 ===")
    print(run_agent(RealModel(), "你会唱歌跳舞吗？"))
# ---- 实验 3：亲手让护栏触发（书里实验 3 的真实模型版）----
class StubbornModel:
    """永远想调工具的模型——用来验证护栏真的会拦"""
    def decide(self, messages):
        return {"type": "tool_call", "name": "query_leaves",
                "args": {"q": "死循环"},
                "tool_call_id": "fake-id", "raw_assistant": {"role": "assistant"}}


if os.environ.get("TEST_GUARDRAIL") == "1":
    print("\n=== 实验3：护栏触发测试 ===")
    print(run_agent(StubbornModel(), "测试护栏", max_iterations=3))
