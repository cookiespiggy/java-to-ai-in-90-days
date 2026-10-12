import os, psycopg
from dotenv import load_dotenv
load_dotenv()

def init_db():
    with psycopg.connect(os.environ["PG_DSN"]) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS doc_chunks (
                    id        BIGSERIAL PRIMARY KEY,
                    source    TEXT NOT NULL,
                    content   TEXT NOT NULL,
                    embedding vector(1024) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                );
            """)
            conn.commit()
    print("doc_chunks 表就绪")

if __name__ == "__main__":
    init_db()
