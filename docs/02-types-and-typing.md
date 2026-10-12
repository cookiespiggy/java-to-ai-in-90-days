# 02 · 类型这回事：Java 的盔甲 vs Python 的轻纱

## 先讲给朋友听（如果你只有一分钟）

> Java 像一纪律部队：上岗前查三代，必须持证（`implements` 接口），没证的一律拦在门外。Python 像一家看结果的创业公司：不管你的出身和血统，能干活就要——背后代价是，它经常等你把项目搞砸了，才发现你丫根本不会干活。

## 你的 Aha Moment

假设你的系统里有个"消息处理器"概念：

```java
// Java 世界：先立规矩，后写实现
interface MessageHandler {
    void handle(Message msg);
}

class EmailHandler implements MessageHandler { ... }
```

规矩先行，编译器是你的政委：谁想假装成 `MessageHandler`，先亮出祖宗十八代。

Python 世界，同样的故事一句话：

```python
def process(handler, msg):
    handler.handle(msg)   # 我只调用 handle，你是谁我不管
```

没有 `interface`，没有 `implements`。只要你有 `.handle()` 方法，你就是"处理器"。

这叫**鸭子类型**（Duck Typing）：*如果它走起来像鸭子、叫起来像鸭子，那么它就是鸭子。*

米宝的 Aha 时刻在于：**这不是"Python 设计水平低"，而是一次关于"谁有资格定义契约"的权力转移。** Java 里，接口的所有者说了算；Python 里，**使用者说了算**——我说我需要 `handle(msg)`，你能不能给我， runtime 见分晓。

这解释了为什么你读 LangChain、LangGraph 源码时，几乎看不到接口继承树：它们全是用"我需要你有个 `invoke()` 方法"这种松耦合拼装起来的。**AI 框架的插件生态之所以爆炸，全靠鸭子类型这个底层的自由度。** 看不懂鸭子类型，你就是读十个框架也像在雾里。

## 不讲术语的版本：三层认知，一次说透

**第一层：Java 是静态强类型，Python 是动态强类型。**

记两个维度，别混淆：

- **静态/动态**：类型检查发生在**编译期**还是**运行期**。Java 编译期，Python 运行期。
- **强/弱**：允不允许隐式乱转换。Java 不强求你 `int + "1"`，Python 也不允许 `1 + "1"`——两者都是强类型阵营。真正的弱类型是 JavaScript 那种 `"1" + 1 == "11"` 的混沌。

所以你从 Java 来，不会觉得 Python"类型混乱"，只是"检查迟到"。检查迟到的日常后果：`user.name` 拼成了 `user.nmae`，Java 编译期就红，Python 要等跑到这一行才炸 `AttributeError`。**在中大型项目里，这就是成本。**

**第二层：类型注解——Python 给自己纺的纱。**

Python 3.5 之后有了 PEP 484 类型注解，3.10 之后可以写 `x: str | None`。注意它的本质：

```python
def greet(name: str) -> str:
    return "Hello " + name
```

这**只是注释，不是法律**。Python 解释器根本不看它，你照样可以 `greet(123)`，运行时照样跑（`"Hello " + 123` 会 TypeError，但它不怨注解，怨 `+`）。

注解的真正消费者是三个工具：IDE 补全、文档生成器、以及静态检查器 `mypy`。

**第三层：mypy——把政委请回来。**

```bash
uv add --dev mypy
uv run mypy your_code.py
```

mypy 会像 javac 一样扫注解，把"运行期才会炸的错"提前到你保存文件的瞬间。**Java 转 Python 的人，工程素养的分水岭就在这：不加注解不跑 mypy 的人，写的是脚本；加注解跑 mypy 的人，写的是工程。** 我们这本书、以及你之后读的所有严肃 AI 项目代码，全是后者。

## Java 老司机对照室

| Java 8 的你以为 | Python 的真相 | 心法迁移 |
|---|---|---|
| `interface UserService` | `class UserService(Protocol):` | `Protocol` 就是"结构式接口"：不看血统看长相 |
| `implements` | 什么都不写 | 鸭子类型自动验收 |
| `Optional<User>` | `User | None` | Python 3.10+ 原生管道语法 |
| `@Nullable String` | `str | None` | 注解即文档 |
| `List<String>` | `list[str]` | 小写内置范型（也可 `List[str]`，但新代码推荐小写） |
| `Map<K, V>` | `dict[K, V]` | 写完直接当对象用 |
| `Function<T, R>` | `Callable[[T], R]` | 函数类型的标准表达，langchain 里遍地 |
| 编译期 `javac` 拦截 | `mypy` + 运行时兜底 | 防线从"门卫"变成"门卫+保险"双保险 |
| `instanceof` 判断 | `isinstance(x, T)` | 还活着，但 Pythonic 代码用得很少 |

最后一行值得玩味：`isinstance` 在严肃 Python 代码里出现频率远低于 Java 的 `instanceof`——**因为当你需要频繁 `isinstance` 时，通常说明你的设计在跟鸭子类型较劲。** 这是语法之外的味道，多读源码自然能品出来。

## 动手实验室

### 实验 1：亲眼见证鸭子类型发身份证

```python
class Duck:
    def quack(self): return "嘎嘎"

class Person:
    def quack(self): return "老子学的鸭子叫"

class Frog:
    def other(self): pass   # 不会叫

def make_it_quack(x):      # 注意：没有任何类型限制
    return x.quack()

print(make_it_quack(Duck()))    # 嘎嘎
print(make_it_quack(Person()))  # 老子学的鸭子叫
print(make_it_quack(Frog()))    # AttributeError: 'Frog' object has no attribute 'quack'
```

第三行让它炸。这就是"权力转移"的代价现场：自由度给了调用双方，验收推迟到了 runtime。**把这次报错截图存手机**——你转 Python 后三个月内，最高频的崩溃日志就是 `AttributeError`，见到它要像见到 `NullPointerException` 一样条件反射。

### 实验 2：给轻纱绣上花纹（类型注解 + mypy）

新建 `service.py`：

```python
class User:
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age

def find_user(users: list[User], name: str) -> User | None:
    for u in users:
        if u.name == name:
            return u
    return None
```

先故意写错，再看 mypy 抓不抓：

```python
u = find_user("不是列表", 123)   # 参数类型全错
```

```bash
uv run mypy service.py
```

输出大概长这样（`error: Argument 1 to "find_user" has incompatible type "str"; expected "list[User]"`）。**javac 的感觉回来了。** 从今晚起，你的每个 Python 文件都该有这个待遇：写完跑 `ruff`，进阶跑 `mypy`。

### 实验 3：Protocol——Java 人心中的接口复活了

```python
from typing import Protocol

class Retriever(Protocol):          # 读 AI 源码时的高频结构
    def retrieve(self, query: str) -> list[str]: ...

class MyRetriever:
    def retrieve(self, query: str) -> list[str]:
        return ["文档片段A", "文档片段B"]

def search(r: Retriever, q: str) -> list[str]:
    return r.retrieve(q)

print(search(MyRetriever(), "年假制度"))   # 能跑：MyRetriever 没继承任何东西
```

`MyRetriever` 没有 `implements Retriever`，却依然被接受。这是 LangChain 血统的文件夹：**框架定义协议，用户随便实现，duck typing 负责发身份证。** 记住这个 `Retriever` 的造型——第 15 篇 LangChain 生态里满世界都是这种"协议 + 鸭子实现"的结构。

## 费曼复述卡

1. 向 Java 同事解释：为什么说"Java 的接口是名义类型，Python 的协议是结构类型"？用 `implements` 和 `Protocol` 各举例。
2. 解释类型注解"不是法律"：既然解释器不看注解，那注解解决了什么问题？提示词有三个消费者。
3. 实验 1 的 `AttributeError` 换成 Java 视角，相当于编译期哪个错？为什么在 Python 里它反而成了"设计 smell"？

三题过不了，回到"不讲术语的版本"重读第二层。类型观是后续所有篇章的地基——**RAG 的鸭子、Agent 的协议、流式的类型，全建立在今天这三层认知上。**

## 今日一句话

> Java 上岗查血统，Python 上岗看长相——`Protocol` 是两者握手言和的边界，也是 AI 框架插件生态的宪法。

---

下一篇：[03 · 容器思维：推导式与切片，一种声明式暴力](./03-containers.md)（返回 [目录](./index.md)）
