# 19 · 偏好对齐与 RLVR：让模型知道什么是"好"

## 先讲给朋友听（如果你只有一分钟）

> SFT 教模型"可以这样答"，偏好对齐教它"这样答比那样答强"。后者只需要你有一个朴素的判断力——**你不会写满分作文，但你一眼看得出哪个回答更烂。** 这个门槛，比 SFT 低得多。

## 你的 Aha Moment

先给你一组 2026 年的硬数据，来自对 **51 种后训练算法**的受控对比实验（oxRL，arXiv 2603.19335）。同样的数据、同样的基础设施，只换算法：

| 方法 | 成绩 |
|---|---|
| **SFT（纯监督微调）** | **54.4%** |
| IPO | 52.2% |
| KTO | 51.2% |
| DPO | 49.1% |
| SimPO | 38.7% |

三个结论，一个比一个反直觉：

1. **SFT 打败了所有偏好算法。** 你没看错——那个"最土"的监督微调，成绩压过一整柜子的花哨算法。
2. **DPO 家族内部差距小到可笑**：各种变体（RDPO、CDPO、CalDPO、BetaDPO…）互相之间差不到 **3.2 个百分点**，且小规模下 seed 方差就有 2 个百分点——**算法差异被噪声淹没了。**
3. 研究者管这个叫"规模依赖的排序反转"（scale-dependent ranking inversions）：**在小模型上选中的"最优算法"，换个大模型可能就不是它了。**

米宝的 Aha 应该在这里：**你纠结"用 DPO 还是 SimPO"的那两周，价值接近于零。** 同样的时间，回去把你的 300 条金数据打磨到 600 条，效果比换算法显著得多。

**这不是说偏好对齐没用，而是说它的用法。** 它真正不可替代的场景是：

- **SFT 写不出"标准答案"，但你能判断好坏**。"把这段话写得更专业一点"——你说不出"专业"的唯一定义，但你看到不专业的版本能立刻挑出来
- **模型在两个坏选择之间选错**。SFT 训完它不骂人了（因为它见过"不骂人"的范本），但遇到挑衅它可能选"阴阳怪气"而不是"礼貌拒绝"——这种"都不理想、但有个更好的"的场景，正是偏好对的猎场
- **杀死特定坏习惯**。模型总爱在结尾加"希望对你有帮助！"——准备 200 对 `{有这个废话的, 没有的}`，训完就好

**一半的偏好数据也不是问题**：KTO 只需要单条标注"好/坏"，不用成对构造。你项目里的用户点击数据、客服质检的打分记录，全是现成的 KTO 数据。

## 不讲术语的版本：从 DPO 到 GRPO 的光谱

**DPO（Direct Preference Optimization）：最实用的起点。**

数据长这样：

```json
{"prompt": "帮我把这句改专业：这破功能又挂了", "chosen": "该功能模块出现异常，建议核实服务状态", "rejected": "亲～这功能又崩了呀，是不是又没充值呀"}
```

DPO 的聪明之处：**它不需要训练一个"奖励模型"来打分**（那正是 RLHF 最贵的部分），直接在"选中答案"和"落选答案"之间把这个差距最大化。等于说"别告诉我几分算好，你告诉我这两个哪个好就行"。

代价：它是离线方法，**只能消化你事先收集的偏好对**，不能在训练中自己探索新答案。

**KTO / ORPO / SimPO：DPO 的简化变体。**

- **KTO**：只要单条标注（好/坏），数据成本砍半
- **ORPO**：把"SFT + 偏好对齐"合成一步训练，省一轮
- **SimPO**：不需要参考模型，更简单——但注意上面表里它 38.7%，**掉队明显，别碰**

**GRPO（Group Relative Policy Optimization）：能自我进化的强化学习。**

适合**答案能被程序判定对错**的场景：数学题、代码单测、格式校验、抽取字段完整性。

做法一句话：**让模型对同一个问题生成 8 个答案，答对的加分答错的减分，模型自己卷自己。** DeepSeek-R1 系列的推理能力主要就是这么来的。它不需要人标"哪个好"，只需要一个能判对错的程序——这个程序叫 reward function。

**给 Java 程序员的奖励函数**，你写起来比谁都快：

```python
def reward_extract_columns(completion: str, truth: dict) -> float:
    """字段抽取任务的奖励：全对1.0，漏字段按比例扣"""
    try:
        pred = json.loads(completion)           # 必须是合法 JSON
    except Exception:
        return -0.5                             # 格式错，重罚
    hits = sum(1 for k, v in truth.items() if pred.get(k) == v)
    return hits / len(truth)                    # 部分正确给部分分
```

**看见了吗，这就是个单元测试。** AI 圈的 RLVR（Reinforcement Learning from Verifiable Rewards，可验证奖励强化学习）听起来玄乎，落到你手里就是"给模型的输出加一个 assert"。

**两个 2026 年的实用结论**（都来自上面引的论文，能帮你省钱）：

- GRPO 的奖励曲线在 **70%~80% 个 epoch 内就饱和**，之后再训纯烧算力——**小团队就该"短促突击"，别学大厂跑满**
- **2-GRPO 用 12.5% 的采样量保留了 16-GRPO 98.1% 的效果**——穷有穷的玩法，先把采样数降下来

**蒸馏：让大佬带小弟。**

第三种"变强"的路径，逻辑完全不同：不改算法，改数据。用大模型（GPT/Claude/DeepSeek 满血）生成高质量回答或推理轨迹，拿去训你的小模型。**这是没有一手标注预算的团队唯一现实路径**——你没有的，API 有。

### 选型速查（接 17 篇决策树的最后一层）

```
有偏好对数据且没算力预算      → DPO（或 ORPO 想省一步）
只有单条好坏标注              → KTO
答案可判对错（代码/数学/格式）→ GRPO/RLVR（短训，70% epoch 停）
啥都没有，只有 API            → 蒸馏（用大模型造 SFT 数据）
都没想清楚                    → 回 18 篇继续做 SFT，别往下走
```

最后一行是本篇最重要的建议。**后训练是条单行道，下一步的投入必须有上一个工位的产出兜底。**

## Java 老司机对照室

| 后训练概念 | 你已经懂的概念 | 一句话翻译 |
|---|---|---|
| 偏好对数据 | A/B 测试标注 | {chosen, rejected} |
| 奖励模型 | 打分卡 | RLHF 要训，DPO 绕开它 |
| reward function | assert / 单测 | 你的老本行 |
| GRPO 的 group 采样 | 参数化测试的多组用例 | 一题多解，对的那个加分 |
| KL 惩罚 | 防跑偏的护栏 | 别离原模型太远 |
| 过拟合（偏好） | 死记标注偏好 | eval 集上要盯 |
| 蒸馏 | 用 Mock 重写核心 | 大佬的生成 = 你的标注 |
| 灾难性遗忘 | 改 A 坏 B | SFT 后接 DPO 要重跑 SFT 评测 |
| seed 方差 | 同样的代码两次不同结果 | 小规模实验的固有噪声 |
| SFT 先行 | 先 Mock 再上真 | OpenAI 官方也建议先 SFT 再 DPO |

## 动手实验室

### 实验 1：把用户点击数据变成 KTO 数据

你项目里可能躺着现成的偏好信号——点赞/点踩、客服质检评分、"这条回答有用/没用"按钮。它们全是金矿：

```python
import json

# 假设这是你后台导出的真实反馈（单条标注，无需成对）
feedback = [
    {"prompt": "年假怎么休", "completion": "入职满一年5天，满十年10天。", "label": True},
    {"prompt": "年假怎么休", "completion": "年假是按入职时间算的哦具体看情况～", "label": False},
    {"prompt": "报销时限", "completion": "行程结束后30天内提交。", "label": True},
    {"prompt": "报销时限", "completion": "可能是30天吧，我也不太确定", "label": False},
]

def to_kto(rows):
    """KTO 格式：prompt + completion + 二元好坏标注"""
    return [{"prompt": r["prompt"], "completion": r["completion"], "label": r["label"]}
            for r in rows]

with open("data/kto.jsonl", "w", encoding="utf-8") as f:
    for r in to_kto(feedback):
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"KTO 数据 {len(feedback)} 条（注意：无需成对构造，标注成本减半）")

# 数据健康度体检
good = sum(r["label"] for r in feedback)
bad = len(feedback) - good
print(f"好/坏样本比: {good}:{bad}")
if good == 0 or bad == 0:
    print("⚠️ 只有一类标签，模型学不到对比，去补数据吧")
```

跑完看一眼你的 `好/坏样本比`——**全是好评的数据集训不出判断力**，这是最容易被忽视的数据质量问题。

### 实验 2：写一个 Java 式的奖励函数（RLVR 的入口）

```python
import json

def reward(completion: str, truth: dict) -> float:
    """一个字段抽取任务的奖励函数——注意这写起来就是单元测试"""
    try:
        pred = json.loads(completion)          # 1. 必须是合法 JSON
    except Exception:
        return -0.5                            # 格式错：重罚（比答错更严重）
    if not isinstance(pred, dict):
        return -0.5
    hits = sum(1 for k, v in truth.items() if pred.get(k) == v)
    coverage = hits / max(len(truth), 1)
    hallucination = sum(1 for k in pred if k not in truth)  # 编造字段要重罚
    return coverage - 0.6 * hallucination                     # 见下面的排序讨论

# 四种典型输出，看奖励怎么区分它们
truth = {"请假类型": "年假", "天数": 5}
cases = [
    ('{"请假类型": "年假", "天数": 5}', "全对"),
    ('{"请假类型": "年假"}', "漏字段"),
    ('{"请假类型": "年假", "天数": 5, "工号": "9527"}', "编造字段"),
    ('本文档介绍了年假制度……', "根本不是 JSON"),
]
for out, name in cases:
    print(f"{name:<12} reward = {reward(out, truth):+.2f}")
```

实测输出是：全对 `+1.00`、漏字段 `+0.50`、**编造字段 `+0.40`**、非 JSON `-0.50`。

注意第三行的系数，这是奖励设计的核心决策：**编造一个不存在字段的惩罚，必须比漏一个字段更重**（0.6 > 0.5 的单价差距），因为漏字段系统会说"未提及"，编字段系统会理直气壮地胡说。我第一版写的 0.2 就导致了错误的排序——编造（+0.80）反而排在了漏字段（+0.50）前面，这种奖励函数训出来的模型会更爱编。**写奖励函数和写 assert 一样：边界情况比正常路径更值得你花时间。**

**四行代码，就是一个能被 GRPO 直接消费的奖励函数。** 你写的每一个"格式校验 + 字段比对"，都是 AI 圈说的 verifiable reward。

### 实验 3：蒸馏——用大模型给你的小模型造教材

```python
# distill.py —— 骨架版：真实项目把 call_teacher 换成 DeepSeek API
import json

def call_teacher(question: str) -> str:
    """调大模型生成'标准答案'。真实实现见 11 篇的 LLMClient"""
    return f"（此处应为大模型对「{question}」的高质量回答）"

QUESTIONS = [
    "年假怎么休？", "打卡迟到了怎么办？", "报销要什么发票？",
    "病假需要什么证明？", "出差住宿标准是多少？",
]

def build_distill_set(questions):
    rows = []
    for q in questions:
        answer = call_teacher(q)
        rows.append({"messages": [
            {"role": "system", "content": "你是米宝公司的客服助手，语气亲切可爱，句末常用波浪号～"},
            {"role": "user", "content": q},
            {"role": "assistant", "content": answer},
        ]})
    return rows

rows = build_distill_set(QUESTIONS)
with open("data/distill.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"蒸馏数据 {len(rows)} 条 → 这是 18 篇 SFT 的输入，链路闭合了")
```

**看到这个循环了吗：API 生成 → 18 篇的 SFT → 你的本地小模型。** 没有标注预算的团队，整条后训练链就建立在这三行拼图上。

### 实验 4：校准度——比准确率更重要的那个指标

19 篇讲的所有方法（SFT/DPO/GRPO），本质上都在解决一件事：**让模型的输出可信**。而"可信"有两个维度，很多人只看第一个：

| 维度 | 问题 | 指标 |
|---|---|---|
| 准确性 | 它说的对不对？ | 准确率 / EM / F1 |
| **校准度** | **它说自己有90% 把握的时候，是不是真的对了 90%？** | **ECE / 可靠性图** |

一个准确率 80% 但校准度很差的模型（说 100% 把握时错一半）比一个准确率 75% 但校准良好的模型**更危险**——因为你无法给它设阈值。

```python
def expected_calibration_error(bins):
    """bins: [(预测置信度, 该桶实际准确率, 样本数)]"""
    total = sum(n for _, _, n in bins)
    return sum(n / total * abs(conf - acc) for conf, acc, n in bins)

# 模型 A：说 90% 把握的时候，只有 60% 对了 → 危险
model_a = [(0.9, 0.6, 100)]
# 模型 B：说 70% 把握，恰好对了 70% → 可用
model_b = [(0.7, 0.7, 100)]
print(f"A 的 ECE = {expected_calibration_error(model_a):.2f}  ← 高，看不出它不可靠")
print(f"B 的 ECE = {expected_calibration_error(model_b):.2f}  ← 低，可设阈值")
```

**这段代码为什么重要**：LLM 说"这个答案我 90% 确定"时，那个 0.9 大概率是**编的**（09 篇说过，logprobs 都不能当概率用）。**校准度训练（RLCD 这类判别式后训练，17 篇工位 5）就是专门修这个问题的**——把模型从"我猜是 90%"训练到"我是真 90%"。

对工程的意义很直接：**你要用置信度做自动降级、人工转接、风险拦截，那校准度就是上线前的必测项**，21 篇会把它加进评测维度。

### 实验 5：成本冷静表（动手算一笔账）

```python
# 假设：要把 5000 条数据用大模型蒸馏成训练集
PRICE_IN, PRICE_OUT = 2.0, 8.0      # 元/百万 token，DeepSeek 级别
AVG_IN, AVG_OUT = 300, 200          # 平均每次请求的输入/输出 token

n = 5000
cost_in  = n * AVG_IN / 1e6 * PRICE_IN
cost_out = n * AVG_OUT / 1e6 * PRICE_OUT
print(f"蒸馏 {n} 条：输入 ¥{cost_in:.2f} + 输出 ¥{cost_out:.2f} = ¥{cost_in + cost_out:.2f}")
print(f"对比人工标注 5000 条（¥1/条）：¥{n * 1}")
print(f"→ 便宜 {n * 1 / (cost_in + cost_out):.0f} 倍，但需要你有人审环节（审 10% 抽样够用）")
```

跑完这五行，你对"蒸馏为什么是小团队的生命线"会有量级的认知。**注意最后那句：人审不能省，但可以抽样。**

## 费曼复述卡

1. 用"你不会写满分作文，但看得出哪个烂"解释：为什么偏好对齐的标注门槛比 SFT 低？
2. 为什么 oxRL 的实验说"先做好 SFT，别沉迷换算法"？把那张排序表背给你的同事听。
3. RLVR 的 reward function 和你日常写的什么代码最像？为什么说这对 Java 工程师是主场？

三题过不了，把实验 2 的奖励函数换成你项目里一个真实校验逻辑。

## 今日一句话

> SFT 打赢了所有偏好算法（54.4%），所以先做数据再做算法——而 reward function 就是单元测试，GRPO 只是让模型自己刷题。

---

下一篇：[20 · 生产级 Agent 架构：记忆、压缩与武器库](./20-agent-architecture.md)（返回 [目录](./index.md)）
