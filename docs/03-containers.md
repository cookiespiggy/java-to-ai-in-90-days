# 03 · 容器思维：推导式与切片，一种声明式暴力

## 先讲给朋友听（如果你只有一分钟）

> Java  Stream 像点菜：跟服务员报一串流程——"来一份红烧肉，去皮，切小块，装盘，加热"。Python 推导式像直接报菜名："我要小份去皮红烧肉"。同样的菜，Python 把中间白话全省了。翻译不是没代价的：菜名太长时，顾客和厨子都会想砍人。

## 你的 Aha Moment

需求来了：从一个字符串列表里找出长度大于 3 的名字，转成大写，组成新列表。这是你的日常工单。

Java 8 老司机的肌肉记忆：

```java
List<String> result = names.stream()
    .filter(s -> s.length() > 3)
    .map(String::toUpperCase)
    .collect(Collectors.toList());
```

三行，链式调用，行云流水。面试能写出这个，说明你 Java 及格了。

Python：

```python
result = [s.upper() for s in names if len(s) > 3]
```

一行。

第一次看到这行代码的 Java 老工程师，内心通常飘过五个字：**"这也算代码？"** 紧接着是第二个念头，有点慌：**"那我苦练三年的 Stream API，算什么？"**

听好了，这是本章的 Aha：**`for` 从句在左，`if` 从句在右，生产逻辑在中间——推导式不是压缩语法糖，它把"管道"画成了"流水线"。** Java 是横向的数据流思维，Python 是纵向的铸造思维：一炉钢水（源数据），过滤一遍（if），浇出一个模子（表达式）。

等你读 RAG 实战里那种一行处理一摞文档切片、Agent 里一行筛出可用工具的代码，你会回过味来——**Python 数据科学生态敢把"一行流"当文化供养，是因为 AI 时代数据处理本来就是"一进一出"的高频吞吐。**

## 不讲术语的版本：四种容器，一句话各配一句咒语

Python 的容器全家桶，用你做 Java 的已有概念锚定：

| 容器 | Java 对应 | 咒语 |
|---|---|---|
| `list` | `ArrayList` | 有序可变，默认武器，`[1, 2, 3]` |
| `dict` | `HashMap` | 键值对宇宙中心，`{"name": "Ada"}` |
| `set` | `HashSet` | 去重神器，`{1, 2, 3}` |
| `tuple` | 无对应（不可变多返回值信封） | `(lat, lng)`，坐标、返回多值专用 |

真正拉开差距的是三个"声明式暴力"工具：

**暴力一：推导式三兄弟。**

```python
[x * 2 for x in nums]              # list：一一映射
{n % 2 for n in nums}              # set：自动去重
{k: v * 2 for k, v in pairs}       # dict：键值重组
```

从"申请箱子 → for 循环 → 判断 → 塞箱子"的四步仪式，压缩成一次平板锻造。Java 老手第一次写会极度不适，一周后会极度舒适。

**暴力二：切片（Slicing），Java 根本没有这东西。**

```python
s = "Java到AI的90天"
s[::-1]        # 倒序
s[2:8]         # 截取
s[::2]         # 隔一个取一个
```

`str.substring` 是个方法调用，切片是**语言级语法**——`[start:stop:step]` 三件套，列表字符串通吃，还能倒序跳切。这个后续筛评测集、切文档块，你天天用。

**暴力三：zip 与 enumerate。**

```python
for i, name in enumerate(names):      # Java 的 fori 循环退休了
    ...
for name, score in zip(names, scores):  # 两个列表平行遍历
    ...
```

Java 里 `fori` 要写下标，一个 bug 高发区。Python 说：要下标？`enumerate` 直接给你 `(下标, 值)` 元组；两个 List 要配对？`zip` 打包成双元组。**又一次仪式感删除。**

## Java 老司机对照室

| Java 8 的你以为 | Python 的真相 | 心法迁移 |
|---|---|---|
| `stream().map().filter().collect()` | `[expr for x in it if cond]` | 纵向铸造代替横向管道 |
| `String.substring(2, 8)` | `s[2:8]` | 语法级操作，不是方法 |
| `new StringBuilder(s).reverse()` | `s[::-1]` | 一行，无需对象 |
| `for (int i = 0; i < n; i++)` | `for i, v in enumerate(lst):` | `fori` 正式退役 |
| `Map<String, Integer> m` 构建循环 | `{k: v for k, v in items}` | 字典铸造机 |
| `Collectors.toSet()` | `set(...)` 或 `{...}` | 一键去重 |
| `Arrays.asList(a, b)` | `(a, b)` | 元组打包，多返回值专用信封 |
| `Optional<Integer> idx` | `lst.index(x)`（找不到会抛异常） | Python 偏爱"炸掉"而不是"包装成 null 风格" |

看到最后一行别急着吐槽：Python 的哲学是**错了就炸，响亮地炸**——`AttributeError`、`IndexError`、`KeyError` 全是一炸了之，**这反而让 bug 无所遁形**，跟你 02 篇学的"运行期兜底"是同一条设计路线的不同切面。

## 动手实验室

### 实验 1：同一需求的 Java/Python 双语对照

```python
names = ["alice", "bob", "charlie", "de", "elizabeth"]

# Java 老司机的肌肉记忆写法（能跑，但一眼就被认出是"Java 翻译腔"）
result_a = []
for n in names:
    if len(n) > 3:
        result_a.append(n.upper())

# Pythonic 一行流（社区行话：这才是自己人）
result_b = [n.upper() for n in names if len(n) > 3]

print(result_a, result_b)   # ['ALICE', 'CHARLIE', 'ELIZABETH'] 两份相同
```

跑通后做个练习：把这段 `result_a` 的结构删掉，改成列表推导式。**迁移成本比想象的还低，心理关比技术关大。** 三周后你会忘记自己写过 fori。

### 实验 2：切片四连击

```python
s = "手把手教你转大模型"
print(s[::-1])     # 型模大转你教手把手  倒序
print(s[2:5])      # 手教你        前闭后开，Java substring(2,5) 一个味
print(s[::2])      # 手手你大型     隔一个取一个
print(s[-3:])      # 大模型        取尾巴，负索引从右数
```

注意 `[2:5]` 是**前闭后开**区间——和 `substring(2,5)` 语义一致，你的肌肉记忆可以无缝搬迁。而 `[-3:]` 这种"我要尾巴"的需求，Java 要算 `s.length()-3`，Python 直接负数索引，又一次自由得让人想报警。

### 实验 3：dict 铸造机——RAG 元数据处理预演

```python
# 模拟检索返回的文档列表（真身长这样：第 13 篇的 retrieve() 会返回 (source, content, score)）
docs = [
    {"id": 1, "content": "年假制度...", "score": 0.82},
    {"id": 2, "content": "报销流程...", "score": 0.61},
    {"id": 3, "content": "考勤规则...", "score": 0.95},
]

# 按分数降序取前 2，抽出 id 组成列表
top2_ids = [d["id"] for d in sorted(docs, key=lambda d: -d["score"])[:2]]
print(top2_ids)   # [3, 1]

# 抽取 content 字段列表——AI 管道里的高频动作
contents = [d["content"] for d in docs]

# id -> score 映射，一行造字典
score_map = {d["id"]: d["score"] for d in docs}
```

`key=lambda` 今天先用（lambda 是下篇主角），感受一下：**排序 + 切片 + 推导 = 三招完成一次数据加工。** 这就是 Python 在数据科学界屠杀 Java 的全套作案工具。

### 实验 4：zip 的甜蜜与坑

```python
names = ["检索", "重排", "生成"]
scores = [0.9, 0.8]

for name, score in zip(names, scores):
    print(name, score)
# 只输出两行！zip 以短的那个为准，静默截断

# 严格模式：不等长立即报警（Python 3.10+，处理评测集时救命）
for name, score in zip(names, scores, strict=True):
    print(name, score)   # ValueError: zip() argument 2 is shorter than argument 1
```

这个坑值得单独说：Java Stream 里长度不齐顶多是空操作，**Python 的 `zip` 默认静默吞数据**——AI 管道里"悄咪咪少了三条"是最阴间的 bug。记住这个 `strict=True`——第 13 篇入库、第 21 篇评测集，"悄咪咪少了几条数据"的 bug 会以贵得多的方式咬你一口。

## 费曼复述卡

1. 向同事解释推导式的"铸造"比喻：为什么说 Python 是纵向铸造、Java Stream 是横向管道？用实验 1 两段代码比划。
2. 不用查资料，说出切片的 `[start:stop:step]` 三兄弟各自含义；`s[::-1]` 为什么能倒序？
3. `zip` 静默截断的坑，换成 Java 行为各是什么样？为什么这在 RAG 管道里特别危险？（提示：想想"检索到 5 篇文档，只有 3 篇被塞进上下文"）

三题过不了，回到"不讲术语的版本"重读暴力二。切片和推导式是你读 AI 源码的识字率——**认不全字，再好的书也读不出味道。**

## 今日一句话

> Java 用管道横向流数据，Python 用模具纵向铸数据——推导式省的不是代码行数，是你大脑的上下文切换。

---

下一篇：[04 · 函数是一等公民：lambda、闭包与黑魔法装饰器](./04-functions.md)（返回 [目录](./index.md)）
