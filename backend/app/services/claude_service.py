from functools import lru_cache

import anthropic

from app.core.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

# spec2.md section 16. Grounding is enforced by the fallback sentence being
# spelled out verbatim -- Claude is instructed to use it exactly, not
# paraphrase it, so the frontend/tests can match on it reliably.
NO_CONTEXT_ANSWER = "目前提供的工程文件中沒有足夠資訊回答此問題。"

SYSTEM_PROMPT = f"""你是一個工程知識助理。

只能根據提供的檢索內容回答問題，不可以捏造工程資訊。

如果提供的內容不足以回答問題，請完全依照以下文字回覆，不要改寫：
「{NO_CONTEXT_ANSWER}」

回答時盡量標註資訊來源（文件與頁碼）。

不可以對以下事項做出未經證實的斷言：
- 結構安全性
- 施工品質
- 法規合規性
- 工程驗收
- 檢驗合格與否
"""


@lru_cache
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def generate_answer(question: str, context_chunks: list[dict]) -> str:
    if not context_chunks:
        return NO_CONTEXT_ANSWER

    context_text = "\n\n".join(
        f"[來源：{c['filename']} 第{c['page']}頁]\n{c['content']}" for c in context_chunks
    )
    message = _client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"檢索到的工程文件內容：\n\n{context_text}\n\n問題：{question}",
            }
        ],
    )
    return message.content[0].text
