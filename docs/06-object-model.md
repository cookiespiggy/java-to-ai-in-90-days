# 06 · 对象模型：引用语义、可变性与上下文管理器

## 先讲给朋友听（如果你只有一分钟）

> Java 的变量像"遥控器"：每个变量手里握着一个明确的对象，复制遥控器，各按各的电视。Python 的变量像"标签贴"：对象才是本体，变量只是贴在对象上的一张便利贴。一张电视上可以贴两张"客厅电视"的标签——你撕其中一张，发现电视没变，但你以为贴的是两台电视时，事故就发生了。

## 你的 Aha Moment

史上最著名的 Java→Python 头七天地狱，来，亲手按下去：

```python
a = [1, 2, 3]
b = a              # Java 大脑：'给 b 也赋个值'
b.append(4)
print(a)           # [1, 2, 3, 4]
```

第一次跑出这个结果的人，表情管理基本失控：**"我把货卸 b 车里，凭什么 a 的后备箱也满了？！"**

答案就藏在比喻里：`b = a` 不是"把 a 的内容复制给 b"，而是**把 `a` 这张便利贴撕下来，原封不动贴到了同一个列表对象上**。之后 `b.append(4)` 动的是那个列表本体——`a` 也贴在同一个本体上，它"看见"一切。

```
Java 世界              Python 世界
  a ──▶ [1,2,3]           [1,2,3] ◀── a, b   （本体只有一个，标签两张）
  b ──▶ [1,2,3]（新副本）
```

那为什么 `x = 1; y = x; y = 2` 之后 `x` 没变？因为 `y = 2` 不是"改 y 指向的对象"，而是**把 `y` 标签撕下来贴到新对象 `2` 上**——整数是**不可变对象**，谁也别想原地动它。

**Aha 语法细节：`b = a` 让两个标签共享本体；`y = 2` 只是给 y 换贴新对象。** 前者是"引用同一对象"，后者是"重新绑定名字"。分不清这两件事，你会在 RAG 实战里把文档对象改得面目全非还以为有鬼。

## 不讲术语的版本：一张便利贴的宇宙

**第一层：一切皆对象，变量皆标签。**

Python 没有 Java 的"原始类型"（`int`/`double`），`1` 和 `"abc"` 都是对象，都住在堆里。变量（name）只是绑定到对象的便利贴。理解这句话，异常行为少一半。

**第二层：可变与不可变的分界线。**

| 不可变（贴上就别想动） | 可变（随时原地改） |
|---|---|
| `int` `float` `str` `bool` `tuple` `frozenset` | `list` `dict` `set` 自定义对象 |

判断口诀：**不可变对象被修改时，其实是"换了个新对象再贴标签"**。`s += "x"` 看似原地追加，实际是新造了个字符串。这个特性是 hashable（能进 set / 当 dict 键）的入场券——后面的缓存、去重全建立在上面。

**第三层：别名（alias）是万恶之源。**

```python
def add_tag(doc, tags=[]):     # 还记得 01 篇的可变默认参数吗？同一个病友
    tags.append(doc)
    return tags
```

两个 list 贴同一张脸的事故，函数入参、返回值、默认参数三个位置全是高发区。Java 的 shield（每次赋值复制引用、但修改互相可见——其实 Java 引用类型也有 alias 问题）只是没把"可变默认参数"这种坑原样奉上。

**第四层：with 语句——try-with-resources 的亲儿子。**

Java 7 的 try-with-resources 是工程史上的进步，Python 的 `with` 是更早的同类智慧，且更通用：任何对象只要实现 `__enter__`/`__exit__`，就能被 `with` 托管。开关文件、拿数据库连接、锁并发、甚至是**给 LLM 调用计时/计费**——第 22 篇的 `token_meter` 会把 Timer 升级成“计时+计费”二合一。

## Java 老司机对照室

| Java 8 的你以为 | Python 的真相 | 心法迁移 |
|---|---|---|
| 原始类型在栈上 | 全部在堆上，`int` 也是对象 | 值语义只存在于心理层面 |
| `str` 不可变 | `str` 同样不可变 | **难得的共识**，放心用 |
| 对象引用赋值 → alias 同样存在 | 一模一样，但**语法糖更诱人** `b = a` | alias 是跨语言公敌 |
| `clone()` / `new` 拷贝 | `copy.copy()` 浅拷贝 / `copy.deepcopy()` 深拷贝 | 显式到必须 import copy |
| `try (var r = open()) {}` | `with open(...) as f:` | Python 版出生于 2006 年，早 Java 五年 |
| `record Point(int x, int y)` | `@dataclass class Point:` | dataclass 默认可变，record 默认不可变，**反的** |
| `equals()` / `hashCode()` | `__eq__()` / `__hash__()` | 魔术方法命名约定 |
| `Objects.equals(a, b)` | `a == b` 即内容比较 | str/list/dict 的 `==` 全是内容比较 |
| 判断同一对象 `==` | `is`（就是比的身份证） | `a is None` 才是正确打开方式 |

倒数第二行值得划线：**Java 的 `==` 比身份，Python 的 `==` 比内容**——所以 `"abc" == "abc"` 两边都 True；要判"是不是同一个对象"，Python 用 `is`。新人写 `x == None` 是经典事故现场（虽然能跑）。

## 动手实验室

### 实验 1：亲眼制造一次"灵异事件"

```python
a = [1, 2, 3]
b = a
b.append(4)
print("a =", a)          # a = [1, 2, 3, 4]  案发现场
print("a is b:", a is b) # True  实锤：同一个身份证

import copy
a = [[1], [2]]        # 嵌套结构：两个"抽屉"
c = copy.copy(a)      # 浅拷贝：复制最外层列表，内层对象共享
d = copy.deepcopy(a)  # 深拷贝：连内层的对象一起复制
a[0].append(99)       # 改的是内层对象

print("a =", a)   # [[1, 99], [2]]
print("c =", c)   # [[1, 99], [2]]   浅拷贝被波及：内层是同一个对象
print("d =", d)   # [[1], [2]]       深拷贝与世隔绝
```

**浅拷贝 vs 深拷贝一句话：浅拷贝复制桌面，深拷贝复制桌面+抽屉+抽屉里的盒子。** 注意别被"浅=差"的直觉骗了——浅拷贝复制**最外层**，所以外层增删不受影响（上面例子里给 `a` 整体 append 元素，`c` 感知不到）；真正的坑在**内层共享**。RAG 实战里 `document.chunks` 这种嵌套结构，只动外层用浅拷，改 chunk 内容必须深拷。

### 实验 2：可变默认参数的连续作案

```python
def collect(items=[]):
    items.append("污染")
    return items

print(collect())   # ['污染']
print(collect())   # ['污染', '污染']
print(collect())   # ['污染', '污染', '污染']
```

解药只有一个，社区规范写法：

```python
def collect(items=None):
    if items is None:
        items = []
    items.append("干净")
    return items

print(collect(), collect())   # ['干净'] ['干净']
```

**把 `def collect(items=[])` 的手感从肌肉记忆里抠掉，换成 `None` 哨兵。** 这是 01 篇留的债，今天连本带利还清。

### 实验 3：with——资源管理的体面写法

```python
import time

class Timer:
    """一个给 LLM 调用计时的上下文管理器"""
    def __enter__(self):
        self.start = time.perf_counter()
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.perf_counter() - self.start
        return False        # 异常照常抛出，不吞

with Timer() as t:
    time.sleep(0.1)         # 假装这是 LLM API 调用
print(f"本次调用耗时 {t.elapsed:.2f}s")   # 约 0.10s
```

`__enter__` 进门、`__exit__` 出门（异常也走这个门），`return False` 意味着"有事说事，异常别拦"。**第 22 篇的 `token_meter` 就是把 Timer 升级成“计时 + 计费”二合一的完全体**——同一个 `with` 结构，加几行就是工程化的起点。

顺带认个亲：Python 标准库 `contextlib` 里有现成的 `@contextmanager`，**用 `yield` 一行写出上下文管理器**——05 篇那个"暂停键"，在这里从语法糖变成了工程基建：

```python
import time
from contextlib import contextmanager

@contextmanager
def timer(label):
    """用 yield 写上下文管理器 = 05 篇生成器的社会实践"""
    start = time.perf_counter()
    try:
        yield                      # 暂停键：执行权在这里交回 with 块
    finally:
        print(f"{label} 耗时 {time.perf_counter() - start:.3f}s")

with timer("假装调 LLM"):
    time.sleep(0.05)

# yield 出来的东西，就是 as 后面的变量：第 22 篇 token_meter 的骨架
@contextmanager
def token_meter():
    budget = {"tokens": 0}
    class Meter:
        def add(self, n):
            budget["tokens"] += n
    yield Meter()                 # with ... as m 的 m，就是这个对象
    print(f"本次消耗 {budget['tokens']} tokens")

with token_meter() as m:
    m.add(120)
    m.add(80)
```

作者机器实测输出：

```text
假装调 LLM 耗时 0.055s
本次消耗 200 tokens
```

两句话看懂它：

- **`yield` 之前是进门、之后是出门**，异常也走 `finally` 这条路——所以 `@contextmanager` 版本天然比手写 `__exit__` 少一个"别忘了 `return False`"的坑。
- **`yield` 出来的对象就是 `as m`**。上面这个 `token_meter` 已经是第 22 篇计费组件的完整心脏了：`with` 进来开账本，`m.add()` 记流量，出门自动结账。你要做的只是把 `time.sleep` 换成真 LLM 调用。

至此 05 和 06 篇正式合流：**`yield` 既是懒数据的传送带（05），也是资源管理的开关（06）。** 同一个语法，两副面孔。

### 实验 4：dataclass——Java record 的孪生兄弟（但性格相反）

```python
from dataclasses import dataclass, field

@dataclass
class Document:
    content: str
    source: str = "unknown"
    score: float = 0.0
    tags: list = field(default_factory=list)   # 可变默认值的正确姿势

d1 = Document(content="年假入职满一年享有")
d2 = Document(content="年假入职满一年享有")
print(d1)                      # Document(content='...', source='unknown', score=0.0, tags=[])
print(d1 == d2)                # True：dataclass 自动生成 __eq__，比内容
print(d1.source)               # unknown
d1.tags.append("HR")           # 独立 mutable，不串味
```

Java record 是不可变的（想改只能 new）；dataclass 默认可变，更像个轻量 POJO。**`field(default_factory=list)` 是 `None` 哨兵的正式编制版。** 第 21 篇评测集会用 `@dataclass` 批量定义评测用例（输入 + 期望 + 类别），第 13 篇的文档块、检索结果也常用这个造型承载，提前认脸。

### 实验 5：__slots__——几十万文档块的内存瘦身术

还记得实验 4 那个 `Document` 吗？第 13 篇切完公司文档，你手里会有**几万个甚至几十万个**这种对象。普通实例每个都拖着一个小字典（`__dict__`）装属性，内存哗哗地流；`__slots__` 把字典换成定长槽位，内存直接瘦一圈：

```python
import sys

class Chunk:
    def __init__(self, content, source, score):
        self.content = content; self.source = source; self.score = score

class ChunkSlots:
    __slots__ = ("content", "source", "score")
    def __init__(self, content, source, score):
        self.content = content; self.source = source; self.score = score

n = 100_000
a = [Chunk("年假满一年5天", "员工手册-年假", 0.71) for _ in range(n)]
b = [ChunkSlots("年假满一年5天", "员工手册-年假", 0.71) for _ in range(n)]
sa = sum(sys.getsizeof(o) + sys.getsizeof(o.__dict__) for o in a[:1000]) / 1000
sb = sum(sys.getsizeof(o) for o in b[:1000]) / 1000
print(f"对象数 n = {n:,}")
print(f"普通实例单对象内存 {sa:.0f} B，slots {sb:.0f} B，省 {100 - 100 * sb / sa:.0f}%")
print(f"总内存对比（MB）：{sa * n / 1e6:.1f} vs {sb * n / 1e6:.1f}")

try:
    b[0].new_attr = 1
except AttributeError as e:
    print("slots 拦住动态加属性:", e)

# dataclass 的正式编制版
from dataclasses import dataclass

@dataclass(slots=True)
class DocSlots:
    content: str
    source: str = "unknown"
    score: float = 0.0

d = DocSlots(content="年假满一年5天")
print(d, d.content)
try:
    d.nope = 1
except AttributeError as e:
    print("dataclass(slots=True) 同样拦截:", e)
```

作者机器实测输出（CPython 3.13.13，macOS arm64）：

```text
对象数 n = 100,000
普通实例单对象内存 144 B，slots 56 B，省 61%
总内存对比（MB）：14.4 vs 5.6
slots 拦住动态加属性: 'ChunkSlots' object has no attribute 'new_attr' and no __dict__ for setting new attributes
DocSlots(content='年假满一年5天', source='unknown', score=0.0) 年假满一年5天
dataclass(slots=True) 同样拦截: 'DocSlots' object has no attribute 'nope' and no __dict__ for setting new attributes
```

十万个对象省出将近 9 MB——听起来不多，但这是**唯一一处"改一行属性声明就见效"的优化**，而且它顺便堵住了一个真实的生产事故源：动态往对象上挂临时属性（`doc.tmp = xxx`），代码一散就没人记得它从哪来的。**`@dataclass(slots=True)` 是正式编制版**，Python 3.10+ 可用，dataclass 该有的照样有。

代价也要说清楚：**slots 类不能随便加新属性，继承链上加 slots 容易踩坑**。所以只对"定型了的海量小对象"用，别对三天两头改结构的配置类用。

### 实验 6：__call__ 与 __getattr__——对象也能当函数，属性也能玩赖的

这两个是 Python 元编程的门把手，你看框架源码时天天见，今天一次认完。

**`__call__`：让对象可被调用。** 第 13 篇你要写一个检索器，它天然该长这样：

```python
class Retriever:
    """可调用对象 = 第 13 篇 retrieve() 的身份证"""

    def __init__(self, threshold=0.6):
        self.threshold = threshold
        self.calls = 0

    def __call__(self, query):
        self.calls += 1
        print(f"  检索「{query}」阈值 {self.threshold}，第 {self.calls} 次调用")
        return [("员工手册-年假", "年假入职满一年享有5天", 0.71)]

retriever = Retriever()
print("callable(retriever):", callable(retriever))

hits = retriever("年假几天")            # 对象当函数用，第 13 篇您就调它
print("命中:", hits)
```

实测输出：

```text
callable(retriever): True
  检索「年假几天」阈值 0.6，第 1 次调用
命中: [('员工手册-年假', '年假入职满一年享有5天', 0.71)]
```

为什么框架爱用可调用对象而不是裸函数？**因为函数只有逻辑，对象还能带配置和状态**——`threshold` 是配置，`calls` 是状态（顺手把调用次数记下来，第 21 篇做评测统计时你会感谢它）。Java 里这叫"带状态的功能接口实现"，Python 里一个 `__call__` 就完事。

**`__getattr__`：按需加载的赖皮管家。** 只在属性找不到时被触发，很多重型库用它做懒加载：

```python
class LazyLib:
    """__getattr__：真身用到才加载（属性名拼错也能抓住）"""

    ALLOWED = {"array", "zeros", "ones"}

    def __init__(self, name):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_loaded", None)

    def _load(self):
        print(f"  [lazy] 第一次访问才真加载 {self._name} ...")
        return {"np": "numpy-2.x", "pd": "pandas-2.x"}[self._name]

    def __getattr__(self, item):
        if item.startswith("_") or item not in LazyLib.ALLOWED:
            raise AttributeError(item)
        return f"{self._load()}.{item}"

np = LazyLib("np")
print("还没碰 np，什么都没发生")
print("现在访问 np.array ->", np.array)
try:
    np.nope
except AttributeError as e:
    print("拼错照样报 AttributeError:", e)
```

实测输出：

```text
还没碰 np，什么都没发生
  [lazy] 第一次访问才真加载 np ...
现在访问 np.array -> numpy-2.x.array
拼错照样报 AttributeError: nope
```

`np` 在构造时不干正事，第一次 `.array` 才加载真身——**"用到了才付代价"**，这正是第 11 篇你敢在脚本里 import 一堆 SDK 的底气。注意 `__init__` 里用 `object.__setattr__` 而不是 `self.xxx = ...`：后者会再触发一次 `__getattr__` 绕圈子，这类细节是翻车重灾区。

顺带一个零成本的工程习惯：给类写 `__repr__`。上面那个 `Timer` 对象 `print(t)` 只会得到 `<__main__.Timer object at 0x10f3a2b40>`，加上 `__repr__` 返回 `<Timer 运行了 0.055s>`，日志里一眼认出它是谁。第 22 篇排查问题时你会回来谢这个习惯。

## 费曼复述卡

1. 用"便利贴 vs 遥控器"的比喻，向同事解释：为什么 `b = a` 后改 b，a 也跟着变？而 `y = 2` 改 y，x 不变？
2. 说出浅拷贝和深拷贝的区别，并举一个 RAG 实战里非用深拷贝不可的场景。
3. `with Timer() as t:` 这段代码，等价于 Java 的什么语法？`__exit__` 的返回值控制什么行为？
4. 用"暂停键"解释：`@contextmanager` 里 `yield` 之前和之后的代码，分别在什么时刻执行？

三题过不了，回到"不讲术语的版本"第一层。便利贴宇宙是 Python 的"世界观"，方法论比语法重要——**世界观不换，写三年也是 Java 翻译腔。**

## 今日一句话

> Java 的变量握遥控器，Python 的变量贴便利贴——`b = a` 贴的是同一张脸，`is` 查户口，`==` 比长相，深拷贝连抽屉一起搬。

---

下一篇：[07 · 并发真相：GIL 之后，线程/进程/asyncio 重排座次](./07-concurrency.md)（返回 [目录](./index.md)）
