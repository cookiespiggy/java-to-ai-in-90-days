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

顺带认个亲：Python 标准库 `contextlib` 里有现成的 `@contextmanager`，用 `yield` 一行写上下文管理器（05 篇的 yield 在此返场）。感兴趣自己搜，本篇点到为止。

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

## 费曼复述卡

1. 用"便利贴 vs 遥控器"的比喻，向同事解释：为什么 `b = a` 后改 b，a 也跟着变？而 `y = 2` 改 y，x 不变？
2. 说出浅拷贝和深拷贝的区别，并举一个 RAG 实战里非用深拷贝不可的场景。
3. `with Timer() as t:` 这段代码，等价于 Java 的什么语法？`__exit__` 的返回值控制什么行为？

三题过不了，回到"不讲术语的版本"第一层。便利贴宇宙是 Python 的"世界观"，方法论比语法重要——**世界观不换，写三年也是 Java 翻译腔。**

## 今日一句话

> Java 的变量握遥控器，Python 的变量贴便利贴——`b = a` 贴的是同一张脸，`is` 查户口，`==` 比长相，深拷贝连抽屉一起搬。

---

下一篇：[07 · 并发真相：GIL 之后，线程/进程/asyncio 重排座次](./07-concurrency.md)（返回 [目录](./index.md)）
