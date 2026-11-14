from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor


def export_docx(revision, analysis, sources):
  document = Document()
  section = document.sections[0]
  section.page_width, section.page_height = Mm(210), Mm(297)
  section.top_margin = section.bottom_margin = Mm(25)
  section.left_margin = section.right_margin = Mm(28)
  style = document.styles["Normal"]
  style.font.name, style.font.size = "宋体", Pt(12)
  style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
  style.paragraph_format.line_spacing = 1.5
  for name, size in (("Title", 18), ("Heading 1", 14), ("Subtitle", 11)):
    heading = document.styles[name]
    heading.font.name = "宋体"
    heading.font.size = Pt(size)
    heading.font.color.rgb = RGBColor(0, 0, 0)
    heading.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "宋体")
  title = document.add_heading(revision["title"], 0)
  title.alignment = WD_ALIGN_PARAGRAPH.CENTER
  document.add_paragraph("AI 辅助草稿 · 待律师复核", "Subtitle")
  for line in revision["body"].splitlines():
    if line.strip():
      document.add_paragraph(line)
  document.add_heading("材料来源与生成记录", level=1)
  for index, source in enumerate(sources, 1):
    document.add_paragraph(f"[{index}] {source['original_name']} · 第 {source['page_no'] or 1} 页")
  document.add_paragraph(f"草稿版本：{revision['revision']}；模板：{analysis['analysis_type']} v1；"
    f"模型：{analysis['model']}；提示词版本 ID：{analysis['prompt_version_id']}；分析记录：{analysis['id']}")
  document.add_paragraph("材料指纹：" + (analysis["source_fingerprint"] or "未记录"))
  document.add_paragraph((analysis["content"] or {}).get("limitations", "仅依据召回材料生成，须人工核实。"))
  document.add_paragraph("本文件为辅助草稿，缺失信息须补齐，事实、诉讼请求、法律依据与格式须经律师复核后使用。")
  footer = section.footer.paragraphs[0]
  footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
  footer.add_run("第 ")
  field = OxmlElement("w:fldSimple")
  field.set(qn("w:instr"), "PAGE")
  footer._p.append(field)
  footer.add_run(" 页 · AI 辅助草稿")
  output = BytesIO()
  document.save(output)
  return output.getvalue()
