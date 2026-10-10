#!/usr/bin/env python3
"""将 Markdown 用户手册转换为 PDF（使用 fpdf2）"""
import re
from pathlib import Path
from fpdf import FPDF


class UserManualPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font('msyh', '', 'C:/Windows/Fonts/msyh.ttc', uni=True)
        self.add_font('msyh', 'B', 'C:/Windows/Fonts/msyhbd.ttc', uni=True)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_font('msyh', '', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, '异形智裁 · 用户使用说明', align='C')
            self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('msyh', '', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'第 {self.page_no()} 页', align='C')

    def chapter_title(self, title):
        self.set_font('msyh', 'B', 16)
        self.set_text_color(26, 26, 26)
        self.ln(10)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(74, 144, 226)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def section_title(self, title):
        self.set_font('msyh', 'B', 13)
        self.set_text_color(44, 62, 80)
        self.ln(8)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def body_text(self, text):
        self.set_font('msyh', '', 11)
        self.set_text_color(51, 51, 51)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def bullet_item(self, text, indent=10):
        self.set_font('msyh', '', 11)
        self.set_text_color(51, 51, 51)
        x = self.get_x()
        self.set_x(x + indent)
        self.cell(5, 6, '•')
        self.multi_cell(0, 6, text)
        self.ln(1)

    def code_block(self, text):
        self.set_fill_color(248, 248, 248)
        self.set_draw_color(224, 224, 224)
        self.set_font('msyh', '', 10)
        self.set_text_color(51, 51, 51)
        y_start = self.get_y()
        self.rect(10, y_start, 190, 20, 'DF')
        self.set_xy(15, y_start + 5)
        self.multi_cell(180, 5, text)
        self.ln(5)


def parse_markdown_to_pdf(md_file, pdf_file):
    content = md_file.read_text(encoding='utf-8')
    pdf = UserManualPDF()
    pdf.add_page()

    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # 标题
        if line.startswith('# ') and not line.startswith('## '):
            title = line[2:].strip()
            pdf.set_font('msyh', 'B', 20)
            pdf.set_text_color(26, 26, 26)
            pdf.ln(20)
            pdf.cell(0, 15, title, align='C', new_x="LMARGIN", new_y="NEXT")
            pdf.ln(10)

        elif line.startswith('## '):
            title = line[3:].strip()
            pdf.chapter_title(title)

        elif line.startswith('### '):
            title = line[4:].strip()
            pdf.section_title(title)

        # 分隔线
        elif line == '---':
            pdf.ln(5)

        # 列表项
        elif line.startswith('- ') or line.startswith('* '):
            item = line[2:].strip()
            # 处理加粗
            item = re.sub(r'\*\*(.+?)\*\*', r'\1', item)
            pdf.bullet_item(item)

        # 代码块
        elif line.startswith('```'):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i].strip())
                i += 1
            pdf.code_block('\n'.join(code_lines))

        # 普通段落
        elif line and not line.startswith('#'):
            # 处理加粗标记
            line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
            pdf.body_text(line)

        i += 1

    pdf.output(str(pdf_file))
    print(f'PDF 已生成：{pdf_file}')
    print(f'文件大小：{pdf_file.stat().st_size / 1024:.1f} KB')


def main():
    md_file = Path('docs/用户使用说明.md')
    pdf_file = Path('docs/异形智裁用户使用说明.pdf')

    if not md_file.exists():
        print(f'错误：找不到 {md_file}')
        return

    parse_markdown_to_pdf(md_file, pdf_file)


if __name__ == '__main__':
    main()
