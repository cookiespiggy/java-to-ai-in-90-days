import os, re, time, psycopg
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()

emb_client = OpenAI(
    api_key=os.environ["AI_DASHSCOPE_API_KEY"],
    base_url=os.environ["EMBEDDING_BASE_URL"],
)

RAW_DOCS = {
    "员工手册-年假": "员工年假制度：入职满一年享有5天带薪年假。满十年10天。满十五年15天。年假最小申请粒度为半天，需提前一周在HR系统提交申请，由直属主管审批通过后生效。跨年度未使用的年假可结转至次年3月31日，逾期作废。",
    "员工手册-病假": "员工病假制度：需提供二级以上医院诊断证明。病假期间工资按基本工资的80%发放，全年累计不超过30天。连续病假超过15天的，需部门负责人和人力资源部共同审批。",
    "员工手册-报销": "差旅报销制度：差旅报销需在行程结束后30天内提交。发票抬头必须为公司全称，个人抬头的发票不予受理。单次报销超过5000元的需分管副总裁审批，超标部分需事前书面说明。",
    "员工手册-考勤": "考勤制度：标准工作时间为早9晚6。每月允许3次忘打卡豁免，第4次起每次扣款50元。季度全勤奖200元，当月请假超过3天不计发全勤奖。",
    "员工手册-食堂": "公司食堂：工作日提供午餐，加班到20点后可用夜宵券。周四固定有小龙虾加餐。食堂代金券每月随工资发放200元。",
    "员工手册-差旅住宿": "差旅住宿标准：一线城市每晚上限500元，二线城市350元，其他城市300元，需附酒店水单。超标部分由个人承担，特殊情况需事前审批。",
}

def chunk_by_section(source, text, max_chars=120):
    sentences = [s for s in re.split(r"(?<=。)", text) if s.strip()]
    chunks, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) > max_chars and buf:
            chunks.append(buf); buf = s
        else:
            buf += s
    if buf: chunks.append(buf)
    return [(source, c) for c in chunks]

def embed(text):
    resp = emb_client.embeddings.create(model="text-embedding-v3", input=text)
    return resp.data[0].embedding

def ingest():
    pairs = []
    for src, text in RAW_DOCS.items():
        pairs += chunk_by_section(src, text)
    t0 = time.perf_counter()
    with psycopg.connect(os.environ["PG_DSN"]) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM doc_chunks WHERE source LIKE '员工手册-%';")
        for src, chunk in pairs:
            cur.execute(
                "INSERT INTO doc_chunks (source, content, embedding) VALUES (%s, %s, %s::vector)",
                (src, chunk, str(embed(chunk))),
            )
        conn.commit()
    dt = time.perf_counter() - t0
    print(f"已入库 {len(pairs)} 个 chunk，耗时 {dt:.2f}s（均 {(dt/len(pairs)*1000):.0f}ms/chunk）")

if __name__ == "__main__":
    ingest()
