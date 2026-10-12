"""LLM 后端：云端 API / 本地 oMLX 双模式，一行环境变量切换。

核心事实：两者都是 OpenAI 兼容协议，所以业务代码零改动（23 篇）。
    切云端：LLM_BACKEND=api
    切本地：LLM_BACKEND=local（需先 omlx serve 起服务）
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # 必须在这里加载：模块被 import 的时机早于调用方的 load_dotenv()


def backend() -> str:
    """惰性读取：api | local（默认 local——零成本、数据不出内网）"""
    return os.environ.get("LLM_BACKEND", "local")


def _client():
    if backend() == "local":
        return OpenAI(
            api_key=os.environ.get("LOCAL_KEY", "EMPTY"),
            base_url=os.environ.get("LOCAL_BASE_URL", "http://127.0.0.1:8000/v1"),
        )
    return OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )


def get_model_name() -> str:
    """本地必须显式指定模型名（= 服务端暴露的模型 id）；云端固定 deepseek-chat"""
    if backend() == "local":
        return os.environ.get("LOCAL_MODEL", "Qwen2.5-0.5B")
    return "deepseek-chat"


def chat(prompt: str, max_tokens: int = 500) -> str:
    """统一的问答入口——调用方不需要知道背后是云还是本地"""
    resp = _client().chat.completions.create(
        model=get_model_name(),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return resp.choices[0].message.content


def health() -> str:
    """连通性自检：切了模式先跑这个"""
    try:
        models = _client().models.list()
        ids = [m.id for m in models.data]
        return f"✅ 后端={backend()} 可用，模型: {ids}"
    except Exception as e:
        return f"❌ 后端={backend()} 连不上: {type(e).__name__}: {e}"


if __name__ == "__main__":
    print(health())