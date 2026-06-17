# PDF 提取最佳实践(文字 / OCR)—— 可落地方案

> 这是**动手篇**:只讲怎么做(选什么、怎么配、贴代码),原理一律不展开。
> 想补原理(为什么 PDF 难、OCR vs VLM 的幻觉)看 → [文档解析-面试笔记](文档解析-面试笔记.md)。

---

## 0. TL;DR(先给结论,三选一)

| 你的处境 | 直接上这个 | 一句话 |
|---|---|---|
| 数据不敏感、想最快上线、量不大 | **云 API:LlamaParse** | 一个接口吃下 文字/扫描/表格,出 markdown,零运维 |
| 要自托管 / 数据不出域(企业知识库) | **Docling**(英文、CPU 友好)或 **MinerU**(中文/公式强,GPU) | 一个工具**自动分流**文字层 vs 扫描件,出 markdown |
| 已知是数字版 PDF、要最快最省 | **PyMuPDF + pymupdf4llm** | 数字版直出 markdown;表格补 pdfplumber/Camelot;文字层空了 fallback OCR |

> **核心铁律:能用一个「自动分流(文字↔OCR)」的工具,就别手搓两条路。**
> 手搓(方案 C)只在你要极致速度 / 极致控制、且 PDF 来源可控时才值得。大多数团队选方案 A 或 B 就够。

---

## 1. 选型表(一屏看完)

| 方案 | 工具 | 文字层 | 扫描件 | 表格 | 中文 | 部署 | 成本 |
|---|---|:--:|:--:|:--:|:--:|---|---|
| **A 云 API** | LlamaParse / Azure Document Intelligence | ✅ | ✅ | ✅ 强 | ✅ | 零运维 | 按页计费,量大贵 |
| **B 自托管一站式** | Docling | ✅ | ✅(内置OCR) | ✅ TableFormer | 一般 | CPU 可跑 | 硬件一次性 |
| **B 自托管一站式** | MinerU(`magic-pdf`) | ✅ | ✅ | ✅ | ✅ 强 | GPU 推荐 | 硬件一次性 |
| **C 手搓高性能** | PyMuPDF + pdfplumber + PaddleOCR | ✅ 极快 | 需自接 OCR | 需自接 | ✅(Paddle) | 本地 | 最省 |

**怎么挑一句话**:不敏感图省事 → A;要私有化、又懒得搓 → B(中文 MinerU / 英文 Docling);来源都是电子版发票/合同要极致吞吐 → C。

---

## 2. 方案 A:云 API(最快上线)

```python
# pip install llama-parse   —— 一个接口搞定 文字层 / 扫描件 / 表格
from llama_parse import LlamaParse

parser = LlamaParse(
    result_type="markdown",     # 直出 markdown,表格也转成 md/html
    language="ch_sim",          # 中文用简体;OCR 走这个语言
)
docs = parser.load_data("a.pdf")    # 自动判断文字版 / 扫描件
md = docs[0].text
```

- **Azure Document Intelligence** 同理(`prebuilt-layout` 模型,现在也能直出 markdown),合规场景常用。
- 适用:数据可出域、量不大或波动大、不想养 GPU。**敏感数据别走这条**。

---

## 3. 方案 B:自托管一站式(推荐默认)

一个工具自动分流文字层 vs 扫描件,内置 OCR + 表格识别,出 markdown。**私有化首选。**

### B-1 Docling(英文 / CPU 友好)

```python
# pip install docling
from docling.document_converter import DocumentConverter

conv = DocumentConverter()              # 默认就会:版面分析→(扫描页)OCR→表格(TableFormer)
result = conv.convert("a.pdf")
md = result.document.export_to_markdown()   # 表格已转好,扫描页已 OCR
# 要带坐标/类型的结构化输出:result.document.export_to_dict()
```

### B-2 MinerU(中文 / 公式强,建议 GPU)

```bash
# pip install magic-pdf  —— 命令行一把梭
magic-pdf -p a.pdf -o ./out -m auto     # -m auto 自动判断文字版/OCR
# 产出:out/a.md(markdown) + out/a_content_list.json(带 bbox 坐标,溯源用)
```

- 中文 PDF、含公式/复杂版面 → MinerU 通常比 Docling 准。
- CPU 也能跑,但慢;有消费级 GPU(几 GB)就顺。

---

## 4. 方案 C:手搓高性能管线(数字版 PDF + OCR fallback)

来源可控、要极致速度时用。**核心是自动分流 + 兜底**,别只走一条路。

```python
# pip install pymupdf pymupdf4llm pdfplumber paddleocr
import fitz, pymupdf4llm

def extract_pdf(path: str) -> str:
    doc = fitz.open(path)
    sample = "".join(doc[i].get_text() for i in range(min(3, len(doc))))

    # ① 文字层空/几乎空 → 扫描件,走 OCR
    if len(sample.strip()) < 50:
        return ocr_pipeline(path)
    # ② 暗坑:文字层乱码(中文字体子集/编码坏)→ 也当扫描件
    if is_garbled(sample):
        return ocr_pipeline(path)
    # ③ 正常数字版:最快最省,直出 markdown(表格也一起转)
    return pymupdf4llm.to_markdown(path)


def is_garbled(text: str, thresh: float = 0.3) -> bool:
    """非常用字符占比过高 → 判为乱码。"""
    if not text:
        return False
    bad = sum(1 for c in text if not (
        c.isalnum() or c.isspace() or
        "一" <= c <= "鿿" or          # 常用中文
        c in "，。、；:!?()【】《》-—…%/.,;:!?\"'"
    ))
    return bad / len(text) > thresh


def ocr_pipeline(path: str) -> str:
    """扫描件兜底:简单场景 PaddleOCR;要版面+表格直接换 Docling/MinerU。"""
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(lang="ch")
    out = []
    doc = fitz.open(path)
    for page in doc:
        pix = page.get_pixmap(dpi=200)        # 渲染成图;扫描件 200–300 dpi 够
        png = pix.tobytes("png")
        for line in ocr.ocr(png)[0]:
            text, conf = line[1]
            if conf < 0.6:                    # 低置信度标记出来,别静默吞掉
                text = f"[?{conf:.2f}] {text}"
            out.append(text)
    return "\n".join(out)
```

**表格单独抽**(数字版,`pymupdf4llm` 拿不准时):

```python
import pdfplumber
with pdfplumber.open(path) as pdf:
    for page in pdf.pages:
        for tbl in page.extract_tables():     # list[list[str]],空格是 None
            md = to_markdown(tbl)              # 简单表转 md;合并单元格转 html
# 有完整框线用 Camelot flavor="lattice";无框线 "stream";再难上 Docling 的 TableFormer
```

---

## 5. 落地参数清单(默认值,照抄就行)

| 环节 | 默认 | 说明 |
|---|---|---|
| OCR 渲染 dpi | **200–300** | 低了认不准,高了慢、内存爆 |
| OCR 语言 | 中文 `lang="ch"` / LlamaParse `ch_sim` | 选错语言中文直接翻车 |
| OCR 置信度阈值 | **0.6** | 低于它**标记**(`[?0.42]`)别静默吞,留人工/复核 |
| 文字层判空阈值 | 抽样前 3 页,非空字符 **< 50** 判扫描件 | 整篇判太慢 |
| 乱码判定 | 非常用字符占比 **> 0.3** | 防「有文字层但乱码」的暗坑 |
| chunk 大小 | **512–1024 token**,overlap **10–15%** | 表格不算在内 |
| **表格分块** | 整张表**留同一个 chunk**,前面补 caption | 跨 chunk 切表 = 报废 |
| 表格 embedding | 另用 LLM 生成**一句表格摘要**去检索 | 裸 markdown 表召回差 |
| metadata | `source` / `page` / 元素类型 / 必要时 bbox | 给检索过滤 + 引用溯源 |

---

## 6. 最终输出格式总结(PDF 抽取的终点长什么样)

不管前面走 PyMuPDF / Docling / MinerU / LlamaParse 哪条路,**抽出来的数据最终都落成下面三层**,这就是你交给 LLM / RAG 的东西:

**① 正文 → Markdown 文本**
标题层级(`#`/`##`)、列表、段落用 markdown 标记保留,是喂 LLM 的主体。

**② 表格 → 内嵌正文 或 旁路,按复杂度选格式**

| 表长什么样 | 输出格式 | 原因 |
|---|---|---|
| 简单规整 | **Markdown 表**(内嵌正文) | token 省、行列关系天然 |
| 合并单元格 / 多级表头 / 单元格多行 | **HTML 表**(`rowspan/colspan`) | markdown 表达不了这些 |
| 要入库 / 程序处理 / 保留坐标 | **JSON**(旁路,可带 bbox) | 结构化、可程序消费 |

> 表格「原始二维数组 → markdown/html/json」的转换细节见 [面试笔记 §3.3](文档解析-面试笔记.md),此处不重复。

**③ 整体进 RAG → 切成 `Document` 列表**
最终形态是若干 chunk,每个 = 一段 markdown + 元数据,**整张表留在同一个 chunk**:

```python
Document(
    page_content="## 2024 营收\n\n| 季度 | 营收 |\n| --- | --- |\n| Q1 | 100 |",
    metadata={"source": "a.pdf", "page": 3, "type": "table"},
)
```

**一眼记牢**:正文是 **Markdown**,表格内嵌 **Markdown / HTML**(复杂表才 HTML),整体是带 `metadata` 的 **`Document` chunk 列表**。

---

## 7. 验收 checklist(上线前自查)

- [ ] **文字版和扫描件都喂过**:扫描件没走 fallback = 漏读半本。
- [ ] **中文乱码 PDF 测过**:有文字层但乱码的,有没有被 `is_garbled` 兜到 OCR。
- [ ] **表格没被 chunk 切断**:抽查几张表,确认整张在一个 chunk 里。
- [ ] **跨页表**:同一张表跨页的,有没有缝合(或至少没被当两张乱表)。
- [ ] **低置信度 OCR 有标记**:金融/医疗/法律场景尤其不能静默吞错。
- [ ] **metadata 齐**:能从答案反查到 `source` + `page`。

---

> **一句话总览**:大多数团队——不敏感用 **LlamaParse**,要私有化用 **MinerU(中文)/ Docling(英文)**;只有「来源全是电子版、要极致吞吐」才值得手搓 **PyMuPDF + OCR fallback**。剩下的事都在第 5 节那张参数表里。
