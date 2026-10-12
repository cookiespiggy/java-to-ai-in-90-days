# 11 · 第一次调用：写一个带重试的流式对话接口

## 先讲给朋友听（如果你只有一分钟）

> 调大模型 API，就是发一个 POST 请求、收一个 JSON 响应——跟你对接过的所有第三方接口没区别。唯一的新鲜事：这个响应用"滴灌"的方式回来，一个字一个字往外渗。而你在第 05 篇学的 `yield`，就是接住这股滴灌的杯子。

## 你的 Aha Moment

今天是一个仪式感时刻。翻开你的笔记：

- 第 04 篇，你写了 `@retry`——给 flaky API 失败重试
- 第 05 篇，你写了 `yield`——旋转寿司的暂停键
- 第 07 篇，你写了 `asyncio.gather`——三路并发等 IO

当时你都问过同一个问题："这些黑魔法，到底什么时候用？"

**今天。**

```python
for chunk in client.chat_stream("介绍一下你自己"):
    print(chunk, end="", flush=True)
```

看见这个 `for chunk in` 了吗？**它是 05 篇 `fake_llm_stream` 的真身。** 当年你在 `fake_llm_stream` 里 `yield word` 的位置，现在换成 SDK 里真的 HTTP 字节流。看见接口超时时的重试了吗？**它是 04 篇 `@retry` 的转正。** 看见并发问三个问题了吗？**它是 07 篇 `asyncio.gather` 的开工。**

Java 老工程师的 Aha 通常在此时升华为一句感叹：**"原来我之前不是在学习三个孤立技巧，是在攒一个系统的三块拼图。"**

这就是本书编排的野心——**语法为工程让路，工程为场景正名。** 今天之后，前三阶段的每一行代码你都有了名分。

## 不讲术语的版本：一次调用的全生命周期

**1. OpenAI 兼容协议：AI 界的 REST 标准。**

2023 年 OpenAI 定义了 Chat Completions 接口格式（`/v1/chat/completions`），发这样的 JSON：

```json
{
  "model": "deepseek-chat",
  "messages": [
    {"role": "system", "content": "你是资深Java架构师"},
    {"role": "user", "content": "用一句话解释一句话解释熔断"}
  ],
  "temperature": 0.3
}
```

离谱又好用的事发生了：**这个格式成了行业标准**。DeepSeek、通义千问、智谱、Moonshot、Kimi、甚至本地 Ollama 部署的开源模型，全部吃这一套。切换模型 = 改一个 `base_url` 和 `api_key`。

**用你熟悉的黑话翻译：这就是一次跨厂商的 REST 接口标准化。** 你 Java 时代对接过支付宝、微信支付、银联，每家一套 SDK 一个协议；AI 圈少见地达成了统一——因为最先发布的接口赢了。

**2. 三个角色，一次会话。**

`messages` 里三种角色：

- `system`：岗位说明书，每轮对话都强制前置。"你是XX助手，用中文回答"写这儿
- `user`：用户说的话，每轮塞最新一条
- `assistant`：模型之前的回答——**你要自己把模型上一轮的回复塞回去**，因为（09 篇警告过的）模型无状态

**多轮对话的真相：不是"接着聊"，是"每轮把全部历史重抄一遍发过去"。** 你 append 三条消息发一次，模型回一条，你再 append 四条发一次——这样的卫生习惯，第 22 篇会进化成"历史摘要压缩"。

**3. stream=True：滴灌模式。**

请求里加 `"stream": true`，响应就从"一个完整 JSON"变成"一串 SSE 事件流"：

```
data: {"choices":[{"delta":{"content":"熔"}}]}
data: {"choices":[{"delta":{"content":"断"}}]}
data: {"choices":[{"delta":{"content":"是"}}]}
...
data: [DONE]
```

每个 `data:` 行是一个 chunk，`delta` 里带着增量文本。**SDK 帮你把这些字节流转成 Python 可迭代对象——于是 `for chunk in ...` 自然成立，`yield` 只需要在生成器里再转发一层。**

**4. 错误就是 HTTP 的老朋友。**

- 429：限流——退避重试（`@retry` 的主场）
- 5xx：模型服务抖动——重试 + 降级到备用模型
- timeout：长文本生成可能几十秒——你的超时预算要按 token 生成速度估
- context_length_exceeded：塞太多——触发 RAG 优化的信号弹

## Java 老司机对照室

| LLM API 场景 | Java 老本行 | 一句话翻译 |
|---|---|---|
| Chat Completions 格式 | REST + DTO | 标准 POST + JSON |
| system/user/assistant 轮 | 会话上下文对象 | 每轮全量重发，模型无状态 |
| `stream: true` | SSE / WebFlux Flux | 服务端推送，客户端 for 循环消化 |
| `for chunk in stream` | 05 篇生成器 | 可迭代对象，走一个收一个 |
| 429 退避重试 | 04 篇 @retry | 指数退避 + 最大次数 |
| timeout 预算 | 熔断器阈值 | P99 延迟 × 安全系数 |
| base_url 切换 | 多租户配置 | 换模型不动业务代码 |
| usage.final 统计 | 成本归因日志 | 每调一次记一次账 |
| function calling | RPC 定义 | 下次课（第 14 篇） |

最后一行先剧透：`tools` 参数能把你的函数 Schema 告诉模型，让模型决定"要不要调用"、传什么参——**那就是 Agent 的起点，我们今天先把地基浇完。**

## 动手实验室

### 实验 0：准备环境

```bash
uv add openai          # 官方 SDK，兼容所有 OpenAI 格式服务
```

申请一个 key 备用（**都有免费额度**）：

- DeepSeek：`platform.deepseek.com`（国内直连，推荐首选）
- 阿里百炼：`bailian.console.aliyun.com`（通义千问）
- 智谱：`open.bigmodel.cn`（GLM）

> ⚠️ **本篇用云端 API 教学，是为了让你看懂协议长什么样，不是说你必须充值。**
>
> 凡是 OpenAI 兼容服务——**包括你自己电脑上跑的那个**——都能用同一份代码调。
> 有了本地模型（第 23 篇）之后，把 `base_url` 换成 `http://127.0.0.1:8000/v1`、
> `api_key` 填 `"EMPTY"`（本地不校验），就完全不用花一分钱。
>
> 第 13 篇的实验 3.5 有一份**实测过的双模式适配层**，云端/本地一行环境变量切换，
> 作者用本地 Qwen3.5-4B-GGUF 把整套 RAG 问答跑通了（0.3~2.3 秒/问）。
>
> > 一句话：**协议是公共的，key 是私有的。学会协议，别被某个服务绑死。**

> 安全提醒（第 02 篇纪律的延伸）：**key 永远不写进代码**，放环境变量：
> ```bash
> export DEEPSEEK_API_KEY="sk-..."
> ```

### 实验 1：完整工程骨架（无 key 也能跑通结构）

新建 `llm_client.py`。**注意这个文件的设计**：默认用内置 Mock，零 key 可运行、可测结构；有 key 时换真身。这是团队里 review 通过的写法——**依赖可替换，测试不烧钱**。

```python
import os, time, random
from typing import Iterator

# ---------- 04 篇的 @retry 返场：指数退避重试 ----------
def retry(max_attempts=3, backoff=1.5):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"[retry] 第{attempt}次失败: {type(e).__name__}: {e}")
                    if attempt == max_attempts:
                        raise
                    time.sleep(backoff ** attempt)
        return wrapper
    return decorator


class MockLLMClient:
    """无 key 也能跑的替身演员：模拟网络延迟和 token 滴灌"""

    def chat_stream(self, prompt: str) -> Iterator[str]:
        reply = f"关于「{prompt}」，我的回答是：大模型本质是读完全互联网的接话机器……"
        for word in reply.split():
            yield word + " "
            time.sleep(0.03)          # 模拟模型"打字"节奏


class RealLLMClient:
    """真身：openai SDK + DeepSeek（OpenAI 兼容协议）"""

    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",   # 换模型只改这一行
        )

    def chat_stream(self, prompt: str):
        stream = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是资深Java架构师，回答精炼"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            stream=True,               # 滴灌模式的开关
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content


class LLMClient:
    """统一入口：有 key 走真身，没 key 走替身"""

    def chat_stream(self, prompt: str) -> Iterator[str]:
        client = RealLLMClient() if os.environ.get("DEEPSEEK_API_KEY") else MockLLMClient()
        return client.chat_stream(prompt)

    @retry(max_attempts=3, backoff=1.5)     # 只给非流式入口上重试（见实验 4 说明）
    def chat(self, prompt: str) -> str:
        return "".join(self.chat_stream(prompt))


if __name__ == "__main__":
    print("流式回答:")
    for chunk in LLMClient().chat_stream("解释一下熔断"):
        print(chunk, end="", flush=True)
    print("\n\n串行完整回答:", LLMClient().chat("再解释一下限流"))
```

```bash
uv run python llm_client.py
```

观察三件事：

1. **文字是一个词一个词蹦出来的**——`for chunk in` + `yield`，05 篇的旋转寿司开张
2. **有 key 时切真身只差一个环境变量**——base_url 标准化带来的水切换
3. **`chat()` 和 `chat_stream()` 双入口**——"我要完整结果"和"我要逐字播报"两个产品姿势，都从同一个底层长出来

### 实验 2：三路并发（07 篇 asyncio 的真身版）

*（接着实验 1 的 `llm_client.py` 往下写，`LLMClient` 直接复用）*

```python
import asyncio

async def ask(client, question):
    loop = asyncio.get_running_loop()
    # SDK 是同步的，用 07 篇学到的 to_thread 桥进异步世界
    parts = await loop.run_in_executor(None, lambda: list(client.chat_stream(question)))
    return question, "".join(parts)

async def main():
    client = LLMClient()
    t0 = time.perf_counter()
    results = await asyncio.gather(
        ask(client, "解释RAG"),
        ask(client, "解释Agent"),
        ask(client, "解释微调"),
    )
    for q, a in results:
        print(f"Q: {q}\nA: {a[:40]}...\n")
    print(f"三问并发总耗时: {time.perf_counter() - t0:.2f}s")

asyncio.run(main())
```

**同步 SDK 进异步世界，过桥费就是 07 篇实验 4 的 `run_in_executor`。**（进阶爱好者：SDK 的异步版本 `AsyncOpenAI` 原生 `await`，用 `async for chunk in stream` 即可，思路完全同构。）

### 实验 3：让 Mock 替你“失败”

*（继续用实验 1 的 `llm_client.py`：新增这个类，然后把 `LLMClient` 里选客户端那行换成它）*

```python
class FlakyMockLLMClient(MockLLMClient):
    def chat_stream(self, prompt):
        if random.random() < 0.7:
            raise ConnectionError("模拟 429/网络抖动")
        return super().chat_stream(prompt)
```

把 `LLMClient` 里的客户端换成它，跑 `LLMClient().chat("测试")`，你会看到 `[retry] 第1次失败…第2次失败…` 后成功。**现在你对 `@retry` 的感情不是"学过"，是"兜过底"。**

### 实验 4：为什么流式不裹 @retry？

这是本章留给你的思考题，也是工程判断的分水岭：

流式响应是"吐字中"的响应，一旦服务端已经开始吐字，重发一次 = **用户看到两遍重复答案**。所以严肃做法是：**重试只保护"连接建立之前"的阶段**，流式中途断流改用断点续传或降级文案。这个判断，培训机构不会教你——因为他们只教"调通"。

先想，想不通来 Issue 区聊。**这正是"会调 API 的人"和"能扛线上的人"的分界线。**

## 费曼复述卡

1. 向同事解释 OpenAI 兼容协议为什么对团队是好事？从"换模型成本"角度说。
2. 多轮对话里 `assistant` 消息该由谁来 append？为什么这是卫生习惯而不是可选项？
3. 用"滴灌"比喻解释 `stream=True` 的字节流是怎么变成 `for chunk in` 的？SDK 和你的生成器各自做了什么？

三题过不了，回到"不讲术语的版本"重读第 2 节。**这一篇是全书的分水岭：读完它，你已经不是"学过 Python 的人"，是"能写出生产代码骨架的 AI 工程师预备役"。**

## 今日一句话

> 05 篇的 yield、04 篇的 @retry、07 篇的 gather，今天第一次在一个文件里会师——语法攒的件，工程来认领。

---

下一篇：[12 · RAG：给学霸一本开卷教材](./12-rag.md)（返回 [目录](./index.md)）
