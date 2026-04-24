import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime
import pytz
import io
import plotly.express as px
import time

# --- KẾT NỐI HỆ THỐNG ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Hệ Thống Thi Lê Quý Đôn", layout="wide", page_icon="🏫")
ADMIN_PASSWORD = "141983" 

# --- LINK ẢNH NỀN GITHUB (Bạn hãy thay USERNAME và REPO bằng thông tin của bạn) ---
# Link chuẩn xác dựa trên GitHub của bạn
bg_img = "https://raw.githubusercontent.com/ngacvantuanhg/tracnghiemlequydonhg/main/Anhnen.png"

# --- STYLE GIAO DIỆN V20: Ô NHẬP LIỆU TRẮNG SÁNG ---
st.markdown(f"""
    <style>
    /* Hình nền toàn trang */
    .stApp {{
        background-image: url("{bg_img}");
        background-attachment: fixed;
        background-size: cover;
        background-position: center;
    }}

    /* Lớp phủ để nội dung nổi bật */
    .main {{
        background-color: rgba(255, 255, 255, 0.8);
        padding: 2rem;
        border-radius: 20px;
    }}

    /* CĂN GIỮA TIÊU ĐỀ */
    h1, .sub-title {{
        text-align: center !important;
        color: #1e3a8a !important;
    }}

    /* LÀM TRẮNG CÁC Ô NHẬP LIỆU (INPUT BOX) */
    input, div[data-baseweb="input"], div[data-baseweb="select"], .stTextArea textarea {{
        background-color: #ffffff !important;
        color: #1e3a8a !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
    }}
    
    /* Hiệu ứng khi click vào ô nhập liệu */
    input:focus {{
        border: 2px solid #1e3a8a !important;
        box-shadow: 0 0 5px rgba(30, 58, 138, 0.2) !important;
    }}

    /* Căn giữa và làm gọn Form */
    [data-testid="stForm"] {{
        background-color: rgba(255, 255, 255, 0.95);
        border: 2px solid #1e3a8a;
        border-radius: 15px;
        padding: 2rem;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        max-width: 850px;
        margin: 0 auto !important;
    }}

    /* Nút bấm Navy căn giữa */
    .stButton>button {{
        display: block;
        margin: 0 auto !important;
        background-color: #1e3a8a;
        color: white;
        border-radius: 30px;
        padding: 10px 40px;
        font-weight: bold;
    }}
    
    /* Đồng hồ đếm ngược Navy */
    .timer-box {{ 
        position: fixed; top: 20px; right: 20px; padding: 10px 20px; 
        background: #1e3a8a; color: white; border-radius: 10px;
        z-index: 1000; text-align: center;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- TIÊU ĐỀ ---
st.markdown("<h1>HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Trường THCS Lê Quý Đôn, phường Hà Giang 1, tỉnh Tuyên Quang</div>", unsafe_allow_html=True)

# --- HÀM HỖ TRỢ (Giữ nguyên) ---
def format_vietnam_time(utc_time_str):
    try:
        utc_dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        return utc_dt.astimezone(vn_tz).strftime("%H:%M:%S %d/%m/%Y")
    except: return utc_time_str

def parse_docx_smart(file):
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
        question_text = parts[0].replace("[[DUNG]]", "").replace("[[HET]]", "").strip()
        options_dict = {}
        final_answer = ""
        for j in range(1, len(parts), 2):
            label = parts[j].strip().upper()[0]
            if "[[DUNG]]" in parts[j+1]: final_answer = label
            options_dict[label] = f"{label}. {parts[j+1].replace('[[DUNG]]', '').replace('[[HET]]', '').strip()}"
        sorted_options = [options_dict[k] for k in sorted(options_dict.keys())]
        if sorted_options:
            questions.append({"question": f"{header} {question_text}", "options": sorted_options, "answer": final_answer})
    return questions

# --- PHÂN CHIA KHU VỰC ---
tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])

with tab_hs:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        ma_de_input = st.text_input("🔑 Nhập Mã đề thi cô giáo giao:", placeholder="Ví dụ: 101, 002...")
    
    if ma_de_input:
        res = supabase.table("exam_questions").select("*").eq("ma_de", ma_de_input).execute()
        if res.data:
            exam_info = res.data[0]
            quiz = exam_info["nội_dung_json"]
            time_limit = exam_info.get('thoi_gian_phut', 15)
            
            if f"started_{ma_de_input}" not in st.session_state:
                st.session_state[f"started_{ma_de_input}"] = False

            if not st.session_state[f"started_{ma_de_input}"]:
                with st.form("info_form"):
                    name = st.text_input("👤 Họ và Tên của em:")
                    actual_class = st.text_input("🏫 Lớp của em:")
                    st.info(f"📋 Môn thi: {exam_info.get('ten_lop')} | Thời gian: {time_limit} phút")
                    if st.form_submit_button("🚀 BẮT ĐẦU LÀM BÀI"):
                        if name and actual_class:
                            st.session_state[f"started_{ma_de_input}"] = True
                            st.session_state[f"st_name_{ma_de_input}"] = name
                            st.session_state[f"st_class_{ma_de_input}"] = actual_class
                            st.session_state[f"end_time_{ma_de_input}"] = time.time() + (time_limit * 60)
                            st.rerun()
                        else: st.error("❌ Em hãy điền đầy đủ thông tin nhé!")
            else:
                time_left = int(st.session_state[f"end_time_{ma_de_input}"] - time.time())
                if time_left > 0:
                    mm, ss = divmod(time_left, 60)
                    st.markdown(f'<div class="timer-box"><small>⏳ CÒN LẠI</small><br><b style="font-size:24px;">{mm:02d}:{ss:02d}</b></div>', unsafe_allow_html=True)
                
                with st.form("quiz_form"):
                    st.subheader(f"Thí sinh: {st.session_state[f'st_name_{ma_de_input}'].upper()}")
                    user_selections = {}
                    for idx, q in enumerate(quiz):
                        st.write(f"**{q['question']}**")
                        user_selections[idx] = st.radio("Chọn đáp án:", q['options'], index=None, key=f"q_{ma_de_input}_{idx}", label_visibility="collapsed")
                        st.write("")
                    
                    st.divider()
                    confirm = st.checkbox("Em xác nhận đã kiểm tra kỹ và muốn nộp bài.")
                    submitted = st.form_submit_button("📤 NỘP BÀI THI")

                    if submitted or time_left <= 0:
                        correct_num = sum(1 for i, q in enumerate(quiz) if user_selections[i] and user_selections[i].startswith(q['answer']))
                        grade = round((correct_num / len(quiz)) * 10, 2)
                        
                        supabase.table("student_results").insert({
                            "ma_de": ma_de_input, "ho_ten": st.session_state[f"st_name_{ma_de_input}"], 
                            "lop": st.session_state[f"st_class_{ma_de_input}"], "diem": grade, 
                            "so_cau_dung": f"{correct_num}/{len(quiz)}", "lop_thi": exam_info.get('ten_lop'), 
                            "ngay_thi": exam_info.get('ngay_thi')
                        }).execute()

                        st.markdown("---")
                        if grade < 5:
                            st.markdown("<h1 style='font-size:80px;'>😔</h1>", unsafe_allow_html=True)
                            st.error(f"Điểm của em: {grade}. Cố gắng hơn nhé!")
                        elif grade <= 7:
                            st.markdown("<h1 style='font-size:80px;'>🙂</h1>", unsafe_allow_html=True)
                            st.warning(f"Điểm của em: {grade}. Khá tốt!")
                        else:
                            st.balloons(); st.snow()
                            st.markdown("<h1 style='font-size:80px;'>🎉 😍 🎉</h1>", unsafe_allow_html=True)
                            st.success(f"Điểm tuyệt vời: {grade}!")
                        
                        del st.session_state[f"started_{ma_de_input}"]
                        st.stop()
                if time_left > 0:
                    time.sleep(1)
                    st.rerun()

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản lý:", type="password")
    if pwd == ADMIN_PASSWORD:
        col1, col2 = st.columns([1, 2.5])
        with col1:
            st.subheader("📤 Đăng đề")
            new_ma = st.text_input("Mã đề:")
            ten_lop = st.text_input("Môn/Lớp:")
            thoi_gian = st.number_input("Thời gian (phút):", min_value=1, value=15)
            ngay_thi = st.date_input("Ngày thi:")
            word_file = st.file_uploader("Tải Word:", type=["docx"])
            if st.button("🚀 Kích hoạt"):
                if new_ma and word_file:
                    data = parse_docx_smart(word_file)
                    supabase.table("exam_questions").upsert({"ma_de": new_ma, "nội_dung_json": data, "ten_lop": ten_lop, "ngay_thi": ngay_thi.strftime("%d/%m/%Y"), "thoi_gian_phut": thoi_gian}).execute()
                    st.success("Xong!")
        with col2:
            st.subheader("📊 Kết quả")
            all_res = supabase.table("student_results").select("*").execute()
            if all_res.data:
                df = pd.DataFrame(all_res.data)
                list_lop = sorted(df['lop_thi'].dropna().unique().tolist())
                sel_lop = st.selectbox("📌 Lớp:", list_lop)
                final_df = df[df['lop_thi'] == sel_lop].sort_values(by="ho_ten")
                st.dataframe(final_df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de"]], use_container_width=True)
