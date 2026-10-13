# 07 · 并发真相：GIL 之后，线程/进程/asyncio 重排座次

## 先讲给朋友听（如果你只有一分钟）

> Java 的多线程像八个厨师八个灶台，真并行；Python 的多线程像八个厨师轮用一个灶台，还得举手表决谁挨揍——这就是 GIL。但 Python 有个后门：**如果厨师大部分时间在等食材（IO 等待），一个灶台也能炒出花来**。而 AI 应用，恰好是"等"占 95% 的世界：等模型吐 token、等网络、等数据库。所以这把 Java 老段位剑，在 AI 赛道反而轻巧了。

## 你的 Aha Moment

先给你看一段舒服的代码，第 14 篇 Agent 篇会返场：

```text
import asyncio

async def ask_llm(question: str) -> str:
    ...  # 调用大模型

# 同时问三个问题，总耗时 ≈ 最慢的那一个
answers = await asyncio.gather(
    ask_llm("解释RAG"),
    ask_llm("解释Agent"),
    ask_llm("解释微调"),
)
```

三路并发访问大模型，总耗时约等于**最慢那一路**。换成 Java，你要掏出 `CompletableFuture.supplyAsync()`、自定义线程池、调 `allOf()`，再小心线程池参数与隔离策略——一个"业务小工具"活生生写成"并发架构题"。

**Aha 就在这：Python 没打算跟 JVM 拼"重量级并行"，它把宝押在"轻量级并发"上。** GIL 确实让多线程不能利用多核算 CPU 密集任务——但 AI 工程师的日常，80% 是在等 IO：等网络响应、等模型流式吐 token、等向量库返回。**"等"这件事，Python 是世界冠军。**

再看一次你的行军路线：从 JVM 的多线程、线程池、锁一路卷过来的老手，来到 Python 会先怀疑人生（"我这么多年白学了？"），然后恍然大悟（"我要学的那部分，这里更简单"）。今天就把这份座次表排清楚。

## 不讲术语的版本：一张地图，三条路

**第一站：GIL 是什么？**

GIL（Global Interpreter Lock，全局解释器锁）是 CPython 解释器身上的一把大锁：**同一进程里，同一时刻只允许一条线程执行字节码**。

类比：你有八个厨师（线程），但厨房只有一把菜刀（GIL）。八个厨师得排队用刀——CPU 密集型任务就像"每人必须连切两小时萝卜"，八个厨师和一个没区别，轮换还增加开销。

但注意：**GIL 是 CPython 的实现细节，不是 Python 语言的。**（PyPy、Jython 无 GIL，3.13+ 的 JIT 也在博弈，但生态主流仍是 CPython，本书默认它。）

**第二站：任务分两类。**

- **CPU 密集型**：算矩阵、跑模型推理、压测循环。特征：厨师在猛挥刀，换谁也不顶用 → **多进程**（多开几个厨房，各发一把刀）。
- **IO 密集型**：调 API、查数据库、读写文件、流式输出。特征：厨师 95% 时间在等食材，刀闲着一会儿 → **多线程/asyncio**，等的时候别人上。

**第三站：asyncio 是 IO 并发的终极答案。**

多线程的线程上下文切换有成本（还带锁竞争的地狱），asyncio 换了个思路：**单线程 + 协作式调度**。所有任务都是协程（`async def`），遇到 IO 等待就主动喊"我先撤，好了叫我"（`await`），事件循环（event loop）在之间转方向盘。**没有锁竞争、没有上下文切换、单线程内几千个并发任务轻松跑**——Java 的 NIO/Reactor 模型，你早就熟，只是这里换了名字、省了心智。

内存代价：每个线程默认 8MB 栈，一个 asyncio 任务只有 KB 级。**用 Java 的话说：asyncio 是把用户态线程的轻量做到了语言级。**

## Java 老司机对照室

| Java 8 的你以为 | Python 的真相 | 心法迁移 |
|---|---|---|
| `new Thread(t).start()` | `threading.Thread(target=fn).start()` | 还在，但慎用裸线程 |
| `ExecutorService fixedPool(8)` | `ThreadPoolExecutor(max_workers=8)` | 同款池化，参数语义一模一样 |
| `synchronized(obj)` | `threading.Lock()` + `with lock:` | Lock 更裸，with 保命（06 篇返场） |
| `volatile` 关键字 | 无对应，靠 Queue / 事件循环序 | asyncio 单线程本无数据竞争 |
| `CompletableFuture.supplyAsync` | `loop.run_in_executor` 或 `asyncio.to_thread` | 把同步函数丢进线程池的桥 |
| `CompletableFuture.allOf(...)` | `await asyncio.gather(...)` | 等的就是这一句 |
| NIO + Reactor 响应式编程 | asyncio + 事件循环 | **你已经会了**，换皮版 |
| `ForkJoinPool` 并行计算 | `multiprocessing.Pool` | 绕过 GIL 的官方指定姿势 |
| 线程栈 8MB 起步 | asyncio 任务 KB 级 | 代码没怎么变，内存压力小一半 |

最后一行是隐藏红利：**同样几千并发，JVM 方案要调栈大小、堆大小、GC 策略，Python asyncio 方案可能就一两行。** 你从 JVM 带来的"并发性能调优焦虑"，在 IO 密集型场景可以直接减半。

## 动手实验室

### 实验 1：亲眼目睹 GIL 的暴政（CPU 密集）

```python
import time, threading

def burn_cpu(name):
    """纯 CPU：1000 万次自增"""
    n = 0
    for _ in range(10_000_000):
        n += 1
    return n

t0 = time.perf_counter()
threads = [threading.Thread(target=burn_cpu, args=(i,)) for i in range(4)]
for t in threads: t.start()
for t in threads: t.join()
print(f"4 线程跑 CPU 密集：{time.perf_counter() - t0:.2f}s")

t0 = time.perf_counter()
for i in range(4):
    burn_cpu(i)
print(f"顺序跑同一任务：{time.perf_counter() - t0:.2f}s")
```

跑完看两个数字：**多线程基本没快，甚至更慢**（线程切换开销）。这就是 GIL 的实锤——换成 Java，八核机器上这里应该近乎四倍加速。**结论写进肌肉记忆：Python 多线程 ≠ Java 多线程，CPU 密集请加 `multiprocessing`。**

### 实验 2：多线程的甜点区（IO 密集）

> 雷区预警：Java 老手转来 Python，最常犯的错就是引入一个不存在的包名（比如 `requests-not-needed` 这种手滑）。养成习惯——**import 只 import 你真会用的**，没装的包 `import` 那行就是当场 Syntax/ImportError。

```python
import time, threading

def io_wait_task(name, seconds):
    time.sleep(seconds)          # 模拟等网络：LLM API 的等待节奏
    print(f"{name} 完成")

t0 = time.perf_counter()
threads = [threading.Thread(target=io_wait_task, args=(f"任务{i}", 1)) for i in range(4)]
for t in threads: t.start()
for t in threads: t.join()
print(f"4 个 1 秒 IO 任务并发：{time.perf_counter() - t0:.2f}s")   # 约 1.05s，而不是 4s
```

**等待时 GIL 是释放的**——所以四个"等 1 秒"的任务总耗时约 1 秒。IO 密集 + GIL = 终于对你点头了。

### 实验 3：asyncio 的真身——并发调 LLM 预演

```python
import asyncio, time

async def fake_llm(question: str, delay: float) -> str:
    await asyncio.sleep(delay)        # 模拟 LLM 吐字的时间
    return f"{question} → 回答完毕"

async def main():
    t0 = time.perf_counter()
    answers = await asyncio.gather(
        fake_llm("解释RAG", 1.5),
        fake_llm("解释Agent", 1.0),
        fake_llm("解释微调", 2.0),
    )
    for a in answers:
        print(a)
    print(f"三路并发总耗时：{time.perf_counter() - t0:.2f}s")   # 约 2.0s = 最慢那路

asyncio.run(main())
```

数一下：三路加起来要等 4.5 秒，`asyncio.gather` 一压，总耗时 ≈ 最慢那一路 2 秒。**这段代码就是第 11 篇流式接口的并发骨架**——真调 LLM 时把 `fake_llm` 换成异步 HTTP 客户端即可，其余原样。Java 要做到同样的事，先写十几个 boilerplate；Python 一个 `await`。

注意 `main()` 不是被直接调，而是被 `asyncio.run(main())` 丟进事件循环驱动——这个临门一脚的仪式感，是 asyncio 留给你唯一的"西装扣"。

### 实验 4：静态函数进异步世界（桥接老代码）

```python
import asyncio, time

def legacy_blocking_api():          # 你的老同步代码：Java 时代的遗产
    time.sleep(1)
    return "老接口响应"

async def main():
    result = await asyncio.to_thread(legacy_blocking_api)   # 丢线程池，不卡事件循环
    print(result)

asyncio.run(main())
```

**这条桥至关重要**：你转 Python 后不可能一切都异步，老同步库（一堆数据库驱动、工具库）怎么办？`asyncio.to_thread` 一键丢进线程池执行，async 世界继续转。Java 的 `CompletableFuture.supplyAsync` 桥同步世界？同款思路，这里一行。

## 费曼复述卡

1. 向 Java 同事汇报：为什么 Python 多线程救不了 CPU 密集型任务？用"一把菜刀八个厨师"的比喻。
2. 实验 3 总耗时为什么不是 4.5s 而是 2s？`asyncio.gather` 在 Java 里最像哪个 API？
3. `async def` 的函数和普通 `def` 差在哪？`await asyncio.sleep(1)` 为啥不卡其他任务？

三题过不了，回到"不讲术语的版本"第三站。并发观是你 Java 老本行的翻新篇——**旧经验不扔掉，换的是调控方式。**

## 今日一句话

> Python 的多线程是假并行，asyncio 是真并发——AI 应用 95% 在等 IO，而"等"这件事，Python 是世界冠军。

---

下一篇：[08 · 大模型是个超级自动补全，这事关尊严](./08-llm-basics.md)（返回 [目录](./index.md)）
