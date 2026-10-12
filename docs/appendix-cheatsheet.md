# 附录 · Java-Python 对照速查表

> 全书二十篇的浓缩卡片。建议收藏本页，前三个月你会反复回来查它。

## 一、基础语法

| Java 8 | Python | 备注 |
|---|---|---|
| `System.out.println(x)` | `print(x)` | 调试用；正式用 `logging` |
| `String s = "a" + b` | `f"{b}"` | f-string 是标准答案 |
| `if (x != null)` | `if x is not None:` | 永远 `is None`，不写 `== None` |
| `a == b`（比身份） | `a == b`（比内容） | 身份比较用 `is` |
| `int i = 0;` | `i = 0` | 声明即初始化 |
| `final x = 1` | 无关键字 | Python 靠约定，常量写 `UPPER_CASE` |
| `public/private` | `_name` / `__name` | 一个下划线=私有约定，两个=名字改写 |
| `a ? b : c` | `b if a else c` | 条件表达式 |
| `switch (x) {...}` | `match x: case ...` | 3.10+，实际很少用 |
| 三目运算链 | `x or y` / `x and y` | 短路求值，返回操作数本身 |

## 二、容器与推导式

| Java 8 | Python |
|---|---|
| `new ArrayList<>()` | `[]` |
| `new HashMap<>()` | `{}` |
| `new HashSet<>()` | `set()` / `{1, 2}` |
| `List.of(a, b)` | `(a, b)` 元组 / `[a, b]` |
| `list.get(i)` | `lst[i]`（负索引从右数） |
| `list.subList(1, 3)` | `lst[1:3]`（切片） |
| `str.substring(2, 5)` | `s[2:5]` |
| `new StringBuilder(s).reverse()` | `s[::-1]` |
| `for (int i...)` | `for i, v in enumerate(lst):` |
| 两 List 配对 | `zip(a, b, strict=True)` |
| `stream().map().filter()` | `[f(x) for x in it if cond]` |
| `stream().collect(toMap())` | `{k: v for k, v in items}` |
| `stream().collect(toSet())` | `{x for x in it}` |

## 三、函数与装饰器

| Java 8 | Python |
|---|---|
| `Function<T,R> f = x -> x*2` | `f = lambda x: x * 2` |
| 匿名内部类（final 捕获） | 闭包 + `nonlocal` 声明写入 |
| Spring AOP `@Around` | `@decorator`（函数套函数） |
| `@Retryable`（Spring Retry） | `@retry(max_attempts=3)` 自己写 |
| `@Transactional` | `with transaction():`（上下文管理器） |
| `Runnable` 实例 | 函数本身 `Thread(target=fn)` |
| Lombok `@Data` | `@dataclass` |
| `record Point(int x, int y)` | `@dataclass class Point:`（默认可变） |
| `Record` 不可变 | `tuple` / `NamedTuple` / `frozen dataclass` |
| `try (var r = open())` | `with open(...) as f:` |

## 四、类型系统

| Java 8 | Python |
|---|---|
| `interface X` | `class X(Protocol):`（结构式） |
| `implements` | 什么都不写（鸭子类型） |
| `List<String>` | `list[str]`（3.9+ 小写泛型） |
| `Optional<T>` | `T | None` |
| `@Nullable String` | `str | None` |
| `Function<T,R>` | `Callable[[T], R]` |
| 泛型 `<T extends X>` | `TypeVar("T", bound=X)` |
| javac 编译期检查 | `mypy` 静态检查（命令: `uv run mypy .`） |
| `instanceof` | `isinstance(x, T)`（Pythonic 代码少用） |

## 五、并发

| Java 8 | Python |
|---|---|
| `new Thread(...)` | `threading.Thread(target=fn)` |
| `Executors.newFixedThreadPool(8)` | `ThreadPoolExecutor(max_workers=8)` |
| `synchronized(obj)` | `with threading.Lock():` |
| `volatile` | 无（asyncio 单线程无竞争） |
| `CompletableFuture.allOf(...)` | `await asyncio.gather(...)` |
| `supplyAsync(...)` | `asyncio.to_thread(fn)` / `run_in_executor` |
| NIO + Reactor | asyncio 事件循环（同构思想） |
| `ForkJoinPool` | `multiprocessing.Pool` |
| GIL 不存在（真并行） | **GIL：多线程 CPU 密集无效**，IO 有效 |
| CPU 密集 | `multiprocessing` 多进程 |
| IO 密集 | 多线程 / asyncio（AI 的主战场） |

## 六、LLM/RAG 黑话翻译

| LLM 圈黑话 | 你的旧相识 |
|---|---|
| Chat Completions 协议 | REST + JSON（OpenAI 兼容全行业） |
| token | 计费/容量单位，中文≈1~1.5字/token |
| BPE 分词 | 前缀合并，学出高频碎片表 |
| 上下文窗口 128k | 工作记忆容量（含 prompt+回答） |
| temperature / top_p | 采样随机旋钮 |
| system prompt | 全局前置配置 |
| few-shot | 模板 + 示例 |
| 幻觉 | 过拟合输出，无 ground truth |
| embedding 向量 | 语义特征向量 |
| 余弦相似度 | 检索打分器 |
| 向量库（pgvector/Milvus） | 带几何检索的索引 |
| RAG | 开卷考试（检索拼进 Prompt） |
| chunk / 分块 | 文档切片，512token+10%重叠 |
| rerank | 二段排序精排 |
| function calling | RPC：吐参数，本地执行回填 |
| ReAct / Agent | 规则引擎换成模型决策 |
| LangGraph | 轻量工作流引擎（Camunda 的 LLM 版） |
| checkpointer | 流程实例持久化 |
| LoRA 微调 | 外挂增强（AOP），教风格不教知识 |
| vLLM | 连续批处理 + 分页显存产线 |
| TTFT / TPOT | 首字延迟 / 每 token 间隔 |
| prompt injection | 检索内容劫持指令（RAG 头号威胁） |

## 七、常用命令速查

```bash
# --- 环境（本书规范） ---
uv init                      # 建项目（自动虚拟环境）
uv add requests              # 加依赖
uv add --dev ruff pytest mypy  # 加开发工具
uv run python x.py           # 在虚拟环境里跑
uv run ruff check .          # 代码检查
uv run pytest                # 测试

# --- LLM 实战 ---
export DEEPSEEK_API_KEY=sk-xxx    # key 只进环境变量
uv add openai                     # OpenAI 兼容 SDK

# --- RAG 基建 ---
docker run -d --name rag-pg -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 pgvector/pgvector:pg16
uv add "psycopg[binary]"
-- SQL: CREATE EXTENSION vector; ALTER TABLE ... ADD COLUMN embedding vector(1024);
-- 检索: ORDER BY embedding <=> %s::vector LIMIT 5

# --- 本地部署 ---
ollama serve                  # 本地模型服务（:11434）
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
vllm serve Qwen/Qwen2.5-7B-Instruct --max-model-len 8192    # Linux+GPU

# --- 微调 ---
mlx_lm.lora --model mlx-community/Qwen2.5-7B-Instruct-4bit --train --data ./data --iters 600
mlx_lm.fuse --model <基座> --adapter-path ./adapters/x --save-path ./models/fused
```

## 八、一份诚实的能力自检（转正前过一遍）

- [ ] 不看书写出生成器 + 装饰器的骨架
- [ ] 跑通过带重试和流式的 LLM Client
- [ ] pgvector 里建过库、灌过 chunk、写过检索 SQL
- [ ] 有一张 50+ 条的评测集和通过率数字
- [ ] 本地 Ollama/MLX 起过一个开源模型并用 OpenAI 协议调过
- [ ] 简历里有一段带数字的 RAG/Agent 项目经历

**六项全勾，你不再是“学过 Python 的 Java 工程师”，是 AI 应用工程师。**

---

下一篇：[附录 B · AI 信息可信度分级手册](./appendix-evidence-grading.md)（返回 [目录](./index.md)）——把书里的实验跑成你自己的项目，欢迎来仓库分享。
