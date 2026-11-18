#!/usr/bin/env python3
"""把 Slides 类型 deck 的本地文件拼成一个 HTML，用无头 Chrome 导出 PDF，并生成缩略总览图。

用法：python3 export_pdf.py <deck 根目录> <输出.pdf> [素材对照.json]
  deck 根目录：放着 project/deck.json 的文件夹
  素材对照.json：{"<blob id>": "/本地/文件/路径"}，用来在本地显示 /_blob/<id> 的图片
"""
import json
import os
import re
import subprocess
import sys

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

BASE_CSS = (
    "@page{size:%(w)dpx 1080px;margin:0}html,body{margin:0}"
    "*{box-sizing:border-box;margin:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}"
    "h1,h2,h3,p{font-weight:400}"
    "section{position:relative;width:%(w)dpx;height:1080px;overflow:hidden;"
    "page-break-after:always;break-after:page}"
    "aside{display:none}"
    # 线上版里写在最前面的绝对定位背景垫在正文下面；本地要手动压到底层
    "section>*{position:relative;z-index:1}"
    "section>[style*='position:absolute'],section>[style*='position: absolute']{position:absolute}"
    ".glow,[data-backdrop]{position:absolute !important;z-index:0 !important}"
    ".num{position:absolute !important}"
)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    root = os.path.abspath(sys.argv[1])
    out_pdf = os.path.abspath(sys.argv[2])
    assets = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}
    proj = os.path.join(root, "project")
    deck = json.load(open(os.path.join(proj, "deck.json")))
    width = 1440 if deck.get("size") == "4:3" else 1920

    body, missing = "", []
    for sid in deck["order"]:
        path = os.path.join(proj, "slides", sid + ".html")
        if not os.path.exists(path):
            missing.append(sid)
            continue
        body += open(path).read()
    if missing:
        print("缺少页面文件：", ", ".join(missing))

    unresolved = set()

    def blob(m):
        bid = m.group(1)
        if bid in assets:
            return "file://" + os.path.abspath(assets[bid])
        unresolved.add(bid)
        return m.group(0)

    body = re.sub(r"/_blob/([0-9a-f]{32})", blob, body)
    if unresolved:
        print("本地没有对应文件的图片 %d 张，PDF 里不会显示。" % len(unresolved))

    links = "".join(
        '<link rel=stylesheet href="%s">' % f["href"]
        for f in deck.get("faces", {}).values()
        if f.get("href")
    )
    css = BASE_CSS % {"w": width}
    for shared in deck.get("format", {}).get("shared", []):
        p = os.path.join(root, shared)
        if os.path.exists(p):
            css += open(p).read()

    html_path = os.path.splitext(out_pdf)[0] + "_all.html"
    with open(html_path, "w") as f:
        f.write("<!doctype html><meta charset=utf-8>" + links + "<style>" + css + "</style>" + body)

    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=10000",
         "--no-pdf-header-footer", "--print-to-pdf=" + out_pdf, "file://" + html_path],
        stderr=subprocess.DEVNULL, check=False,
    )
    if not os.path.exists(out_pdf):
        sys.exit("没有生成 PDF，请确认已安装 Google Chrome。")

    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("已导出：", out_pdf, "（未安装 PyMuPDF，跳过总览图）")
        return
    pdf = fitz.open(out_pdf)
    n = len(pdf)
    cols = 3
    rows = (n + cols - 1) // cols
    w, h = 800, int(800 * 1080 / width)
    sheet = fitz.open()
    page = sheet.new_page(width=w * cols, height=h * rows)
    for i in range(n):
        r = fitz.Rect((i % cols) * w, (i // cols) * h, (i % cols + 1) * w, (i // cols + 1) * h)
        page.show_pdf_page(r, pdf, i)
    sheet_path = os.path.splitext(out_pdf)[0] + "_sheet.png"
    page.get_pixmap().save(sheet_path)
    print("已导出 %d 页：%s" % (n, out_pdf))
    print("总览图：", sheet_path)


if __name__ == "__main__":
    main()
