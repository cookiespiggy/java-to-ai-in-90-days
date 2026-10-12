import os, time, psycopg
from dotenv import load_dotenv
from openai import OpenAI
from llm_backend import chat, get_model_name, backend
load_dotenv()
emb = OpenAI(api_key=os.environ["AI_DASHSCOPE_API_KEY"],
             base_url=os.environ["EMBEDDING_BASE_URL"])

TOP_K = 3
THRESHOLD = 0.60  # 实测扫描得出：1.0=命中, 0.5~0.7=相关, <0.5=不相关

def embed(text):
    return emb.embeddings.create(model="text-embedding-v3", input=text).data[0].embedding

def retrieve(question):
    q = embed(question)
    lit = "[" + ",".join(f"{x:.6f}" for x in q) + "]"
    with psycopg.connect(os.environ["PG_DSN"]) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT source, content, 1 - (embedding <=> %s::vector) AS score
            FROM doc_chunks ORDER BY embedding <=> %s::vector LIMIT %s
        """, (lit, lit, TOP_K))
        return cur.fetchall()

EVAL = [("年假怎么休？","员工手册-年假"),("住院了工资怎么算？","员工手册-病假"),
        ("出差发票有什么要求？","员工手册-报销"),("迟到扣钱吗？","员工手册-考勤"),
        ("食堂有夜宵吗？","员工手册-食堂"),("出差住宿多少钱一晚？","员工手册-差旅住宿"),
        ("公司健身房几点开？",None)]

print("=== 检索评测 ===")
hit1 = 0
t_all = time.perf_counter()
for q, expect in EVAL:
    t0 = time.perf_counter()
    hits = retrieve(q)
    ms = (time.perf_counter()-t0)*1000
    top = hits[0]
    ok = (top[2] < THRESHOLD) if expect is None else (top[0] == expect)
    hit1 += ok
    print(f"  {q:<18} → {top[0]:<14} score={top[2]:.3f} {ms:5.0f}ms {'✓' if ok else '✗ 期望:'+str(expect)}")
print(f"  top1 命中率: {hit1}/{len(EVAL)}  平均检索延迟: {(time.perf_counter()-t_all)/len(EVAL)*1000:.0f}ms")

def answer(q):
    hits = [(s,c) for s,c,sc in retrieve(q) if sc >= THRESHOLD]
    if not hits: return "资料未提及"
    ctx = "\n".join(f"[{s}] {c}" for s,c in hits)
    prompt = f"你是HR制度助手。仅根据资料回答，资料没覆盖就说'资料未提及'。\n\n{ctx}\n\n问题：{q}"
    return chat(prompt)

print("\n=== 问答端到端 ===")
print(f"  后端模式: {backend()}  模型: {get_model_name()}")
for q in ["我入职三年了，年假几天？", "出差住酒店超标了能报吗？", "公司食堂周三有小龙虾吗？"]:
    t0=time.perf_counter()
    a=answer(q); ms=(time.perf_counter()-t0)*1000
    print(f"Q: {q}\nA: {a[:110]}\n   [{ms:.0f}ms]\n")
