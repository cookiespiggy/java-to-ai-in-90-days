# 完整目录

25 篇正文 + 2 个附录，共约 6800 行。
序号即依赖顺序，**跳读容易在第四阶段迷路**。


## 第一阶段 · 换语言：从 Java 8 到 Pythonic（第 01-07 篇）

| 篇 | 标题 |
|---|---|
| [01](01-python-first-touch.md) | 第一次亲密接触：删掉 30% 的仪式感 |
| [02](02-types-and-typing.md) | 类型这回事：Java 的盔甲 vs Python 的轻纱（鸭子类型、类型注解） |
| [03](03-containers.md) | 容器思维：推导式与切片，一种声明式暴力 |
| [04](04-functions.md) | 函数是一等公民：lambda、闭包与黑魔法装饰器 |
| [05](05-generators.md) | 生成器：yield 的秘密，流式输出的前世 |
| [06](06-object-model.md) | 对象模型：引用语义、可变性与上下文管理器 |
| [07](07-concurrency.md) | 并发真相：GIL 之后，线程/进程/asyncio 重排座次 |

## 第二阶段 · 懂原理：大模型到底是个什么东西（第 08-10 篇）

| 篇 | 标题 |
|---|---|
| [08](08-llm-basics.md) | 大模型是个超级自动补全，这事关尊严 |
| [09](09-token-embedding.md) | Token、Embedding、上下文窗口：三个词读懂计费单 |
| [10](10-transformer.md) | Transformer：一场关于"注意力"的注意力经济 |

## 第三阶段 · 上手：RAG 与 Agent 实战（第 11-15 篇）

| 篇 | 标题 |
|---|---|
| [11](11-first-call.md) | 第一次调用：写一个带重试的流式对话接口 |
| [12](12-rag.md) | RAG：给学霸一本开卷教材 |
| [13](13-rag-project.md) | 实战：搭一个会读公司文档的助手 |
| [14](14-agent.md) | Agent：让模型学会自己用工具 |
| [15](15-langgraph.md) | LangGraph：画一张会思考的流程图 |

## 第四阶段 · 精通检索与后训练（第 16-20 篇）

| 篇 | 标题 |
|---|---|
| [16](16-advanced-retrieval.md) | 生产级检索：混合检索、RRF、Rerank 与权重 |
| [17](17-posttraining-map.md) | 后训练地图：为什么规则兜不住泛化 |
| [18](18-sft-deep.md) | SFT 深水区：让 1.7B 小模型上岗（数据工程 + 训练诊断） |
| [19](19-alignment-rl.md) | 偏好对齐与 RLVR：DPO/KTO/GRPO 与蒸馏 |
| [20](20-agent-architecture.md) | 生产级 Agent 架构：记忆三层、压缩与武器库 |

## 第五阶段 · 成专家：工程化与部署（第 21-24 篇）

| 篇 | 标题 |
|---|---|
| [21](21-evaluation.md) | 评测：别问三个问题就说"还行" |
| [22](22-engineering.md) | Token 计费、日志与 Prompt 版本回滚（含安全账） |
| [23](23-local-inference.md) | 本地推理闭环：oMLX、unsloth 与 MLX 的三人舞 |
| [24](24-serving.md) | 部署：vLLM 与推理优化 |

## 尾声

| 篇 | 标题 |
|---|---|
| [25](25-career.md) | 简历与面试：把工程经验翻译成 AI 语言 |

## 附录

| 附录 | 内容 |
|---|---|
| [附录 A · 速查手册](appendix-cheatsheet.md) | API 调用、pgvector SQL、本地部署命令、常见报错的一页速查 |
| [附录 B · 证据分级](appendix-evidence-grading.md) | **本书特有**：如何判断一条 AI 技术说法是"实测"还是"抄的" |

---

返回 [首页](index.md) · 项目代码见 [GitHub 仓库](https://github.com/cookiespiggy/java-to-ai-in-90-days/tree/main/projects)
