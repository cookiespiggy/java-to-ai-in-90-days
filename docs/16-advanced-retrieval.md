# 16 · 生产级检索：混合检索、RRF、Rerank 与权重

## 先讲给朋友听（如果你只有一分钟）

> 第 13 篇的纯向量检索，是"秀才遇到兵"的检索——它听得懂意思，但对不上黑话。BM25 反过来，字字计较却不懂变通。生产级检索的做法是：**两路各查各的，然后按"名次"合并，再请一个精读模型重排**。这个组合在一篇 2026 年的基准测试里，把召回率从单路的 0.587 提到了 **0.816**。

## 你的 Aha Moment

先看一组真实数字（来自 arXiv 2604.01733，金融文档问答场景的实测）：

| 检索方式 | Recall@5 |
|---|---|
| 纯稠密向量 | 0.587 |
| 纯 BM25 关键词 | 0.644 |
| **BM25 + 向量 混合（RRF 融合）** | **0.695** |
| **混合 + Cross-Encoder 精排** | **0.816** |

三个结论，每个都值得刻进肌肉记忆：

1. **纯向量居然是最差的。** 在专业文档里，BM25 这种"老掉牙"的关键词算法几乎全指标胜过大模型时代的新贵 dense 检索。为什么？用户搜"增值税专用发票抵扣期限"，他不会说"进项税额认证时效"——**真实查询里塞满了缩写、型号、错别字、内部黑话，这些都是字面匹配的活。**
2. **混合不是优化项，是及格线。** RRG 融合比两路任意一路都稳，且"never loses"——另一组 BEIR 基准（arXiv 2608.00452）测出融合比纯向量平均高 4.3%、比纯 BM25 高约 10%，在 MSMARCO 上从 0.66 干到 0.80。
3. **精排是最大的一分。** 混合召回 50 个候选，用 cross-encoder 精排出 top 10，比"混合完直接取前 10"再涨 17.4%。同样的召回集，排序换一层，效果天差地别。

还有一条反直觉的：同一篇论文里，**CRAG（查询重写）反而输给了朴素的混合融合**，多查询的 RAG-Fusion 也几乎没有增益。翻译成人话：**别折腾花活，先把两路召回+精排做扎实。**

Aha 落在哪？落在"**你没有写出烂代码，你只是选错了召回方式**"。13 篇那套纯 dense 的玩具代码，工程上完全正确，但在真实文档上就是拿不到分——**RAG 的效果天花板是检索决定的，不是 Prompt 决定的。**

## 不讲术语的版本：两路、融合、精排、权重

**第一路：BM25（字面派）。**

老牌排序函数，核心就三件事：词频（出现的词在文档里出现几次）、逆文档频率（这词稀不稀有，比如"的"没权重）、长度归一化（长文档别占便宜）。**它的强项是精确匹配**：错误码 `E0308`、法条编号、产品型号、人名。它的弱项：问"怎么请长假"去找不到写"年假制度"的文档。

**第二路：Dense 向量（意思派）。**

13 篇讲透了，强项是语义、同义、跨语言；弱项是专有名词和罕见词会"融进语义"里糊掉。

**融合层：RRF（Reciprocal Rank Fusion，倒数排名融合）。**

两路各返回一个有序列表，怎么合成一个？千万别把两个分数直接相加——**BM25 的分数量级和余弦相似度根本不在一个宇宙**（这就是"score normalization"的地狱）。RRF 的解法优雅得让人想鼓掌：

```
score(doc) = Σ 1 / (k + rank_i(doc))
```

只看**名次**，不看分数。一个文档在两路里分别排第 2 和第 5，得分就是 `1/(60+2) + 1/(60+5)`。那个 `k`（工业界默认 60）用来压平头部差异，让"两路都觉得你还行"的文档胜过"一路第一但另一路排 50 名"的文档。

**这就是"不用调参"的代价与收益**：免掉了分数归一化，但丢掉了一个旋钮——当你知道自己的查询 90% 是黑话（内部知识库常这样），你会想让 BM25 权重更高。这就是你说的 **Dense Weight 配置**。

**精排层：Cross-Encoder 重排。**

召回 50 个候选要合并上下文，塞不进 Prompt（09 篇的台面铁律）。思路是二段式：**粗排求全，精排求准**。粗排快而糙，精排慢而准。

- Bi-encoder（召回用）：query 和文档分别编码，相似度是点积。**可以离线预计算**，所以快
- Cross-encoder（精排用）：query 和文档拼一起过一次模型，逐 token 交叉注意力，输出相关分。**无法预计算**，只能现场算 50 次，所以只用在小候选集上

代价参考（A100 实测）：MiniLM 33M 精排 128 条 43.5ms，bge-reranker-v2-m3（568M）409.6ms——**贵，所以只排几十条，不排几千条。**

**权重层：加权融合。**

`α·sparse + (1-α)·dense`，α 就是你问的 Dense Weight。Elasticsearch/OpenSearch/LanceDB 都内建。但注意代价：**加权前必须归一化**（min-max 或 z-score），否则 BM25 的 20 分能把 0.8 的余弦碾成渣。实测（arXiv 2608.00452）显示：RRF 和加权融合的召回几乎打平，但加权融合的 nDCG@10 更好，因为它保留了分数幅度信息。**结论：先用 RRF 起步（零调参），有评测集之后再上加权融合调 α。**

## Java 老司机对照室

| 检索概念 | 你已经懂的概念 | 一句话翻译 |
|---|---|---|
| BM25 | Lucene/ES 默认打分器 | 你用过一千次了 |
| 两路召回 | 多路召回（ES + 向量并行查） | 并行查询后合并 |
| RRF 融合 | 归并排序 + 投票制 | 看名次不看分数 |
| k=60 | 平滑常数 | 防头部马太效应 |
| 加权融合 α | 融合权重 | 归一化后加权求和 |
| Bi-encoder 预计算 | 离线索引构建 | 建库算一次，查询只算 query |
| Cross-encoder 精排 | 二段排序精排 | 慢而准，只排小集合 |
| 召回 50 精排出 10 | funnel 逐层收窄 | 每层收窄 5~10 倍 |

## 动手实验室

### 实验 1：纯手写 RRF 融合（零依赖，跑通机制）

接着 12 篇的手搓 RAG 内核，给 `retrieve()` 加第二路和融合层：

```python
import re, math

DOCS = {
    "doc1": "员工年假：入职满一年享有5天带薪年假。满十年10天。满十五年15天。",
    "doc2": "员工病假：需提供二级以上医院诊断证明。病假工资按基本工资80%发放。",
    "doc3": "报销制度：差旅报销需在行程结束后30天内提交。发票抬头必须为公司全称。",
    "doc4": "考勤制度：标准工作时间为早9晚6。每月允许3次忘打卡，第4次起每次扣款50元。",
    "doc5": "公司食堂：工作日提供午餐。加班到20点后可用夜宵券。周四有小龙虾加餐。",
    "doc6": "差旅住宿标准：一线城市每晚上限500元，二线城市350元，需附酒店水单。",
}

# ---- 路 1：BM25（玩具版，机制与真的 BM25 同构） ----
def tokenize(s):
    """中文玩具分词：单字 + 相邻二元组。
    注意别用 [一-龥]{1,2} 按'贪心成对'切——'住酒店'会切成 住酒/店能，把'酒店'
    这个词拦腰截断，BM25 直接全军覆没（这是我第一版就踩的坑）。"""
    chars = re.findall(r"[一-龥]", s)
    return chars + [a + b for a, b in zip(chars, chars[1:])]

class ToyBM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.tf = {n: {} for n in docs}
        self.dl = {}
        for n, t in docs.items():
            cnt = {}
            for w in tokenize(t):
                cnt[w] = cnt.get(w, 0) + 1
            self.tf[n] = cnt
            self.dl[n] = len(tokenize(t))
        self.avgdl = sum(self.dl.values()) / len(self.dl)
        # idf：词在几个文档里出现过
        df = {}
        for n in docs:
            for w in self.tf[n]:
                df[w] = df.get(w, 0) + 1
        N = len(docs)
        self.idf = {w: math.log(1 + (N - d + 0.5) / (d + 0.5)) for w, d in df.items()}
        self.k1, self.b = k1, b

    def search(self, q, top_k=3):
        qw = tokenize(q)
        scores = {}
        for n in self.tf:
            s = 0.0
            for w in qw:
                if w not in self.tf[n]:
                    continue
                tf = self.tf[n][w]
                norm = tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * self.dl[n] / self.avgdl))
                s += self.idf[w] * norm
            scores[n] = s
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

# ---- 路 2：Dense（12 篇的字符二元组 + Jaccard） ----
def dense_embed(s): return {s[i:i+2] for i in range(len(s) - 1)}
def jaccard(a, b): return len(a & b) / len(a | b) if a and b else 0.0

bm25 = ToyBM25(DOCS)
DB_DENSE = [(n, dense_embed(t)) for n, t in DOCS.items()]

def dense_search(q, top_k=3):
    qv = dense_embed(q)
    return sorted(((n, jaccard(qv, v)) for n, v in DB_DENSE),
                  key=lambda x: x[1], reverse=True)[:top_k]

# ---- 融合层：RRF ----
def rrf_fuse(*ranked_lists, k=60):
    """传入若干 [(doc, score), ...] 有序列表，按名次融合"""
    fused = {}
    for lst in ranked_lists:
        for rank, (doc, _) in enumerate(lst):   # rank 从 0 开始
            fused[doc] = fused.get(doc, 0) + 1.0 / (k + rank + 1)
    return sorted(fused.items(), key=lambda x: x[1], reverse=True)

# ---- 见证时刻：一个"两路结论相反"的查询 ----
Q = "住酒店能报多少"
sparse = bm25.search(Q, top_k=3)
dense = dense_search(Q, top_k=3)
print("BM25  路:", sparse)
print("Dense 路:", dense)
print("RRF 融合:", rrf_fuse(sparse, dense))
```

跑这个查询，看两路各自怎么赢：

- BM25 给 `doc6` 打 6.35 分，靠的是"酒店"这个词命中；`doc3` 拿 2.15，靠"报"字
- Dense 同样先选 `doc6`——因为二元组"酒店"照进了它的"语义坐标"

RRF 融合后 `doc6` 和 `doc1` 咬得很紧（0.0328 vs 0.0320）。**这个例子里两路是一致的，所以融合只是"确认"了结论。真正要混合的理由在实验 4：两路吵架的时候听谁的。**

### 实验 2：加权融合 + 权重那个旋钮

*（同一脚本接着写，`bm25`/`dense_search` 来自实验 1）*

```python
def minmax(scores):
    vs = list(scores.values())
    lo, hi = min(vs), max(vs)
    return {k: (v - lo) / (hi - lo) if hi > lo else 0.0 for k, v in scores.items()}

def weighted_fuse(sparse_scores, dense_scores, alpha=0.5):
    """alpha = 稀疏路权重；dense_weight = 1 - alpha。
    注意末尾的'无信号'处理：两路都零分时返回空列表，而不是随便指一个文档——
    否则纯 dense 在这些查询上不是'答错'，而是'抽签'，评测结果完全不可信。"""
    s, d = minmax(sparse_scores), minmax(dense_scores)
    fused = [(k, alpha * s.get(k, 0) + (1 - alpha) * d.get(k, 0)) for k in set(s) | set(d)]
    fused = sorted(fused, key=lambda x: x[1], reverse=True)
    return [] if not fused or fused[0][1] <= 0 else fused

sp_all = dict(bm25.search(Q, top_k=6))
dn_all = dict(dense_search(Q, top_k=6))
for alpha in (0.0, 0.3, 0.5, 0.7, 1.0):
    top = weighted_fuse(sp_all, dn_all, alpha)[:2]
    print(f"alpha={alpha} → {[n for n, _ in top]}")
```

拖动这条 α，看结果怎么漂。**注意：在只有 6 条的玩具语料上，两路经常给出同样的答案，所以 α 怎么拖都差不多——这正是小语料的欺骗性。换到你自己几百上千条真实文档上，它才会露出獠牙。**

### 实验 3：接一个真精排器（本地 CPU 就能跑）

需要先 `uv add sentence-transformers`（模型首次运行会自动下载，bge-reranker-base 约 278M，你的 HF 缓存里已经有 `BAAI/bge-reranker-v2-m3`，直接换模型名即可）。

```bash
uv add sentence-transformers
```

```python
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("BAAI/bge-reranker-base")   # 278M，Mac CPU 可跑
candidates = [DOCS[n] for n, _ in rrf_fuse(sparse, dense)[:5]]
pairs = [(Q, doc) for doc in candidates]
scores = reranker.predict(pairs)
ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
print("精排后首位:", ranked[0][0][:40])
```

**两段式的完整形状出来了：RRF 召回 5 个 → cross-encoder 重排 → 取前 2 塞进 Prompt。** 中文场景想要更强换 `BAAI/bge-reranker-v2-m3`（568M），代价是精排延迟从几十毫秒到几百毫秒——**这个 trade-off 要用你的 QPS 算，不要拍脑袋。**

### 实验 4：让权重和分段都由数据决定（本篇的灵魂）

*（仍在同一个脚本里接着写，`minmax`/`weighted_fuse`/`bm25`/`dense_search` 都来自实验 1、2）*

```python
EVAL = [
    ("年假多少天", ["doc1"]),
    ("病假工资怎么发", ["doc2"]),
    ("发票抬头错了怎么办", ["doc3"]),
    ("迟到扣钱吗", ["doc4"]),
    ("食堂有夜宵吗", ["doc5"]),
    ("出差住宿多少钱", ["doc6"]),
    ("工位餐补", ["doc5"]),
    ("去医院开的证明", ["doc2"]),
]

def top1_hit(fused, expect) -> bool:
    """空列表 = 两路都没信号，算未命中"""
    return bool(fused) and fused[0][0] in expect

for alpha in (0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0):
    misses = []
    for q, expect in EVAL:
        fused = weighted_fuse(dict(bm25.search(q, top_k=6)),
                              dict(dense_search(q, top_k=6)), alpha)
        if not top1_hit(fused, expect):
            misses.append(q)
    print(f"alpha={alpha}: 命中 {len(EVAL)-len(misses)}/{len(EVAL)}  失败: {misses}")
```

实测输出（按下表核对你跑的结果对不对）：

```
alpha=0.0: 命中 6/8  失败: ['迟到扣钱吗', '工位餐补']
alpha=0.2: 命中 8/8  失败: []
alpha=0.4: 命中 8/8  失败: []
alpha=0.5: 命中 8/8  失败: []
alpha=0.6: 命中 8/8  失败: []
alpha=0.8: 命中 8/8  失败: []
alpha=1.0: 命中 8/8  失败: []
```

**这几行就是本篇的题眼：**

1. **α=0.0（纯向量）是唯一不及格的**，死的两条全是关键词查询："迟到扣钱吗"里，dense 的二元组（迟到/到扣/扣钱/钱吗）在六份文档里**一个都匹配不上**，直接交了白卷；而 BM25 靠单字"扣"稳稳捞回 `doc4`。dense 的语义泛化在这种场景不是"猜错"，是"没信号"。
2. **只要给稀疏路 0.2 的权重就满分**——混合检索的甜点区很宽，但纯 dense 明确更差。这就是"混合是及格线，不是优化项"的数据证据。
3. 反过来说，如果你的查询全是"我想歇几天"这种口语，α 就该往 dense 偏——**方向取决于你的用户怎么提问，而这个答案只能评测集给。**

**调参的正确姿势不是凭感觉拧，是拿评测集扫。** 只换了融合层，一行模型代码都没动，分数差出两个点。下一篇（21 篇评测）会把这套仪表盘正式化。

## 费曼复述卡

1. 向同事解释：为什么不能把 BM25 分数和余弦相似度直接相加？RRF 怎么绕过这个问题的？
2. Bi-encoder 和 Cross-encoder 的区别是什么？为什么精排只能用后者？
3. 假设你的查询 90% 是内部黑话（产品型号、错误码），α 该往哪边调？你怎么用实验 4 证明？

三题过不了，把实验 1 的查询换成专业术语和口语各一个，再跑一遍两路输出。

## 今日一句话

> 生产级检索 = 字面派 + 意思派 + 按名次合并 + 精排精读——而权重不是调出来的，是评测集扫出来的。

---

下一篇：[17 · 后训练地图：为什么规则兜不住泛化](./17-posttraining-map.md)（返回 [目录](./index.md)）
