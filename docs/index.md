---
hide:
  - navigation
  - toc
---

# Java 转 AI 的 90 天

<div class="hero" markdown>

**你不是从零开始，你只是换了一把剑。**

写给写了多年 Java 的后端工程师 · 25 篇正文 + 2 个附录 · **全部实验实测跑通**

[![GitHub](https://img.shields.io/github/stars/cookiespiggy/java-to-ai-in-90-days?style=social)](https://github.com/cookiespiggy/java-to-ai-in-90-days)
[![进阶篇 Agentic RL 123★](https://img.shields.io/badge/%F0%9F%9A%80%20进阶阅读-Agentic_RL-4285F4?style=flat-square)](https://github.com/cookiespiggy/agentic-rl)

</div>

## 这本书到底在讲什么

不是又一份"大模型全栈知识图谱"，而是回答一个具体问题：

> **Java 后端工程师，在 AI 时代到底该学什么？**

答案可能和你想的相反——**不是 SFT、不是 LoRA、不是 Transformer 数学**。

AI 应用开发的竞争壁垒，早就不是"会不会微调模型"，而是
**"能不能把不稳定的模型能力，包装成稳定的线上服务"**。

而限流、熔断、状态管理、评测、灰度、回滚——**恰好是你写了十年的老本行**。

## 90 天怎么排的

| 阶段 | 天数 | 主题 | 你会拿到什么 |
|---|---|---|---|
| **一·换武器** | Day 1-7 | Python + 并发 + 容器 | 能用 Python 写出带并发控制的工程代码 |
| **二·懂原理** | Day 8-14 | Token / Embedding / Transformer | 能向非技术同事讲明白 LLM 在干什么 |
| **三·上手做** | Day 15-25 | API 调用 → RAG → Agent | 一个真能用的企业知识库助手 |
| **四·上生产** | Day 26-90 | 评测 / 工程化 / 本地部署 / 职业转型 | 把 Demo 变成能上线的服务 |

每个阶段都以**可运行的项目**收尾，不是"读完就懂"。

## 作者是谁

一个写了多年 Java 8 的后端工程师。没有 AI 学历背景，也没有数学博士学位。

这本书的每个结论都**在作者本机跑过并留下数据**（Apple M5 Pro / 24GB / 本地模型 + pgvector）：

| 实测项 | 数据 |
|---|---|
| RAG 检索精度 | top1 **7/7**，平均 158ms |
| 本地 4B 模型问答 | 0.2~2.3 秒/问，**零 API 费用** |
| SFT 微调 0.5B | loss `6.443 → 0.777` |
| 踩过的坑 | 0.5B 输出日文乱码、oMLX 507 内存拦截、模块级读 env 拿到旧值…… |

**没有实测的结论，本书不写。**
判断一条经验值是"真跑出来的"还是"网上抄的"，见 [附录 B · 证据分级](appendix-evidence-grading.md)。

## 这本书适合谁

- :white_check_mark: 1 年以上 Java 后端经验（JDK 8 思维根深蒂固也没关系）
- :white_check_mark: 想转 AI，但被"数学""炼丹""PyTorch"劝退过
- :white_check_mark: 讨厌知识图谱式学习，要"学一个、懂一个、讲一个"的节奏
- :x: 想找"三天精通大模型"捷径的
- :arrow_forward: **已有 RAG/Agent 基础** → 直接看 [Agentic RL 教程（123★）](https://github.com/cookiespiggy/agentic-rl)

## 方法论：费曼四步

| 费曼原教旨 | 本书落地 |
|---|---|
| 选一个概念 | 一篇只讲一个概念，不贪多 |
| 讲给小学生听 | 开篇「一句话」必须零术语，有生活类比 |
| 卡住就回去 | 每篇「动手实验室」跑不通就别往下走 |
| 简化并重述 | 每篇结尾一张「复述卡」，讲不出来就是没懂 |

## 从哪开始

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } __序章__

    ---

    先搞清楚：为什么一个 Java 工程师要学 AI？

    [:octicons-arrow-right-24: 从序章开始](00-序章.md)

-   :material-school:{ .lg .middle } __直接上手__

    ---

    跳过原理，先跑通一个能用的企业知识库助手

    [:octicons-arrow-right-24: 13 篇 · RAG 实战](13-rag-project.md)

-   :material-brain:{ .lg .middle } __进阶篇__

    ---

    Agentic RL 教程 · 33 篇（123★）——本书之后的路

    [:octicons-arrow-right-24: cookiespiggy/agentic-rl](https://github.com/cookiespiggy/agentic-rl)

</div>

## 可直接跑的实战项目

全部在作者本机实测通过，不依赖本书正文也能独立使用。

| 项目 | 对应篇目 | 实测结果 |
|---|---|---|
| [`rag-project`](https://github.com/cookiespiggy/java-to-ai-in-90-days/tree/main/projects/rag-project) | 13 篇 · 企业知识库 RAG | 检索 top1 **7/7**，平均 158ms；生成层默认**本地模型**，零 API 费用 |
| [`sft-project`](https://github.com/cookiespiggy/java-to-ai-in-90-days/tree/main/projects/sft-project) | 18 篇 · SFT 微调 0.5B | loss **6.443 → 0.777**，9 条数据让 0.5B 学会客服语气 |
| [`agent-project`](https://github.com/cookiespiggy/java-to-ai-in-90-days/tree/main/projects/agent-project) | 14 篇 · 真实 ReAct Agent | 本地 4B 真调工具，护栏实测触发；含 4B 参数翻车实录 |

---

## 全部章节

完整目录见 [完整目录页](toc.md)。共 25 篇正文 + 2 个附录，约 6800 行，全部实验在作者机器实测通过。

---

**作者**：[cookiespiggy](https://github.com/cookiespiggy) · **License**：[MIT](https://github.com/cookiespiggy/java-to-ai-in-90-days/blob/main/LICENSE)
**有问题**：[开 Issue](https://github.com/cookiespiggy/java-to-ai-in-90-days/issues)