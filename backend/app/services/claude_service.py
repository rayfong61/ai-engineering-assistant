import base64
import json
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


def _extract_text(message: anthropic.types.Message) -> str:
    # message.content[0] is not always a text block -- Claude can lead with
    # a ThinkingBlock (no .text attribute), which raised a bare
    # AttributeError and surfaced as an intermittent 500 whenever it
    # happened. Filter for the actual text block instead of assuming it's
    # first, matching the pattern analyze_image already used.
    return next(block.text for block in message.content if block.type == "text")


def generate_answer(question: str, context_chunks: list[dict]) -> str:
    if not context_chunks:
        return NO_CONTEXT_ANSWER

    context_text = "\n\n".join(
        f"[來源：{c['filename']} 第{c['page']}頁]\n{c['content']}" for c in context_chunks
    )
    message = _client().messages.create(
        model=CLAUDE_MODEL,
        # 1024 was too tight for a detailed multi-section Chinese answer
        # with citations -- got observed cutting off mid-sentence.
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"檢索到的工程文件內容：\n\n{context_text}\n\n問題：{question}",
            }
        ],
    )
    return _extract_text(message)


# spec2.md section 18. Wording is verbatim from the spec -- Claude is
# instructed to use exactly these phrases (可觀察到/可能/疑似/需要人工確認),
# never an affirmative safety/compliance/quality claim. test_vision.py locks
# this text against accidental edits.
VISION_SYSTEM_PROMPT = """你是一個工程圖片分析助理。

只描述圖片中可觀察到的內容，不可以捏造未出現在圖片中的細節。

不可僅依據圖片直接宣稱：
- 結構安全
- 施工品質合格
- 法規合規
- 工程驗收通過

應使用：可觀察到 / 可能 / 疑似 / 需要人工確認。
例如：「圖片中可觀察到鋼構構件與施工設備，但僅憑圖片無法確認施工品質或結構安全性。」
"""

VISION_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis": {"type": "string"},
        "observations": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["analysis", "observations", "limitations"],
    "additionalProperties": False,
}


def analyze_image(image_bytes: bytes, media_type: str) -> dict:
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    message = _client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=VISION_SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": VISION_OUTPUT_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                    },
                    {
                        "type": "text",
                        "text": "請分析這張工程圖片：可觀察到的內容、初步分析、以及僅憑圖片無法判斷的限制。",
                    },
                ],
            }
        ],
    )
    return json.loads(_extract_text(message))


SUMMARY_SYSTEM_PROMPT = """你是一個工程會議摘要助理。

請將提供的工程文件檢索內容與圖片分析結果整理成一份簡潔的會議摘要，用於明日會議。
沿用與文件問答/圖片分析相同的安全邊界用語（可觀察到 / 可能 / 疑似 / 需要人工確認），
不得對結構安全、施工品質、法規合規、工程驗收做出未經證實的斷言。
盡量標註資訊來源（文件與頁碼）。
"""


def generate_summary(context_chunks: list[dict], vision_analyses: list[dict]) -> str:
    sections = []
    if context_chunks:
        sections.append(
            "文件檢索內容：\n"
            + "\n\n".join(f"[來源：{c['filename']} 第{c['page']}頁]\n{c['content']}" for c in context_chunks)
        )
    if vision_analyses:
        sections.append(
            "圖片分析結果：\n"
            + "\n\n".join(
                f"[{v.get('filename', '圖片')}]\n"
                f"分析：{v['analysis']}\n"
                f"觀察：{'; '.join(v['observations'])}\n"
                f"限制：{'; '.join(v['limitations'])}"
                for v in vision_analyses
            )
        )
    if not sections:
        return "目前沒有可整理的工程文件或圖片分析內容。"

    message = _client().messages.create(
        model=CLAUDE_MODEL,
        # A meeting summary synthesizing multiple document chunks + vision
        # analyses genuinely needs headroom -- this is the exact call that
        # was observed truncating mid-sentence at 1024.
        max_tokens=4096,
        system=SUMMARY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "\n\n".join(sections) + "\n\n請整理成會議摘要。"}],
    )
    return _extract_text(message)
