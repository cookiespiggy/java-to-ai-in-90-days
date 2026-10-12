# 01 · 第一次亲密接触：删掉 30% 的仪式感

## 先讲给朋友听（如果你只有一分钟）

> Java 像正式西装：每一针每一线都有规矩，穿上笔挺，但你需要先学打领带。Python 像一件优质 T 恤：套上就能出门，舒服、自由、跑得快——代价是它不会提醒你纽扣扣错了。

## 你的 Aha Moment

先看两段"你好世界"。

Java 版（ JDK 8 的老朋友，你都记不起抄过多少遍）：

```java
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("你好，AI");
    }
}
```

数一下，为了打印一行字：类、`public`、`static`、`void`、`main`、`String[] args`、分号，一个都不能少。保存文件必须叫 `HelloWorld.java`，编译成 `.class`，再跑来跑去。

Python 版：

```python
print("你好，AI")
```

完事。

第一次敲下这行代码时，很多 Java 老司机的内心是复杂的：**"就这？我当年熬一周才跑通的程序，它一行？"** 紧接着是第二反应：**"那它凭什么保证工程质量？"**

这两个念头碰撞的瞬间，就是你的第一个 Aha Moment：**Python 把 Java 的"仪式"删掉了，但把"纪律"的责任，从编译器转移给了你。**

- Java：编译期类型检查 = 出厂前的全检流水线，次品别想出车间
- Python：运行时才暴露错误 = 客户现场见了面才发现问题

所以 Java 团队大而不乱，Python 团队快而依赖素养。这不是优劣问题，是**两种关于"谁来兜底"的哲学**。理解这一点，你后面学类型注解、学 Ruff、学 Pytest，才知道它们存在的原因——**它们是在给 T 恤缝上隐形纽扣。**

## 不讲术语的版本：Python 的三条设计信条

记住三句话，Python 的"怪脾气"就解释了一半：

**第一条：显式不如隐晦（不，是反过来——可读性高于一切）**

Python 之禅（在终端输入 `import this` 能看到全文）里有句名言：`Flat is better than nested`（平铺优于嵌套）。翻译成人话：**代码是给人看的，顺便给机器跑跑。**

所以它用缩进代替大括号——不是偷懒，是**强制可读**：一段代码嵌套几层，肉眼扫过去就知道，想写乱了上帝都拦你。

**第二条：任何事情都该有"一个明显的方法"**

Java 里遍历一个 List，老手能写出三种写法（foreach、Iterator、Stream），面试还能互撕三百回合。Python 里？`for x in items:` 一种，爱用不用。

语法选项越少，读别人代码的成本越低。Python 赌的是：**代码被阅读的次数，远多于被编写的次数。**

**第三条：自带电池（Batteries Included）**

Python 装完就带着一整个工具箱：JSON 处理、HTTP 请求、正则、数学计算、数据库驱动。Java 里你要引 Guava、引 Hutool、引 Lombok 再配 Maven——Python 里 `import json` 就完了。

这对你意味着：**AI 生态的"世界语"是 Python，所有新模型、新框架，Python 版本总是第一个发布。** 这就是转行者必须选它的现实理由。

## Java 老司机对照室

| Java 8 的你以为 | Python 的真相 | 注意事项 |
|---|---|---|
| `List<String> list = new ArrayList<>()` | `items = []` 或 `items = list()` | 声明即初始化，没有 `new` |
| `for (String s : list)` | `for s in items:` | 注意 `:` 和缩进 |
| `String.format("%s 岁了", age)` | `f"{age} 岁了"` | f-string，2026 年了别用 `%` 了 |
| `System.out.println(x)` | `print(x)` | 调试阶段够用，正经项目用 `logging` |
| `null` | `None` | `if x is None:`，不是 `== None` |
| `a == b` 比内容 | `a == b` 比内容 | 但 `is` 比身份（相当于 Java 的 `==`） |
| `public/private` 封装 | `_name` 约定私有（一个下划线） | 靠自觉，真私有要 `__name`（名字改写） |
| `HashMap` | `dict`，写作 `{}` | Python 的"万能对象"，比 HashMap 亲密得多 |
| 一个文件一个 public 类 | 一个文件随便写，模块即文件 | 项目结构靠 `__init__.py` 和目录约定 |
| Maven 管依赖 | `uv` 或 `pip` 管依赖 | 本书用 `uv`，快出一个数量级 |

最后一行多说一句。本书的环境规范：**`uv` 创建虚拟环境，`ruff` 检查代码，`pytest` 跑测试。** 为什么不是 `pip`？`uv` 是 Rust 写的包管理器，装依赖比 `pip` 快 10~100 倍，且自动管理虚拟环境——像 Java 的 Maven 一样一次配好，终身受益。

## 动手实验室

### 实验 1：从零搭一个工程化 Python 环境

**全书环境要求：Python 3.10+**（3.9 及以下会在第 02 篇的 `str | None`、第 03 篇的 `zip(strict=True)` 上直接报语法错误）。查版本：

```bash
python3 --version    # 需要 >= 3.10
```

打开终端，依次执行：

```bash
# 建项目目录
mkdir ~/personal/learn-demos/hello-ai && cd ~/personal/learn-demos/hello-ai

# 用 uv 初始化（会自动建好虚拟环境，并按需锁定 Python 版本）
uv init --python 3.11

# 装开发和测试工具
uv add --dev ruff pytest mypy
```

跑完之后，你会得到：`pyproject.toml`（相当于 Java 的 `pom.xml`）、`main.py`（入口）、`.venv`（虚拟环境目录，相当于隔离的 JDK classpath）。

### 实验 2：Java 老代码翻译器

新建 `translator.py`，故意把 Java 思维硬翻成 Python，然后再 Pythonic 化：

```python
# 版本 A：Java 老司机的直译（能跑，但处处别扭）
names = ["Ada", "Linus", "Guido"]
for i in range(len(names)):
    print("第 " + str(i) + " 个名字: " + names[i])

# 版本 B：Pythonic 写法
for i, name in enumerate(names):
    print(f"第 {i} 个名字: {name}")
```

两段输出一模一样。但 B 没有了下标运算、没有字符串拼接、没有临时变量——这就是"删除仪式感"的实感：**不是 Python 少了功能，是它相信你能更优雅地表达意图。**

### 实验 3：感受一个真实的坑

```python
# 坑：可变默认参数（Java 转 Python 十大酷刑之一）
def add_item(item, target=[]):
    target.append(item)
    return target

print(add_item("苹果"))   # 输出 ['苹果']
print(add_item("香蕉"))   # 输出什么？
```

跑一下。如果你猜 `['香蕉']`，那第二行会打脸：它输出 `['苹果', '香蕉']`。

原因：默认参数在**函数定义时**只创建一次，之后每次调用共享同一个列表。Java 不存在这个问题，所以 Java 大脑完全没预警。**这就是"纪律转移"的代价现场**——好在下一篇（类型注解和防御式编程）我们会系统修补这类坑，现在你只需要记住：**Python 的自由是借来的，利息是你会踩中 Javaer 一辈子遇不到的坑。**

### 实验 4：跑通测试闭环

```bash
uv run pytest   # 此时没有测试文件，会提示 no tests ran，正常
uv run ruff check .   # 检查代码风格
```

这两个命令，就是你未来每个项目的起手式。建议现在就写进肌肉记忆：**先写测试，再写实现（TDD）**——Java 圈卷了十年的方法论，Python 圈还在普及中，这是你的降维优势。

## 费曼复述卡

1. 向一个前端同事解释：为什么 Python 删掉类型声明反而让大型项目更难维护？（关键词：兜底责任、类型注解）
2. `import this` 里你最喜欢哪条信条？结合今天写的代码举例说明。
3. 可变默认参数的坑，用大白话讲给同事听，不许说"生命周期"三个字。

三题过不了，回"不讲术语的版本"重读。这一章你不需要"学会 Python"，你只需要一个信念落地：**Java 的严谨不是过时，是抵押给了自由。**

## 今日一句话

> Python 删掉了你的仪式感，但没有删掉你的纪律要求——编译器不管了，以后你自己就是编译器。

---

下一篇：[02 · 类型这回事：Java 的盔甲 vs Python 的轻纱](./02-types-and-typing.md)
