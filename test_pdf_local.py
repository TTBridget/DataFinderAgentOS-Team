import os, re, time, datetime
from app.models.chat import ChatSessionRepository, ChatMessageRepository

session_id = 48
session = ChatSessionRepository.get_by_id(session_id)
print("session", session)
messages = ChatMessageRepository.get_session_messages(session_id, session["user_id"])
print("messages", len(messages))

font_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "app", "static", "fonts"))
bundled_fonts = [
    os.path.join(font_dir, "NotoSansCJKsc-Regular.ttf"),
    os.path.join(font_dir, "NotoSansCJKsc-Regular.otf"),
]
windows_font_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
system_fonts = [
    os.path.join(windows_font_dir, "simhei.ttf"),
    os.path.join(windows_font_dir, "msyh.ttc"),
    os.path.join(windows_font_dir, "simsun.ttc"),
]
font_path = next((p for p in bundled_fonts + system_fonts if os.path.exists(p)), None)
print("font_path", font_path)

from fpdf import FPDF
pdf = FPDF()
pdf.add_page()
pdf.add_font("DataFinderCJK", "", font_path)
pdf.set_font("DataFinderCJK", "", 12)

pdf.set_font_size(16)
pdf.cell(0, 10, txt=f"对话记录：{session['title'] or '未命名对话'}", ln=True, align="C")

for msg in messages:
    role_label = "用户" if msg["role"] == "user" else "AI"
    pdf.set_font_size(10)
    pdf.set_text_color(22, 93, 255)
    pdf.cell(0, 6, txt=f"[{role_label}] {msg['created_at']}", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font_size(11)
    content = msg["content"] or ""
    content = re.sub(r'```[\s\S]*?```', '[代码块]', content)
    content = re.sub(r'`([^`]+)`', r'\1', content)
    content = content.replace("**", "").replace("*", "")
    for line in content.split("\n"):
        pdf.multi_cell(0, 6, txt=line)
    pdf.ln(3)

out = f"test_export_{session_id}.pdf"
with open(out, "wb") as f:
    f.write(pdf.output(dest="S"))
print("saved", out, os.path.getsize(out))
