import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime, timedelta
import pytz
import io
import plotly.express as px
import time

# --- CẤU HÌNH HỆ THỐNG ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Thi Trực Tuyến Lê Quý Đôn", layout="wide", page_icon="🏫")

# --- STYLE GIAO DIỆN MÀU SẮC BẮT MẮT ---
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    .stApp { background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 100%); }
    h1 { color: #1e40af; text-align: center; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .sub-title { text-align: center; color: #1d4ed8; font-weight: bold; margin-bottom: 20px; }
    .stButton>button { 
        background-color: #2563eb; color: white; border-radius: 20px; 
        border: none; padding: 10px 25px; transition: 0.3s;
    }
    .stButton>button:hover { background-color: #1e40af; transform: scale(1.05); }
    .timer-box { 
        position: fixed; top: 50px; right: 20px; padding: 15px; 
        background: white; border-radius: 15px; border: 2px solid #2563eb;
        z-index: 1000; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- TIÊU ĐỀ TRƯỜNG ---
st.markdown("<h1>HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Trường THCS Lê Quý Đôn, phường Hà Giang 1, tỉnh Tuyên Quang</div>", unsafe_allow_html=True)

# --- CÁC HÀM HỖ TRỢ (GIỮ NGUYÊN TỪ V15) ---
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

# --- GIAO DIỆN CHÍNH ---
tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])

with tab_hs:
    ma_de_input = st.text_input("🔑 Nhập Mã đề thi:", placeholder="Nhập mã cô giáo giao...")
    
    if ma_de_input:
        res = supabase.table("exam_questions").select("*").eq("ma_de", ma_de_input).execute()
        if res.data:
            exam_info = res.data[0]
            quiz = exam_info["nội_dung_json"]
            time_limit = exam_info.get('thoi_gian_phut', 15) # Mặc định 15p nếu ko nhập
            
            if f"started_{ma_de_input}" not in st.session_state:
                st.session_state[f"started_{ma_de_input}"] = False

            if not st.session_state[f"started_{ma_de_input}"]:
                with st.form("info_form"):
                    c1, c2 = st.columns(2)
                    name = c1.text_input("👤 Họ và Tên:")
                    actual_class = c2.text_input("🏫 Lớp:")
                    st.info(f"📋 Môn: {exam_info.get('ten_lop')} | Thời gian: {time_limit} phút")
                    if st.form_submit_button("🚀 BẮT ĐẦU LÀM BÀI"):
                        if name and actual_class:
                            st.session_state[f"started_{ma_de_input}"] = True
                            st.session_state[f"st_name_{ma_de_input}"] = name
                            st.session_state[f"st_class_{ma_de_input}"] = actual_class
                            st.session_state[f"end_time_{ma_de_input}"] = time.time() + (time_limit * 60)
                            st.rerun()
                        else: st.error("Điền tên và lớp nhé!")
            else:
                # --- ĐỒNG HỒ ĐẾM NGƯỢC ---
                time_left = int(st.session_state[f"end_time_{ma_de_input}"] - time.time())
                
                if time_left > 0:
                    mins, secs = divmod(time_left, 60)
                    st.markdown(f"""
                        <div class="timer-box">
                            <small>Thời gian còn lại</small><br>
                            <span style="font-size: 25px; font-weight: bold; color: #e11d48;">
                                {mins:02d}:{secs:02d}
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Tự động refresh trang mỗi 10 giây để cập nhật đồng hồ (giảm tải server)
                    # if time_left % 10 == 0: st.empty() 

                with st.form("quiz_form"):
                    st.write(f"👨‍🎓: **{st.session_state[f'st_name_{ma_de_input}'].upper()}** | Lớp: **{st.session_state[f'st_class_{ma_de_input}']}**")
                    user_selections = {}
                    for idx, q in enumerate(quiz):
                        st.write(f"**Câu {idx+1}:** {q['question']}")
                        user_selections[idx] = st.radio("Chọn:", q['options'], index=None, key=f"q_{ma_de_input}_{idx}", label_visibility="collapsed")
                    
                    st.divider()
                    confirm = st.checkbox("Em xác nhận đã kiểm tra kỹ bài làm.")
                    submitted = st.form_submit_button("📤 NỘP BÀI THI")

                    # XỬ LÝ NỘP BÀI (DO HẾT GIỜ HOẶC BẤM NÚT)
                    if submitted or time_left <= 0:
                        if time_left <= 0: st.error("⏰ Hết giờ làm bài! Hệ thống đang tự động nộp...")
                        
                        correct_num = sum(1 for i, q in enumerate(quiz) if user_selections[i] and user_selections[i].startswith(q['answer']))
                        grade = round((correct_num / len(quiz)) * 10, 2)
                        
                        supabase.table("student_results").insert({
                            "ma_de": ma_de_input, "ho_ten": st.session_state[f"st_name_{ma_de_input}"], 
                            "lop": st.session_state[f"st_class_{ma_de_input}"], "diem": grade, 
                            "so_cau_dung": f"{correct_num}/{len(quiz)}", "lop_thi": exam_info.get('ten_lop'), 
                            "ngay_thi": exam_info.get('ngay_thi')
                        }).execute()

                        # HIỂN THỊ KẾT QUẢ (GIỮ NGUYÊN CẢM XÚC V15)
                        if grade < 5:
                            st.markdown("<h1 style='text-align: center;'>😔</h1>", unsafe_allow_html=True)
                            st.error(f"Điểm của em: {grade}. Hãy cố gắng hơn nhé!")
                        elif grade <= 7:
                            st.markdown("<h1 style='text-align: center;'>🙂</h1>", unsafe_allow_html=True)
                            st.warning(f"Điểm của em: {grade}. Em làm khá tốt!")
                        else:
                            st.balloons(); st.snow()
                            st.markdown("<h1 style='text-align: center;'>🎉 😍 🎉</h1>", unsafe_allow_html=True)
                            st.success(f"Điểm tuyệt vời: {grade}!")
                        
                        del st.session_state[f"started_{ma_de_input}"]
                        if time_left <= 0: st.stop()

                # Tự động refresh sau 1 giây để đồng hồ chạy liên tục
                if time_left > 0:
                    time.sleep(1)
                    st.rerun()

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản lý:", type="password")
    if pwd == "141983":
        col1, col2 = st.columns([1, 2.5])
        with col1:
            st.subheader("📤 Đăng đề mới")
            new_ma = st.text_input("Mã đề:")
            ten_lop = st.text_input("Môn/Lớp:")
            thoi_gian = st.number_input("Thời gian thi (phút):", min_value=1, value=15)
            ngay_thi = st.date_input("Ngày kiểm tra:")
            word_file = st.file_uploader("Tải file Word:", type=["docx"])
            if st.button("🚀 Kích hoạt"):
                if new_ma and word_file:
                    data = parse_docx_smart(word_file)
                    supabase.table("exam_questions").upsert({
                        "ma_de": new_ma, "nội_dung_json": data, 
                        "ten_lop": ten_lop, "ngay_thi": ngay_thi.strftime("%d/%m/%Y"),
                        "thoi_gian_phut": thoi_gian
                    }).execute()
                    st.success("Đã kích hoạt đề!")
