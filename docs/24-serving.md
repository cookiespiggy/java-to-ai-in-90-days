# 24 · 部署：vLLM 与推理优化

## 先讲给朋友听（如果你只有一分钟）

> 裸起一个模型像路边摊：一人一单，现炒现等。vLLM 像中央厨房：连续翻台（动态批处理）、剩菜冷链（KV 缓存）、显存分页（虚拟内存那套）——**而你调优时盯的指标，还是当年 JVM 调优三件套：延迟、吞吐、资源利用率。**

## 你的 Aha Moment

先看一张任何想自部署模型的团队都会撞上的墙：

```
需求：公司内网部署 Qwen-7B，支撑 200 人并发问答
裸起模型：QPS≈2，第一个字等3秒，第10人排队就开始超时
```

第一反应"加机器"——**但 GPU 显存翻倍，QPS 可能只涨 30%。** 因为瓶颈根本不在算力，在**调度**：并发请求像一堆散客，模型一个一个接待，显存大片闲着。

Aha 时刻：**LLM 推理的性能问题，70% 是“排队与内存管理”问题，不是“算得快不快”问题。** 而你，做了十年高并发的人，最熟的就是这个——

| 裸起模型的问题 | 你 Java 时代的解药 | vLLM 的同款药 |
|---|---|---|
| 请求串行接待 | 线程池复用 | Continuous Batching（连续批处理） |
| 显存被 KV 缓存占满 | 对象池 / 内存池 | PagedAttention（分页管理显存） |
| 重复计算上下文 | 结果缓存 | Prefix Caching（前缀缓存） |
| FP16 模型太大 | — | INT8/FP8 量化 |

**vLLM 的技术内核，翻成你的语言就是：动态批处理 + 分页内存 + 缓存三件套。** 全是你调优过多年的老问题的新马甲。

第二层 Aha 关于生态：**vLLM 起服务 = 一个 OpenAI 兼容端点。** 第 11 篇你写的 `LLMClient`，把 `base_url` 从 `api.deepseek.com` 换成 `http://localhost:8000/v1`，业务代码一行不改。**这就是 OpenAI 兼容协议最大的红利：推理后端对你完全透明，本地开源模型与云端 API 是无缝替补关系。**

## 不讲术语的版本：三个核心机制，说人话

**机制一 · Continuous Batching（连续批处理）：餐厅翻台术。**

传统批处理：凑满 32 个请求一起算，等最慢的那个算完，整批才吐结果——你的第 5 个请求要等 32 个里最慢的，**用户体验灾难**。

连续批处理：每一步生成结束的请求立刻离场，新请求实时补位。**永远保持满负荷翻台，没有任何人等空桌。** 吞吐提升常见 5~20 倍。

**机制二 · PagedAttention：显存界的虚拟内存。**

KV Cache（历史 token 的 K/V 缓存）是显存吞金兽，且各请求长度不可预测。传统方案给每个请求预留最大长度的连续显存——**一半以上在浪费。**

PagedAttention 把 KV Cache 切成固定大小的 block，按需分配、用完回收、不连续的块也能拼。**听起来耳熟吗？OS 的虚拟内存分页、JVM 的堆内存块管理，一个思想在三个时代各火一次。** 效果：同样显存能塞的并发请求翻几倍，直接换成 QPS。

**机制三 · 量化：精度换空间的交易。**

FP16 模型 14GB → INT8 7GB → 4bit 4GB。**质量损失从 INT8 往上几乎无感**（有评测数据支撑），4bit 开始出现可感知劣化，需你按场景权衡。私有化部署穷学生（比如你的 MacBook）的救命稻草。

## Java 老司机对照室

| vLLM 概念 | 你已经懂的概念 | 一句话翻译 |
|---|---|---|
| Continuous Batching | 线程池动态调度 | 到点下班立刻补位 |
| PagedAttention | OS 虚拟内存分页 | 显存块按需分配回收 |
| Prefix Caching | 结果缓存 | 相同前缀不重复算 |
| KV Cache | 预计算缓存 | 历史 token 的中间产物 |
| Tensor Parallelism | 分库分表 | 大模型切开放多卡 |
| TTFT | 首包延迟 | 用户等多着急的指标 |
| TPOT | 单 token 间隔 | 打字速度指标 |
| throughput | QPS/TPM | 产能指标 |
| 量化 INT8/FP8 | 有损压缩 | 空间换质量 |
| Loopback/网关限流 | Sentinel | 防打爆产线 |

下面三个指标是你以后汇报部署效果的标配，记牢：

- **TTFT（Time To First Token）**：用户按下回车到看到第一个字——**产品体验生死线**，P95 超过 2 秒就要挨骂
- **TPOT（Time Per Output Token）**：每字间隔——“打字速度”，20-40ms 体感流畅
- **吞吐（tokens/s）**：产线产能——决定你的 GPU 账单能服务多少人

## 动手实验室

### 实验 1：Mac 本地产线（Ollama 快速版 vs MLX 性能版）

Mac 上两条路，按场景选：

```bash
# 玩具级/开发调试：Ollama 三行起服务
ollama pull qwen2.5:7b-instruct-q4
ollama serve          # 默认 :11434

# 生产级（Apple Silicon 优化）：MLX 起 OpenAI 兼容服务
uv add mlx-lm
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
```

### 实验 2：业务代码零改动（第 11 篇的 base_url 换 Localhost）

```python
import os
os.environ["DEEPSEEK_API_KEY"] = "EMPTY"        # 本地服务不校验

from llm_client import LLMClient     # 直接改 RealLLMClient 的 base_url：
# base_url = "http://localhost:8080/v1"  （MLX）
# base_url = "http://localhost:11434/v1"（Ollama）
```

跑一遍第 11 篇的实验，**流式输出、多轮对话、`asyncio.gather` 并发全部原样工作。** 这就是“推理后端可替换”的实感——**面试时这句话值一个月工资。**

### 实验 3：Linux + GPU 的正式产线（vLLM）

团队真要上规模，是这套（公司 GPU 服务器/云上）：

```bash
pip install vllm

# 起 OpenAI 兼容服务，三个参数覆盖 80% 场景
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --max-model-len 8192 \          # 上下文上限，按需别贪大
  --gpu-memory-utilization 0.9 \  # 显存留给调度的比例
  --enable-prefix-caching         # 前缀缓存，system prompt 复用神器

# 压测看指标（就用它验收"扛不扛得住"）
vllm bench serve \
  --backend openai-chat \
  --model Qwen/Qwen2.5-7B-Instruct \
  --dataset-name sharegpt \
  --request-rate 10               # 每秒10个请求压过去
```

输出关注三个数：**TTFT、TPOT、throughput**，对照上面表格的生死线判断。**不会压测就上线，等于闭眼飙车。**

### 实验 4：容量规划速算（给老板的数字）

一个够用的经验公式：

```
所需并发 ≈ 峰值QPS × 平均生成时长(秒)
例：200并发客服，峰值80 QPS，平均回答5秒 → 需要并发槽位 400
7B 4bit 单卡 A10(24G)：约 30-50 并发/良好体验
→ 约需 8~13 张卡，或换更激进的配置（更长 batch、更短上下文）
```

别背数字，背方法：**测出单卡吞吐 → 乘上目标 QPS → 除出卡数。** 这套算术你给容器做容量规划时做过一百遍。

## 费曼复述卡

1. 向架构师解释 Continuous Batching 为什么是餐厅翻台，以及它比“凑批”强在哪。
2. PagedAttention 对应 OS 的哪个机制？它让显存里发生了什么变化？
3. TTFT 和 TPOT 分别影响什么体验？为什么部署验收必须看 P95 而不是平均值？

三题过不了，把实验 2 再跑一遍直到本地端点和云端 API 的切换在你眼里像换 DNS 一样自然。**最后一篇：简历与面试——把这一路工程翻译成市场语言。**

## 今日一句话

> vLLM 的内核是老药方：连续批处理是线程池，PagedAttention 是分页内存，量化是有损压缩——推理优化，优化的是排队和内存，不是算数。

---

下一篇：[25 · 简历与面试：把工程经验翻译成 AI 语言](./25-career.md)（返回 [目录](./index.md)）
