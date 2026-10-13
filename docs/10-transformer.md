# 10 · Transformer：一场关于"注意力"的注意力经济

## 先讲给朋友听（如果你只有一分钟）

> 老模型读句子像"传话游戏"：第一个词耳语给第二个，第二个再耳语给第三个——传到队尾，早忘了开头。Transformer 发明了微信群聊：**每个词都能直接听到所有其他词，自己决定谁的话更重要。** 2017 年那篇改变世界的论文标题就叫《Attention Is All You Need》——你需要的一切，就是"注意力"，别的都可以扔。

## 你的 Aha Moment

先看一个翻译任务的中场战况：

"**The** cat didn't cross the street because **it** was too tired."

翻译 `it` 的时候，三岁的译者知道 `it` 指"猫"而不是"街道"。模型怎么做到？它得完成一次**远距离指代消解**——`it` 在句子第 10 个词，`cat` 在第 2 个。

RNN 时代的做法就是传话游戏：`cat` 的信息经过 8 次中转才到 `it`，每中转一次衰减一点，等到了 `it` 手上，信息只剩"十米之内有个活物"。

Transformer 的做法：**`it` 直接问全场每个词"你对我有用吗"，`cat` 举手："我，0.9，主语就是我。"过程结束。**

Aha 在这三个转变：

1. **距离消失了**：任意两个词一步直达，没有"中转衰减"
2. **相关性强加了权重**：不是全场等量接收，是"谁相关听谁的"
3. **项项可并行**：传话游戏必须排队，微信群聊可以同时发言——**这正是 GPU 能榨干算力的原因，也是为什么大模型烧的是显卡而不是 CPU**

理解了"注意力"，你未来每一行跟模型有关的代码都有了直觉：为什么 Prompt 里塞满无关内容会稀释答案质量（**注意力预算被摊薄**）、为什么关键指令要放在开头或结尾（**位置偏见**，09 篇的 lost in the middle 的机理源头）、为什么长上下文文档问答需要检索而不是全塞（**摊薄的极致就是 RAG**）。

## 不讲术语的版本：一次图书检索的全程

忘掉公式。把 Self-Attention（自注意力）想成一次图书馆查询：

**图书馆里有 N 本书（token）**。每本书身上贴着三张不同的卡片：

| 卡片 | 角色 | 类比 |
|---|---|---|
| Query（问询） | 我是谁、我在找什么 | 读者手里的检索需求 |
| Key（索引） | 我这本书讲什么、谁能配我 | 图书索引卡 |
| Value（内容） | 我真正携带的信息 | 书的正文 |

**一次注意力计算 = 一个读者进场，跟全场比对：**

1. 读者举起自己的 **Query**："我是一个代词，我要找我的先行词"
2. 逐本书比对 Key：主语书目录写着"生物/动物"——匹配度 0.9；街道书写着"基础设施"——匹配度 0.05
3. 所有匹配分过一个 softmax，变成一组权重——**这是注意力分配的瞬间**：主语书分到 0.9 的"注意力预算"，街道书只剩零头
4. 按权重把每本书的 **Value**（正文内容）加权倒进一杯新的鸡尾酒——**这就是这个位置的新表示**

一杯鸡尾酒 = 一个 token 融合了全场信息之后的新身份。模型每层都重复几十次这个过程（大模型有 60~100+ 层），每层的鸡尾酒都比上一层更醇——最后一层出来的东西，就是"理解上下文之后的你"。

**多头注意力**？就是同一个图书馆开了八个不同主题的检索窗口（语法关系组、指代组、情感组……同时独立比对，最后拼一起）。**位置编码**？因为微信群聊有时间虚无病——没人记得谁先说的——所以每个词进场前，管理员给它别一个"座位号"徽章（sinusoidal 或 RoPE）。**KV Cache**？图书馆发现昨天那个读者的检索结果今天还在用，就办了张月卡缓存——推理加速的关键工程，第 24 篇部署 vLLM 时你会见到它的商业化成品。

#### 追问一：多头到底是"多"在哪？为什么不是越多越好？

单头注意力有个隐蔽的缺陷：**同一个 Q/K/V 投影只能表达一种关系。** 拿"小明把书给了小红，因为她很累了"举例：处理"她"时，一个头可能同时在权衡"指代谁"和"为什么累"——两种完全无关的关系挤在同一个打分空间里，互相干扰。

多头把这件事做得很像你熟悉的架构：**把 d_model 维切成 h 份，每份独立做一次完整注意力，最后拼接再投影一次。**

```
单头: [d_model=4096] ──► 一次注意力 ──► [4096]

多头: [4096] ─┬─► head1(64维) ──► 注意力 ─┐
             ├─► head2(64维) ──► 注意力 ─┼─► concat [4096] ──► 投影 ──► [4096]
             ├─► ...                              │
             └─► head64(64维) ─► 注意力 ─┘
```

**Java 类比**：这就是把一次 `SELECT * FROM orders WHERE user_id=?` 拆成 h 个并行查询，各走各的索引（按下单索引、按金额索引、按时间索引），最后 `UNION` 回来。**每个 head 就是一路独立的召回通道。**

**代价与经验值**：注意力矩阵的显存开销与 `头数 × seq_len²` 成正比，**不是线性的**。所以工程上 `head_dim` 通常固定（64 或 128），头数随模型规模增长——4B 模型大约 32-40 头，70B 能到 64+ 头。**头数不是越多越好：再多的头会学到高度相似的模式，白烧显存。**

#### 追问二：位置编码为什么必需——它补的是哪种"病"？

注意力机制的"attention is all you need"有个反直觉的后果：**它对顺序完全无感。**

```
"小明打了小红"  和  "小红打了小明"
```

对纯注意力来说，**这两句话是同一个意思**——每个词照样去全场比对、照样找到对方，只是权重分配完全一样。注意力能看出"谁和谁相关"，看不出"谁在谁前面"。

而语言里顺序就是意义。你写 Java 时知道 `a[i]` 和 `a[j]` 交换位置就是不同的语义；**注意力层如果没有位置信号，就退化成了"集合语义"**。

位置编码就是在词向量进场前，**给每个位置加一个可区分的向量**：

```
第0个词: [词向量] + [座位号0的徽章]
第1个词: [词向量] + [座位号1的徽章]   ← 徽章两两不同，模型就能分辨"先后"
...
```

**Java 类比**：这就是给 `HashMap` 的 key 补一个 `seqId`——`HashMap` 本身只保证 key 唯一不保证插入顺序，你要顺序语义就得自己维护一个 `sequenceId` 字段。位置编码就是把 `sequenceId` 变成模型能直接吃的一个维度。

现代模型用 **RoPE（旋转位置编码）** 而不是最早的 sinusoidal：它把位置编码成对向量旋转，"相对距离"在计算里保持不变——**"离我 3 个词"比"我在第 7 位"更重要**，RoPE 直接让注意力天然感知相对距离。这也是 2026 年主流开源模型（Llama 系、Qwen 系）几乎全部采用 RoPE 的原因。

## 追问三：KV Cache 的显存账（这是你做本地部署时真正要算的数）

"KV Cache 是个加速技术"是句空话。**你真正需要知道的是：它吃多少显存？** 因为在你的 24GB MacBook 上，这笔账决定了你能开多大上下文、能挂几个并发。

**算式**（记住这一行就够）：

```
KV Cache 字节数 = 层数 × KV头数 × head_dim × 2(K和V) × 2(fp16每参数2字节) × 上下文长度
```

```python
def kv_cache_gb(layers, kv_heads, head_dim, ctx, dtype_bytes=2):
    """算一个模型在给定上下文下的 KV Cache 显存占用（返回 GB）"""
    return layers * kv_heads * head_dim * 2 * dtype_bytes * ctx / 2**30

# 作者机器 oMLX 日志的真实参数（Qwen2.5-0.5B）
layers, kv_heads, head_dim = 24, 2, 64
print(f"每 token: {kv_cache_gb(layers, kv_heads, head_dim, 1) * 2**30 / 1024:.0f} KB")
print(f"每 64-token 块: {kv_cache_gb(layers, kv_heads, head_dim, 64) * 2**30 / 1024:.0f} KB")
# 输出: 每 token: 12 KB | 每 64-token 块: 768 KB  ← oMLX 日志实测值，完全吻合
```

跑一下，你就得到了这张**部署前必算的账**（自己按你要用的模型改参数）：

| 模型 | KV 头×head_dim | 4K 上下文 | 32K 上下文 |
|---|---|---|---|
| Qwen2.5-0.5B（24层） | 2 × 64 | 0.05 GB | 0.38 GB |
| Llama-3-8B（32层） | 8 × 128 | 0.50 GB | **4.00 GB** |
| Qwen-72B（80层，GQA） | 8 × 128 | 1.25 GB | **10.00 GB** |

**三个立刻能用的结论**（每个都在本地部署时真金白银）：

1. **上下文开 4K → 32K，KV Cache 涨 8 倍**。你想在 24G 卡上开 128K 上下文？先算这笔账再决定。
2. **KV Cache 与"参数量"无关，只与"结构"有关**。一个 72B 大模型的 KV Cache（10G @32K）可能比 8B 模型的权重（16G）还小——因为大模型普遍用了 **GQA（分组查询注意力）**，多个 Q 头共享一个 KV 头，KV 头数远小于 Q 头数。
3. **这就是 oMLX/MLX 要做"KV Cache 分层（内存热层+SSD 冷层）"的动机**（23 篇实测过）——它把已经算过的 KV 在多轮请求间持久化，第二次问相关问题就不用重算。你在 oMLX 日志里看到的 `768 KB per 64-token block`，就是上面这个算式的逐块输出。

## Java 老司机对照室

| Transformer 概念 | 你已经懂的模式 | 一句话翻译 |
|---|---|---|
| RNN/LSTM 顺序依赖 | 责任链模式 | 逐个传递，长链衰减 |
| Self-Attention | 广播订阅 + 加权投票 | 一步直达全场，按相关分分赃 |
| Q/K/V 三件套 | 路由规则 / 匹配键 | Key 是价签，Query 是出价，Value 是货 |
| softmax | 权重归一化 | 打分变概率，总和为 1 |
| Multi-Head | 多消费者组 / 多视图 | 八种委员会并行投票，结果拼接 |
| Positional Encoding | 消息队列里的 sequence id | 给"无时间概念"的计算补上顺序 |
| Token Embedding | 特征向量化 | 第 09 篇的 GPS 坐标系 |
| LayerNorm + 残差 | 熔断 + 兜底链路 | 稳住训练，让梯度还有路可退 |
| Decoder 逐词生成 | 05 篇的 yield | 一个 token 一杯鸡尾酒往外端 |
| KV Cache | 缓存 / 预计算 | 昨天算过的 Key/Value 今天别重算 |

最后一行再强调：**模型生成是逐 token 的，而 KV Cache 把"已经算过的上下文 QK"缓存下来**——这是推理服务能撑住高并发的核心技术之一，第 24 篇部署优化时再见。

## 动手实验室

### 实验：手算一次注意力（全程只用 math 库）

任务：让模型"读" `猫 追 老鼠`，算每个词的新表示。不调任何库，一张纸的数学：

```python
import math

# 三个词的玩具 embedding（4 维，真实模型是几千维）
tokens = ["猫", "追", "老鼠"]
E = {
    "猫":   [1.0, 1.0, 0.0, 0.0],   # 动物属性拉满
    "追":   [0.0, 1.0, 1.0, 0.0],   # 动作属性
    "老鼠": [1.0, 0.0, 1.0, 0.0],   # 又是动物
}

# 简化：Q=K=V=E（真实里 Wq/Wk/Wv 是训练出来的三个大矩阵）
Q = {t: E[t] for t in tokens}
K = {t: E[t] for t in tokens}
V = {t: E[t] for t in tokens}

def dot(a, b):
    return sum(x * y for x, y in zip(a, b))

def softmax(scores):
    m = max(scores)                      # 数值稳定技巧
    exps = [math.exp(s - m) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]

D = 4   # 向量维度，用于缩放
print("谁在关注谁（注意力权重矩阵）:")
for q_tok in tokens:
    # 1. Query 和每个 Key 打分，除以 sqrt(d)
    scores = [dot(Q[q_tok], K[k_tok]) / math.sqrt(D) for k_tok in tokens]
    # 2. softmax 归一化成"注意力预算"
    weights = softmax(scores)

    # 3. 按权重把所有 Value 加权求和 = 新表示
    new_vec = [0.0] * D
    for w, k_tok in zip(weights, tokens):
        for i in range(D):
            new_vec[i] += w * V[k_tok][i]

    print(f"\n[{q_tok}] 关注分布: " +
          " ".join(f"{w:.2f}→{tok}" for w, tok in zip(weights, tokens)))
    print(f"  新表示: {[round(x, 2) for x in new_vec]}")
```

跑出来你会看到（数字以实际运行为准）：

```
[猫]   关注分布: 0.45→猫 0.27→追 0.27→老鼠
[追]   关注分布: 0.27→猫 0.45→追 0.27→老鼠
[老鼠] 关注分布: 0.27→猫 0.27→追 0.45→老鼠
```

盯着这三行看十秒钟，然后接受一个诚实的结论：

**这个玩具版里，"猫"和"老鼠"互相分到 0.27 的预算，"追"也拿到 0.45 的自关注——最原始的注意力机制，本质上就是"语义聚类"：彼此像的词，互相关注得多。** 我们的 `Q=K=V=E` 简化版，还没有本领让"追"主动去找主语宾语。

而真实 Transformer 有训练出来的 `Wq`/`Wk` 矩阵——正是这两组矩阵，在几万亿词的训练里学会了"代词找先行词""动词找主语"这类角色匹配。**刚才我们简化的每一步都还在，只是 Key 不再是 Embedding 本身，而是一张被训练打磨过的"专用匹配卡片"。**

所以你在实验里看到的是注意力机制的"素颜"，图书馆那节讲的是训练后的"妆容"。两者都不骗你，只是出镜阶段不同。

至于这七步——**打分 → 缩放 → softmax → 加权求和**——就是 Transformer 论文的全部内核。真实模型无非是把 4 维换成 4096 维、3 个词换成几千个 token、这个动作堆 60 层重复几万次。**你亲手走完了一次，以后看任何架构图都不慌——它们都只是这台机器的外壳。**

### 实验 2：搭一台迷你 Transformer（把追问一、二全部跑起来）

实验一是一只"素颜裸奔"的头。这一个实验把整台机器装起来——**多头 + 位置编码 + 残差 + LayerNorm**，全手写，仍然只用 `math`：

```python
import math, random

random.seed(42)
TOKENS = ["小明", "把", "书", "给", "小红"]
D_MODEL = 8          # 极小的模型维度
N_HEADS = 2          # 两个头，验证"多头各看各的"
HEAD_DIM = D_MODEL // N_HEADS

# ---------- 1. Token Embedding：每个词一个初始向量 ----------
embedding = {t: [random.uniform(-1, 1) for _ in range(D_MODEL)] for t in TOKENS}

# ---------- 2. 位置编码：给每个位置一个可区分的徽章 ----------
pos_encoding = []
for i in range(len(TOKENS)):
    angle = i * (1.0 / 10000 ** (2 * (i % 2) / D_MODEL))     # RoPE 简化版：偶数位偶频率，奇数位奇频率
    vec = [math.cos(angle) if d % 2 == 0 else math.sin(angle) for d in range(D_MODEL)]
    pos_encoding.append(vec)

# 加上位置编码（这就是"座位号徽章"的数学实现）
X = [[embedding[t][d] + pos_encoding[i][d] for d in range(D_MODEL)]
     for i, t in enumerate(TOKENS)]

# ---------- 3. 投影出 Q/K/V（真实模型是训练出来的矩阵，这里用随机投影） ----------
def project(vecs, seed):
    rnd = random.Random(seed)
    W = [[rnd.uniform(-0.5, 0.5) for _ in range(D_MODEL)] for _ in range(D_MODEL)]
    return [[sum(v[r] * W[r][c] for r in range(D_MODEL)) for c in range(D_MODEL)] for v in vecs]

Q, K, V = project(X, 1), project(X, 2), project(X, 3)

# ---------- 4. 多头注意力：每个头独立算，再拼回来 ----------
def softmax(xs):
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps)
    return [e / s for e in exps]

def one_head_attention(Q, K, V, h):
    """第 h 个头：在 [0:HEAD_DIM] 这个子空间里做注意力"""
    q_slice = [v[h * HEAD_DIM:(h + 1) * HEAD_DIM] for v in Q]
    k_slice = [v[h * HEAD_DIM:(h + 1) * HEAD_DIM] for v in K]
    v_slice = [v[h * HEAD_DIM:(h + 1) * HEAD_DIM] for v in V]
    out = []
    all_weights = []
    for i, qi in enumerate(q_slice):
        scores = [sum(qi[d] * kj[d] for d in range(HEAD_DIM)) / math.sqrt(HEAD_DIM) for kj in k_slice]
        weights = softmax(scores)
        all_weights.append(weights)          # 存下每个 token 的关注分布
        out.append([sum(weights[j] * v_slice[j][d] for j in range(len(V)))
                    for d in range(HEAD_DIM)])
    return out, all_weights

heads_out, head_weights = [], []
for h in range(N_HEADS):
    out, w = one_head_attention(Q, K, V, h)
    heads_out.append(out)
    head_weights.append(w)

# 拼接各头输出 → 残差连接 → LayerNorm
def layer_norm(vec, eps=1e-6):
    mean = sum(vec) / len(vec)
    var = sum((x - mean) ** 2 for x in vec) / len(vec)
    std = math.sqrt(var + eps)
    return [(x - mean) / std for x in vec]

concat = []
for i in range(len(TOKENS)):
    merged = []
    for h in range(N_HEADS):
        merged += heads_out[h][i]
    residual = [X[i][d] + merged[d] for d in range(D_MODEL)]   # 残差：原信息 + 新信息
    concat.append(layer_norm(residual))                        # LayerNorm：稳住数值

# ---------- 5. 打印结果 ----------
print("多头注意力的分布（每个头看的是不同子空间）：")
for h in range(N_HEADS):
    for i, t in enumerate(TOKENS):
        top = max(range(len(head_weights[h][i])), key=lambda j: head_weights[h][i][j])
        print(f"  head{h} 处理「{t}」最关注「{TOKENS[top]}」({head_weights[h][i][top]:.2f})")

print("\n最终每个词的表示（前3维，已过残差+LayerNorm）：")
for t, v in zip(TOKENS, concat):
    print(f"  {t}: {[round(x, 2) for x in v[:3]]}")
```

**跑完观察三件事**：

1. **两个头的关注模式确实不同**——对比"书"这一行：`head0` 让它最关注「小红」（0.24），而 `head1` 让它最关注自己（0.29）。同一句话，同一个词，两个头给出了不同的答案。**这正是追问一说的"每个头一路独立召回通道"。**

   但别被"不同"骗了：**你看「小明」和「把」，两个头都指向了「给」。** 为什么？因为这里 Q/K/V 用的是**随机投影**——我们没有真实模型训练出的"Wq/Wk 那样会分工的投影矩阵"。**真实模型的多头之所以分工，是几万亿词训练出来的结果，不是随机初始化的副产品。** 你这个玩具实验演示的是"结构支持分工"，不是"分工真的发生了"。

2. **加了位置编码后，"给"和"把"的位置不同**——即使它们的词向量来自同一个分布，位置徽章（RoPE 简化版）让它们在几何上分开了。没有这个徽章，"小明把书给小红"和"小红把书给小明"在模型眼里是一样（追问二说的病）。

3. **残差 + LayerNorm 之后数值被稳住了**——输出每维大致在 ±2 之间，不会因为堆了几十层就爆炸。这就是对照室里"熔断+兜底链路"那个类比的真实作用。

**这台迷你 Transformer 有 8 维、2 个头、1 层，而真实的 Qwen3-72B 是 4096 维、64 个头、80 层。但结构一模一样**——你现在亲手跑通了它，未来看到任何架构图，都只是数一数"多少维、几个头、多少层"，然后把它缩小回眼前这台小机器。

## 费曼复述卡

1. 用"图书馆三张卡片"的比喻，向同事讲清 Q/K/V 各自的角色，不许用公式。
2. RNN 的"传话游戏"比喻里，Transformer 解决了什么具体问题？为什么这让 GPU 并行成为可能？
3. 实验里"猫"和"老鼠"互相分的注意力预算来自什么几何性质？真实模型让"代词找先行词"成为可能，靠的是哪两个训练出来的矩阵？
4. （新）把你机器上 oMLX 的实测数字对进那个 KV Cache 算式：24 层 / 2 个 KV 头 / head_dim 64，算出每 64-token 块多少 KB？为什么大模型的 KV Cache 反而可能比权重小？
5. （新）为什么说"没有位置编码，'小明打了小红'和'小红打了小明'在模型眼里是同一句话"？位置编码补的到底是哪种病？

三题过不了，回到"不讲术语的版本"重走一遍图书馆。**本篇是全书理论密度的顶点，也是最后一篇纯理论——从这里开始，全部内容都为"把它用起来"服务。**

## 今日一句话

> Transformer 的本质是一场全民微信群聊：每个词直接问所有词"你怎么看我"，注意力预算按相关度分赃——理解、幻觉、Prompt 技巧，全从这场分赃里诞生。

---

下一篇：[11 · 第一次调用：写一个带重试的流式对话接口](./11-first-call.md)（返回 [目录](./index.md)）
