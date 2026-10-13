# 04 · 函数是一等公民：lambda、闭包与黑魔法装饰器

## 先讲给朋友听（如果你只有一分钟）

> Java 世界里，函数是"类的租客"——想用函数传参？先给它办暂住证（接口）租个公寓（匿名类）。Python 世界里，函数就是人民币：能揣兜里、能递手上、能当礼物送、还能在递出去之前顺手包装一下。你看到的 AI 框架里满屏 `@tool`、`@retry`，就是"送礼前的包装艺术"。

## 你的 Aha Moment

先看一个你迟早会写的场景（第 14 篇 Agent 篇的预告）：

```python
@tool
def search_knowledge_base(query: str) -> str:
    """搜索公司知识库"""
    ...
```

一个 `@tool`，这函数就成了大模型可以调用的工具。你肯定好奇：**这个 `@` 后面什么都没发生的"注解"，凭什么把一个普通函数变成新物种？**

再看一个更基建的场景（第 11 篇流式接口的预告）：

```python
@retry(max_attempts=3, backoff=2.0)
def call_llm_api(prompt: str) -> str:
    ...
```

一个 `@retry`，你的 LLM 调用自动获得"失败退避重试三次"的超能力——而你的函数体连一行 try-catch 都没写。

**两个 `@`，指向同一件事：装饰器（decorator）。**

Java 老司机的 Aha 在这里：你当年靠 Spring AOP + 注解处理器 + Lombok 三件套才能做到的事——环绕通知、字节码增强、自动加日志——**Python 用语言原生的一个 `@` 符号就全部兑现，不需要容器、不需要注解处理器、不需要字节码工程。** `@retry` 不是配置，就是普通函数，二十行就能自己写一个（今天实验 5 就是）。

看懂了装饰器，LangChain/LangGraph 的源码对你就不再是黑魔法：**整个框架的插件体系，就是建立在这条"函数可以被随手包装"的公理上。**

## 不讲术语的版本：三个渐进认知

**第一层：函数是值。**

```python
def greet(name):
    return "你好 " + name

say = greet          # 函数赋值给变量，不加括号是"不调用"
print(say("米宝"))    # 你好 米宝
people = [greet]     # 函数能塞进 list
```

函数在 Java 里是"方法"，必须挂在对象或类上，是二等公民。在 Python 里函数是**一等公民**：能赋值、能入参、能返回、能塞容器。`Function<T,R>` 接口？那是 Java 给二等公民办的暂住证。

**第二层：lambda——一次性打火机。**

```python
sorted(docs, key=lambda d: d["score"])         # 按 score 排序
list(map(lambda x: x * 2, nums))               # 批量翻倍
```

lambda 就是"不用起名字的小函数"，专治"这段逻辑只在此处用一次，给它起名是浪费"的场景。Java 的 `s -> s.length() > 3` 和它几乎一模一样——**但注意粒度哲学：Java lambda 倾向几行的简洁，Python lambda 只该写一行表达式，复杂逻辑老老实实写 `def`。** 这是 Python 社区的洁癖，跟它是"给团队写的代码"的定位有关。

**第三层：装饰器——不拆信封，改信 contents。**

```python
def logging(func):                      # 装饰器工厂：收一个函数
    def wrapper(*args, **kwargs):       # 包装：原函数的替身演员
        print(f"{func.__name__} 开始")
        result = func(*args, **kwargs)  # 替身演员请真身上场
        print(f"{func.__name__} 结束")
        return result
    return wrapper

@logging
def work():
    print("干活")

work()
```

执行流程：`work()` 实际调用的是 `wrapper`，wrapper 在真身前后各打印一行，然后**把真身的光芒原样还给你**（返回值照传，异常照炸）。

翻译成 Spring 黑话：**装饰器 = `@Around` 环绕通知。** 区别是 Spring 的织入要启动容器、要 CGLIB 动态代理、要注解处理器扫描三件套；Python 的装饰器就是**函数套函数**，零框架、零配置、源码级透明。你不就是写 `@Transactional` 的过来人吗？对，那就是 Java 装饰器思想的 Enterprise 版，只是实现重了十倍。

## Java 老司机对照室

| Java 8 的你以为 | Python 的真相 | 心法迁移 |
|---|---|---|
| `Function<T,R> f = x -> x*2` | `f = lambda x: x*2` | 匿名函数同款，语法更裸 |
| 匿名内部类捕获外部变量必须 `final` | 闭包随便读写外部变量 | Python 闭包解放天性（06 篇细说坑） |
| Spring AOP `@Around` | `@装饰器` | 函数级 AOP，零容器 |
| `@Transactional` 声明式事务 | 自己写 `@transactional`？二十行 | Python 社区传统：框架即代码 |
| Lombok `@Data` | `@dataclass`（内置！） | 连这个都内置了 |
| Mockito 静态 mock | 运行时替换函数属性 | 动态语言的测试右倾策略 |
| `Runnable` 实例 | 函数直接当线程任务 | 函数即任务，函数即回调 |

最后一行值得回味：`threading.Thread(target=my_func)`——Java 里必须 new 一个 Runnable 对象，Python 直接把函数扔进去。**函数是人民币，走到哪花到哪。**

## 动手实验室

### 实验 1：函数进容器的爽感

```python
def double(x): return x * 2
def square(x): return x ** 2

ops = {"翻倍": double, "平方": square}    # 函数当字典值
mood = "平方"
print(ops[mood](5))    # 25：用字符串选函数，像策略模式的裸奔版
```

Java 的策略模式要接口+实现类+工厂三件套；Python 一个 dict。**同样的设计模式，代码量差出数量级。**

### 实验 2：lambda 的舒适区与禁区

```python
docs = [{"name": "Ada"}, {"name": "linus"}, {"name": "Guido"}]
print(sorted(docs, key=lambda d: d["name"]))          # 舒适：一行排序

# 禁区：复杂逻辑写 lambda 是社区公敌
weird = lambda x: x + 1 if x > 0 else 0               # ruff 会警告 E731
# 正确做法
def weird_proper(x):
    if x > 0:
        return x + 1
    return 0
```

`ruff` 检查时会教训你 `E731`：lambda 只配干 retrieval 的活。**这条纪律是 Python 给 lambda 划的医保范围——表达式一行，逻辑请下楼左转 def。**

### 实验 3：闭包计数器（Java final 综合征的解药）

```python
def make_counter():
    count = 0
    def inc():
        nonlocal count      # 声明：我要动外面那个 count
        count += 1
        return count
    return inc              # 把"带着环境的函数"送出去

c = make_counter()
print(c(), c(), c())   # 1 2 3
```

Java 里这段要 `final int[] holder = {0}` 套娃，因为匿名内部类捕获的变量必须 final。Python 一个 `nonlocal` 直接声明修改权。**闭包 = 函数 + 它的出生证明（环境变量）**，这是函数式编程的第一课，也是你后面读装饰器源码的敲门砖。

### 实验 3.5：functools.partial——闭包失散多年的亲兄弟

有些参数你每次都要写，烦不烦？`partial` 帮你先焊死：

```python
import functools

def call_llm(prompt, model, temperature=0.2):
    return f"[{model} t={temperature}] {prompt}"

default_llm = functools.partial(call_llm, model="qwen3:4b", temperature=0.2)
print(default_llm("年假几天"))
print(default_llm("能改成 0.7 吗", temperature=0.7))     # 焊死的照样能覆盖

print("内幕:", default_llm.func.__name__, default_llm.args, default_llm.keywords)

embed = functools.partial(call_llm, model="text-embedding-v3")
print(list(map(embed, ["年假", "病假"])))
```

作者机器实测输出：

```text
[qwen3:4b t=0.2] 年假几天
[qwen3:4b t=0.7] 能改成 0.7 吗
内幕: call_llm () {'model': 'qwen3:4b', 'temperature': 0.2}
['[text-embedding-v3 t=0.2] 年假', '[text-embedding-v3 t=0.2] 病假']
```

两个要点：

- **`partial` 不是黑魔法，就是个对象**，三个属性摆在那：`func` 是真身、`args` 是按位置焊的前缀、`keywords` 是焊死的关键字。调用时你还能临时覆盖焊死的值——焊的是默认值，不是铁律。
- **`partial` + `map` 是批量处理的黄金搭档**：最后三行就是 `map(partial(embed, ...), texts)` 的骨架，第 13 篇把 15 条文档灌进 pgvector 时你会写出工业级版本（批量 + 重试）。

Java 老司机对照室：Java 想干这事得写个工厂方法或者 lambda 硬编码参数，`Function<String,String> f = p -> call(p, "qwen", 0.2)`；`partial` 把这个"固定前几个参数"的动作变成了语言级的一等公民。读完这一节，你工具箱里就没有"每次重抄相同参数"的手酸病了。

### 实验 4：带参数的装饰器——LLM 重试的亲爹

```python
import time, functools

def retry(max_attempts=3, backoff=1.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"第{attempt}次挂了: {e}")
                    if attempt == max_attempts:
                        raise
                    time.sleep(backoff ** attempt)   # 指数退避
        return wrapper
    return decorator

# 模拟一个 30% 概率失败的 API
attempt_count = {"n": 0}
@retry(max_attempts=4, backoff=1.5)
def flaky_api():
    attempt_count["n"] += 1
    if attempt_count["n"] < 3:
        raise ConnectionError("网络抖动")
    return "LLM响应成功"

print(flaky_api())   # 大概率打印两次失败后成功
```

逐层拆解这个"函数套函数套函数"的俄罗斯套娃：

- 最外层 `retry(...)`：接收配置，吐出装饰器（所以 `@retry(...)` 带括号）
- 中间层 `decorator(func)`：接收被装饰的真身
- 最内层 `wrapper`：替身演员，执行前后加戏，异常时指数退避

`functools.wraps` 是化妆师：让替身演员保留真身的 `__name__` 和文档字符串，否则调试时你会看到满屏 `wrapper` 怀疑人生。

**第 11 篇调用真 LLM 时，`@retry` 会原样返场**——大模型的 API 不稳定是常态，超时限流是日常，这个装饰器就是从今天起常驻你工具箱的基建。

### 实验 5：封神时刻——手写一个 @tool

```python
def tool(func):
    """AI 框架 @tool 的贫民版原型：给函数挂一张'我可被模型调用'的身份证"""
    func.is_tool = True
    func.tool_name = func.__name__
    return func

@tool
def get_weather(city: str) -> str:
    """查询指定城市的天气"""
    return f"{city} 今天晴，25 度"

@tool
def search_docs(query: str) -> str:
    """搜索公司文档"""
    return "找到 3 条相关制度"

def collect_tools():
    registry = []
    for name, obj in list(globals().items()):
        if callable(obj) and getattr(obj, "is_tool", False):
            registry.append(obj)
    return registry

print([t.__name__ for t in collect_tools()])   # ['get_weather', 'search_docs']
```

看，二十行代码，你就复刻了 Agent 框架的心脏机制：`@tool` 不过是往函数上贴了个属性标签，运行时扫一遍 `is_tool` 就能收集全部工具，喂给大模型的 function calling 接口。**第 14 篇你会看到工业级版本（langchain 的 `@tool` 会进一步抽取参数 schema、写描述），但心脏，就是今天这一跳。**

## 费曼复述卡

1. 向同事解释：装饰器和 Spring AOP `@Around` 解决同一个问题，为什么说 Python 的实现"轻了十倍"？别提字节码，从"谁是框架谁是语言"的角度说。
2. `@retry(...)` 为什么带括号而 `@logging` 不带？用"三层套娃"的拆解说明。
3. 看实验 5 回答：大模型怎么知道你的函数是"可调用的工具"？`is_tool` 标签在其中扮演什么角色？

三题过不了，回到"不讲术语的版本"第三层。装饰器是第一阶段最后的硬骨头，**啃下它，第一阶段收官，你已有资格说'我能读懂 AI 框架源码级构造'。**

## 今日一句话

> Java 的函数要租公寓暂住，Python 的函数直接上桌当人民币——而装饰器，就是在递出人民币之前顺手给它镶的金。

---

下一篇：[05 · 生成器：yield 的秘密，流式输出的前世](./05-generators.md)（返回 [目录](./index.md)）
