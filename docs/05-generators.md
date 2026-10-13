# 05 · 生成器：yield 的秘密，流式输出的前世

## 先讲给朋友听（如果你只有一分钟）

> 普通函数像一次性外卖：下单、出餐、关门，要么全给你要么没有。生成器像旋转寿司：你拿一盘，它转一盘，随时暂停、永远新鲜、还不会把桌子堆满。你 ChatGPT 里一字一字往外蹦的答案，底层就是这台旋转寿司。

## 你的 Aha Moment

这一篇是全书埋得最深的一条暗线。先给你看一段代码：

```python
for chunk in llm.stream("用三句话解释什么是多线程"):
    print(chunk, end="", flush=True)
```

这段代码出现在本书第 11 篇（第一次调用大模型 API）。`llm.stream` 会一个 token 一个 token 地把模型的回答往外抛——就像你亲眼看着 ChatGPT 一个字一个字打字那样。

现在我问你：**凭什么它能这样？** 模型不是应该"生成完整个回答再返回"吗？

答案是 `yield`。

如果你还记得第 01 篇说的"Python 删掉了仪式感"，那 `yield` 就是**Java 压根没给你、而 Python 原生的超能力**：

> `return` 是交货+关门。`yield` 是交货，然后**站在门口等你喝完这口水再递下一件**。

函数第一次调用时不执行，每次你要一个值（`next()`），它才从上次暂停的地方继续跑，直到遇见下一个 `yield`，把货递给你，再次冻结原地。整个函数的状态——局部变量、执行到第几行——像被施了定身法，完整保留。

等你见证了第 11 篇那段流式代码，再回头看今天这篇，你会回来谢我。

## 不讲术语的版本：会走路的暂停播放器

把普通函数想象成 DVD 光盘：放完就弹匣，进度条清零。每次点播放，都得从头来。

生成器是**带记忆的暂停播放器**：

- 第一次按播放，它开始播
- 碰到 `yield`，"咔哒"一声暂停，把一个画面递给你
- 你说"继续"，它从暂停处接着播
- 影片结束（函数体跑完），播放器"咔哒"关机——Java 程序员管这个叫抛 `StopIteration` 异常

而 `for` 循环的本体，其实就是一台复读机：**不停地按播放键，直到播放器关机。**

更妙的一面叫**惰性求值**。普通做法是把 100 万个数字全算好存进 `list`，像先把整个仓库装满。生成器是"你要一个我现算一个"——算到第 50 个时，前 49 个的内存早就让出去了。

这就是为什么处理大文件、无限序列、流式数据这三件事，Python 都用一个模式搞定：`for x in generator:`。

**AI 场景翻译**：模型吐 token 的速度大概是每秒几十个，一个长回答要几秒甚至几十秒。如果等服务端全生成完再传给你，你盯着空白屏幕干等八秒——产品经理会砍人。用了旋转寿司模式，用户立刻看到第一个字流出来，**同样的答案，等待感少一半**。用户体验的魔法，工程上只是一个 `yield`。

## Java 老司机对照室

| Java 8 的你以为 | Python 生成器的真相 | 差距在哪 |
|---|---|---|
| `return List<Order>` | `yield order` | Java 一次交付全集，Python 逐件交付 |
| 实现 `Iterator` 接口 + 维护 index 状态 | 写个含 `yield` 的函数完事 | Java 需要手写状态机，Python 编译器帮你冻结现场 |
| `stream().map()` 惰性管道 | `(x*2 for x in nums)` 生成器表达式 | 都很惰性，但生成器表达式没有 Stream 的启动开销 |
| 遍历到一半 break，Java 里只是停止消费 | 生成器没人取了，自动回收（`close()`） | Python 会在迭代结束时清理资源，`with` 语法同理 |
| 没有原生"暂停/恢复"能力 | `async yield`：异步生成器 | 这是 asyncio 流式接口的骨架，第 11 篇直接面对 |

一句话总结这张表：**Java 靠接口规范和样板代码模拟"逐个生产"，Python 用语言级开关原生了这件事。** 代价么，和全书主旨一样：自由 = 你的责任——生成器只能用一次，用完成枯骨，想再来一遍必须重新调用函数。

## 动手实验室

### 实验 1：侧躺的 return 对比实验

```python
# 普通函数：一口气交货
def normal_version():
    return [1, 2, 3]

# 生成器函数：含 yield，调用它什么都不执行
def gen_version():
    print("开始")   # 注意：调用时这句话不会打印！
    yield 1
    yield 2
    yield 3

print(normal_version())     # [1, 2, 3]
print(gen_version())        # <generator object gen_version at 0x...>

g = gen_version()
print(next(g))   # 开始 -> 1（这才真正开始执行，跑到第一个 yield）
print(next(g))   # 2
print(next(g))   # 3
print(next(g))   # StopIteration：播放器关机
```

跑完盯住这两行输出，把 Aha Moment 钉进脑子：**`print(gen_version())` 打印的不是数字，是一个"还没开始播放的播放器"的身影。**

### 实验 2：无限序列——Java 老司机的噩梦

```python
def fibonacci():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

import itertools
for n in itertools.islice(fibonacci(), 10):  # 只要前 10 个，防止失控
    print(n)
```

`while True` + 有限消费，Java 里你这么写等于自杀，Python 里这是日常。**"无限供应、按需索取"就是生成器的世界观。**

### 实验 3：恒定内存读 10GB 日志

模拟你排查线上问题的日常，**这份日志 10 个 G**（真要造 10G 太慢，用 1000 行代表它，原理不变）：

```python
# 先造一份模拟日志
with open("huge.log", "w", encoding="utf-8") as f:
    for i in range(1000):
        f.write(f"2026-10-12 10:{i%60:02d} INFO 正常心跳 {i}\n")
        if i % 100 == 0:
            f.write(f"2026-10-12 10:{i%60:02d} ERROR 接口超时 user={i}\n")

def read_lines(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            yield line

error_count = 0
for line in read_lines("huge.log"):     # 换成 10GB 文件也是同一段代码
    if "ERROR" in line:
        error_count += 1
print("ERROR 行数:", error_count)       # 10
```

想亲眼验证"恒定内存"，把文件放大到一亿行再跑：内存占用**纹丝不动**——因为处理完一行就扔一行。这个模式，就是第 13 篇 RAG 实战里切分大文档时你会反复用到的东西。

### 实验 4：预演第 11 篇——假造一个 LLM 流式输出

```python
import time

def fake_llm_stream(question: str):
    """模拟大模型逐字蹦答案。第 11 篇你会写出真身。"""
    answer = f"关于「{question}」，我的回答是：多线程就像..."
    for word in answer.split():           # 按词切分，模拟 token
        yield word + " "
        time.sleep(0.1)                   # 模型"打字"的节奏

for chunk in fake_llm_stream("什么是多线程"):
    print(chunk, end="", flush=True)
```

第二步的 `time.sleep(0.1)` 请务必保留——**看着文字像 ChatGPT 一样往外蹦的瞬间，"旋转寿司"这个比喻才真正长进你的直觉里。** 第 11 篇把 `fake` 换成真模型，代码骨架一模一样。

### 实验 5：接收你的第一次 StopIteration

在实验 1 的基础上，亲手触发一次（教材性质的错误，请故意犯）：

```python
g = gen_version()
next(g); next(g); next(g)
next(g)   # 就是要让它炸：StopIteration
```

看到的报错文本记下来。下一阶段调 LLM API，流式响应用完后再去 `next()`，就是这个错——到那天你会感谢今天故意犯错的自己。

### 实验 6：迭代器协议——generator 只是速成班

前五个实验你一直在用 `for`，但 `for` 到底凭什么能遍历一个对象？答案只有两个方法，这就是 **迭代器协议**：

```python
class Countdown:
    """手写迭代器：协议只有两个方法，dataset 的牙齿"""

    def __init__(self, n):
        self.n = n

    def __iter__(self):
        return self

    def __next__(self):
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n + 1


for x in Countdown(3):
    print(x, end=" ")          # 3 2 1
print()

it = iter(Countdown(2))
print(next(it), next(it))      # 2 1

# generator 是迭代器的语法糖：for 只认协议，不关心你是谁
g = (x * x for x in range(4))
print("是迭代器吗:", iter(g) is g, "| list(g) =", list(g))

def ticker(n):
    for i in range(n):
        yield i

print("generator 类型:", type(ticker(2)), "| 有 __iter__:", hasattr(ticker(2), "__iter__"))
```

作者机器实测输出：

```text
3 2 1
2 1
是迭代器吗: True | list(g) = [0, 1, 4, 9]
generator 类型: <class 'generator'> | 有 __iter__: True
```

`for x in obj` 干的事，翻译成 Java 老司机的语言：**先问一遍 `obj.__iter__()` 拿一个迭代器，然后反复 `next()`，直到 `StopIteration` 举手投降**。Java 的 `Iterable`/`Iterator` 是同一条协议，区别是 Python 把它做成了语法糖：`yield` 函数自动帮你实现这两个方法。

所以实验 5 那个 `StopIteration`，不是报错，是**协议在按流程谢幕**。

### 实验 7：预习第 11 篇——async generator，流式输出的完全体

第 11 篇的 `chat_stream` 是异步的（等网络时不能让整个进程趴下），所以它用的是这篇的升级版：`async def` + `yield` = **异步生成器**，配 `async for` 使用。

```python
import asyncio, inspect

async def async_stream():
    """第 11 篇 chat_stream 的心脏：async generator"""
    for word in ["大", "模", "型"]:
        await asyncio.sleep(0.01)      # 假装等网络
        yield word

async def main():
    print("是异步生成器:", inspect.isasyncgen(async_stream()))
    async for chunk in async_stream():
        print(chunk, end="")
    print()

asyncio.run(main())
```

作者机器实测输出：

```text
是异步生成器: True
大模型
```

对照着记：**同步生成器喂同步循环，异步生成器喂 `async for`**。到第 11 篇写真 LLM 流式调用时，把 `async_stream` 的 `for word in [...]` 换成 `for chunk in response:`，其他一个字符都不用改。

## 费曼复述卡

1. 向同事解释：为什么 `gen_version()` 这行代码什么都没打印？（不许说"因为它是生成器"）
2. 用"旋转寿司"比喻，向产品经理解释流式输出为什么能提升用户体验，最后要落到"省内存"这个技术收益上。
3. 看着实验 3 的代码自问：如果日志文件里有 100 万行，Python 的内存占用取决于文件大小还是行数？用你自己的话说出答案。

三题过不了？回到"不讲术语的版本"重读。生成器是第一阶段唯一"和 Java 没有对照物"的硬骨头，值得多花半小时——**它是从 Python 语法通向 AI 工程的第一道暗门。**

## 今日一句话

> `return` 交货关门，`yield` 交货等人——大模型那一个个往外蹦的字，就是 `yield` 在现实世界的投影。

---

下一篇：[06 · 对象模型：引用语义、可变性与上下文管理器](./06-object-model.md)（返回 [目录](./index.md)）
