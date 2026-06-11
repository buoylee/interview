#!/usr/bin/env python3
"""
prepare_kb_data.py
------------------
Builds a small SFT (Supervised Fine-Tuning) dataset from the MVP Agentic-RAG
sample_docs corpus.  No GPU, no LLM — runs with stdlib + pathlib only.

Output: ai/fine-tuning/data/kb_sft.jsonl

Each line is a JSON object:
  {
    "messages": [
      {"role": "system",    "content": "<system prompt>"},
      {"role": "user",      "content": "<question>"},
      {"role": "assistant", "content": "<answer with citation>"}
    ],
    "_meta": {"type": "kb" | "refusal", "source_file": "<filename>", "section": "<heading>"}
  }
"""

import json
import pathlib
import re
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
THIS_DIR = pathlib.Path(__file__).parent
SAMPLE_DOCS_DIR = THIS_DIR.parent / "langchain" / "mvp-agentic-rag" / "sample_docs"
OUTPUT_FILE = THIS_DIR / "data" / "kb_sft.jsonl"

SYSTEM_PROMPT = (
    "你是企业知识库助手，回答必须基于知识库内容并注明来源文件，"
    "依据不足时明确说明。"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_sections(md_text: str) -> list[dict]:
    """
    Split a Markdown file into sections by ## headings.
    Returns a list of {"heading": str, "body": str}.
    The body includes all text until the next ## heading.
    The intro text before the first ## is discarded (document-level only).
    """
    sections = []
    # Split on lines that start with exactly "## " (level-2 headings)
    parts = re.split(r'(?m)^## (.+)$', md_text)
    # parts = [intro, heading1, body1, heading2, body2, ...]
    if len(parts) < 3:
        return sections
    # Skip parts[0] (intro paragraph before first ##)
    for i in range(1, len(parts) - 1, 2):
        heading = parts[i].strip()
        body = parts[i + 1].strip()
        if body:
            sections.append({"heading": heading, "body": body})
    return sections


def build_kb_samples(heading: str, body: str, filename: str) -> list[dict]:
    """
    Generate 2-3 chat-format samples for one ## section.
    Questions use What/How/Compare templates — fully deterministic.
    Answer is grounded directly in `body` text.
    """
    samples = []

    def make_sample(question: str, answer: str) -> dict:
        return {
            "messages": [
                {"role": "system",    "content": SYSTEM_PROMPT},
                {"role": "user",      "content": question},
                {"role": "assistant", "content": answer},
            ],
            "_meta": {"type": "kb", "source_file": filename, "section": heading},
        }

    # --- Template 1: "什么是 / What is" ----------------------------------------
    q1 = f"什么是 {heading}？请解释其核心概念。"
    # Take the first 2 sentences of body as the core answer
    sentences = re.split(r'(?<=[。？！.!?])\s*', body)
    core = " ".join(s.strip() for s in sentences[:3] if s.strip())
    a1 = f"{core}\n\n（来源：{filename}，章节：{heading}）"
    samples.append(make_sample(q1, a1))

    # --- Template 2: "如何 / How does" ----------------------------------------
    # Pick the first sentence that contains a verb keyword
    verb_keywords = ["通过", "使用", "采用", "通常", "主要", "supports", "allows",
                     "provides", "uses", "enables", "builds", "runs", "creates"]
    how_sentence = ""
    for s in sentences:
        if any(kw in s for kw in verb_keywords):
            how_sentence = s.strip()
            break
    if not how_sentence:
        how_sentence = sentences[0].strip() if sentences else body[:200]

    q2 = f"{heading} 是如何工作的？有哪些关键机制？"
    a2 = (
        f"根据知识库，{heading} 的工作机制如下：\n\n{how_sentence}\n\n"
        f"详细内容：{body[:400]}{'...' if len(body) > 400 else ''}\n\n"
        f"（来源：{filename}，章节：{heading}）"
    )
    samples.append(make_sample(q2, a2))

    # --- Template 3: "对比 / Compare" (only when body has comparison keywords) ----
    compare_keywords = ["vs", "versus", "compared", "difference", "trade-off",
                        "对比", "区别", "不同", "优缺点", "vs.", "比较"]
    has_compare = any(kw.lower() in body.lower() for kw in compare_keywords)
    if has_compare:
        q3 = f"在 {heading} 中，有哪些选项或方案需要对比取舍？"
        # Find the paragraph most likely to contain comparison content
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        compare_para = body[:500]
        for para in paragraphs:
            if any(kw.lower() in para.lower() for kw in compare_keywords):
                compare_para = para
                break
        a3 = (
            f"在 {heading} 领域，知识库描述了以下对比或取舍：\n\n{compare_para}"
            f"{'...' if len(compare_para) >= 500 else ''}\n\n"
            f"（来源：{filename}，章节：{heading}）"
        )
        samples.append(make_sample(q3, a3))

    return samples


# ---------------------------------------------------------------------------
# Refusal samples
# ---------------------------------------------------------------------------

REFUSAL_SAMPLES = [
    {
        "user": "明天东京的天气怎么样？",
        "assistant": (
            "依据不足，知识库中没有天气预报相关内容。"
            "此问题超出知识库范围，无法基于现有文档作答。"
        ),
    },
    {
        "user": "公司首席执行官的家庭住址是什么？",
        "assistant": (
            "依据不足，知识库中不包含任何人员个人信息。"
            "如需了解公司架构，请查阅公司官方目录。"
        ),
    },
    {
        "user": "苹果公司现在的股价是多少？",
        "assistant": (
            "依据不足，知识库仅涵盖技术文档（Docker、Kubernetes、"
            "PostgreSQL、Redis），不包含实时金融数据。"
        ),
    },
    {
        "user": "公司内部关于 AI 在生产环境使用的政策文件说了什么？",
        "assistant": (
            "依据不足，知识库中没有该公司内部政策文件。"
            "请联系相关负责人或查阅内网文档。"
        ),
    },
    {
        "user": "高级工程师的薪资范围是多少？",
        "assistant": (
            "依据不足，知识库不包含薪酬相关信息。"
            "此类问题应向 HR 部门咨询。"
        ),
    },
    {
        "user": "昨天发生了哪些重大新闻事件？",
        "assistant": (
            "依据不足，知识库仅包含技术文档，不涵盖新闻资讯。"
            "建议查阅新闻网站获取实时信息。"
        ),
    },
]


def build_refusal_samples() -> list[dict]:
    samples = []
    for item in REFUSAL_SAMPLES:
        samples.append({
            "messages": [
                {"role": "system",    "content": SYSTEM_PROMPT},
                {"role": "user",      "content": item["user"]},
                {"role": "assistant", "content": item["assistant"]},
            ],
            "_meta": {"type": "refusal", "source_file": None, "section": None},
        })
    return samples


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not SAMPLE_DOCS_DIR.exists():
        print(f"ERROR: sample_docs not found at {SAMPLE_DOCS_DIR}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    kb_samples: list[dict] = []
    refusal_samples: list[dict] = build_refusal_samples()

    doc_files = sorted(SAMPLE_DOCS_DIR.glob("*.md"))
    print(f"Found {len(doc_files)} source docs: {[f.name for f in doc_files]}")

    for doc_path in doc_files:
        md_text = doc_path.read_text(encoding="utf-8")
        sections = parse_sections(md_text)
        print(f"  {doc_path.name}: {len(sections)} sections")
        for sec in sections:
            new_samples = build_kb_samples(sec["heading"], sec["body"], doc_path.name)
            kb_samples.extend(new_samples)
            print(f"    [{sec['heading'][:50]}] → {len(new_samples)} samples")

    all_samples = kb_samples + refusal_samples

    with OUTPUT_FILE.open("w", encoding="utf-8") as fh:
        for sample in all_samples:
            fh.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print()
    print("=" * 60)
    print(f"Output: {OUTPUT_FILE}")
    print(f"Total samples:    {len(all_samples)}")
    print(f"  KB samples:     {len(kb_samples)}")
    print(f"  Refusal samples:{len(refusal_samples)}")
    print()

    # Sanity-check: print first kb sample and first refusal sample
    print("--- Sample 1 (KB) ---")
    s = kb_samples[0]
    print(f"  source: {s['_meta']['source_file']}  section: {s['_meta']['section']}")
    print(f"  user:      {s['messages'][1]['content']}")
    print(f"  assistant: {s['messages'][2]['content'][:200]}...")
    print()
    print("--- Sample (Refusal) ---")
    r = refusal_samples[0]
    print(f"  user:      {r['messages'][1]['content']}")
    print(f"  assistant: {r['messages'][2]['content']}")


if __name__ == "__main__":
    main()
