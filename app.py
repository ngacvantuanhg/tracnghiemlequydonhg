import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime
import pytz
import io
import time

# --- KẾT NỐI HỆ THỐNG ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Hệ Thống Thi Lê Quý Đôn", layout="wide", page_icon="🏫")
ADMIN_PASSWORD = "141983" 

bg_img = "https://raw.githubusercontent.com/ngacvantuanhg/tracnghiemlequydonhg/main/Anhnen.png"

# --- STYLE GIAO DIỆN V44 ---
st.markdown(f"""
    <style>
    .stApp {{ background-image: url("{bg_img}"); background-attachment: fixed; background-size: cover; background-position: center; }}
    .main {{ background-color: rgba(255, 255, 255, 0.85); padding: 2rem; border-radius: 20px; }}
    h1, .sub-title {{ text-align: center !important; color: #1e3a8a !important; }}
    
    div[data-baseweb="input"], div[data-baseweb="select"] {{
        background-color: #ffffff !important; border: 2px solid #cbd5e1 !important; border-radius: 8px !important;
    }}
    
    [data-testid="stForm"] {{
        background-color: rgba(255, 255, 255, 0.95); border: 2px solid #1e3a8a;
        border-radius: 15px; padding: 2rem; max-width: 850px; margin: 0 auto !important;
    }}

    /* VÙNG HIỂN THỊ PHIẾU TRÊN WEB */
    .printable-content {{
        background-color: white !important;
        padding: 30px !important;
        border: 2px solid #1e3a8a !important;
        color: black !important;
        border-radius: 10px;
        margin-bottom: 20px;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- HÀM HỖ TRỢ ---
def format_vietnam_time(utc_time_str):
    try:
        utc_dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        return utc_dt.astimezone(vn_tz).strftime("%H:%M:%S %d/%m/%Y")
    except: return utc_time_str

def parse_docx_simple(file):
    doc = Document(file)
    questions = []
    full_text_with_marks = ""
    for para in doc.paragraphs:
        para_text = "".join([f" [[DUNG]]{r.text}[[HET]] " if r.font.color and str(r.font.color.rgb) == "FF0000" else r.text for r in para.runs])
        full_text_with_marks += para_text + "\n"
    q_blocks = re.split(r'(?i)(Câu\s+\d+[:.])', full_text_with_marks)
    for i in range(1, len(q_blocks), 2):
        header = q_blocks[i].strip()
        parts = re.split(r'(?i)\b([A-D]\s*[:.])', q_blocks[i+1])
        if len(parts) > 1:
            ans_key = ""
            for j in range(1, len(parts), 2):
                if "[[DUNG]]" in parts[j+1]: ans_key = parts[j].strip().upper()[0]
            questions.append({"question": header, "answer_key": ans_key})
    return questions

# --- TIÊU ĐỀ ---
st.markdown("<h1>HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])

# ... (Phần tab_hs giữ nguyên như bản V43) ...

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản trị:", type="password")
    if pwd == ADMIN_PASSWORD:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("📤 ĐĂNG ĐỀ")
            n_ma = st.text_input("Mã đề:"); t_mon = st.text_input("Môn học:"); t_lop = st.text_input("Lớp:"); f_word = st.file_uploader("File Word:", type=["docx"])
            if st.button("🚀 Kích hoạt đề"):
                if n_ma and t_mon and f_word:
                    d_js = parse_docx_simple(f_word)
                    supabase.table("exam_questions").upsert({"ma_de": n_ma, "nội_dung_json": d_js, "ten_mon": t_mon.strip(), "ten_lop": t_lop.strip(), "ngay_thi": datetime.now().strftime("%d/%m/%Y")}).execute()
                    st.success("Đã đăng!"); st.rerun()

        with c2:
            st.subheader("📊 KẾT QUẢ VÀ IN PHIẾU")
            r_all = supabase.table("student_results").select("*").execute()
            if r_all.data:
                df = pd.DataFrame(r_all.data).sort_values(by="ho_ten")
                df['created_at_vn'] = df['created_at'].apply(format_vietnam_time)
                st.dataframe(df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de"]], use_container_width=True)
                
                s_hs = st.selectbox("🖨️ Chọn học sinh để in phiếu:", ["-- Chọn --"] + df['ho_ten'].tolist())
                if s_hs != "-- Chọn --":
                    hs = df[df['ho_ten'] == s_hs].iloc[0]
                    
                    # NỘI DUNG PHIẾU
                    html_content = f"""
                    <div class='printable-content'>
                        <h2 style='text-align: center; color: #1e3a8a;'>PHIẾU MINH CHỨNG KẾT QUẢ KIỂM TRA</h2>
                        <p style='text-align: center;'>Trường THCS Lê Quý Đôn - Tuyên Quang</p>
                        <hr>
                        <table style='width: 100%; font-size: 1.1em; line-height: 2.2em;'>
                            <tr><td width='40%'><b>Họ và tên học sinh:</b></td><td>{hs['ho_ten'].upper()}</td></tr>
                            <tr><td><b>Lớp:</b></td><td>{hs['lop']}</td></tr>
                            <tr><td><b>Môn kiểm tra:</b></td><td>{hs['lop_thi']}</td></tr>
                            <tr><td><b>Ngày nộp bài:</b></td><td>{hs['created_at_vn']}</td></tr>
                            <tr><td><b>Kết quả:</b></td><td><b>{hs['diem']} điểm ({hs['so_cau_dung']})</b></td></tr>
                        </table>
                        <br><br>
                        <table style='width: 100%; text-align: center;'>
                            <tr>
                                <td><b>GIÁO VIÊN</b><br><br><br>(Ký tên)</td>
                                <td><b>HỌC SINH</b><br><br><br>(Ký tên)</td>
                            </tr>
                        </table>
                    </div>
                    """
                    st.markdown(html_content, unsafe_allow_html=True)
                    
                    # TUYỆT CHIÊU JAVASCRIPT ĐỂ MỞ CỬA SỔ IN RIÊNG BIỆT
                    print_js = f"""
                    <script>
                    function printReport() {{
                        var printContents = document.getElementsByClassName('printable-content')[0].innerHTML;
                        var originalContents = document.body.innerHTML;
                        var printWindow = window.open('', '', 'height=600,width=800');
                        printWindow.document.write('<html><head><title>In Phieu Minh Chung</title>');
                        printWindow.document.write('<style>body{{font-family:Arial;padding:40px;}} hr{{border:1px solid #1e3a8a;}} table{{width:100%;line-height:2.5em;}}</style>');
                        printWindow.document.write('</head><body>');
                        printWindow.document.write(printContents);
                        printWindow.document.write('</body></html>');
                        printWindow.document.close();
                        printWindow.print();
                    }}
                    </script>
                    <div style="text-align: center;">
                        <button onclick="printReport()" style="background-color: #1e3a8a; color: white; padding: 12px 40px; border-radius: 25px; border: none; cursor: pointer; font-weight: bold; font-size: 1.1em;">
                            🚀 NHẤN VÀO ĐÂY ĐỂ IN PHIẾU NGAY
                        </button>
                    </div>
                    """
                    st.components.v1.html(print_js, height=100)
