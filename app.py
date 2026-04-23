import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime
import pytz # Thư viện xử lý múi giờ

# --- KẾT NỐI HỆ THỐNG ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Hệ Thống Thi Online Lê Quý Đôn", layout="wide", page_icon="🏫")

ADMIN_PASSWORD = "141983" 

# --- HÀM CHUYỂN ĐỔI GIỜ VIỆT NAM ---
def format_vietnam_time(utc_time_str):
    try:
        # Chuyển chuỗi thời gian từ Supabase thành đối tượng datetime
        utc_dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        # Chuyển sang múi giờ Việt Nam
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        vn_dt = utc_dt.astimezone(vn_tz)
        return vn_dt.strftime("%H:%M:%S %d/%m/%Y")
    except:
        return utc_time_str

# --- BỘ MÁY QUÉT ĐỀ THI ---
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

# --- GIAO DIỆN ---
st.title("🏫 Hệ Thống Thi Trắc Nghiệm Trực Tuyến")

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN LÝ GIÁO VIÊN"])

with tab_hs:
    ma_de_thi = st.text_input("🔑 Nhập Mã đề thi:")
    if ma_de_thi:
        res = supabase.table("exam_questions").select("nội_dung_json").eq("ma_de", ma_de_thi).execute()
        if res.data:
            quiz = res.data[0]["nội_dung_json"]
            with st.form("quiz_form"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Họ và Tên học sinh:")
                class_name = c2.text_input("Lớp:")
                user_selections = {idx: st.radio(f"**{q['question']}**", q['options'], index=None, key=f"q_{idx}") for idx, q in enumerate(quiz)}
                
                if st.form_submit_button("NỘP BÀI THI", use_container_width=True):
                    if name and class_name:
                        correct_num = sum(1 for i, q in enumerate(quiz) if user_selections[i] and user_selections[i].startswith(q['answer']))
                        grade = round((correct_num / len(quiz)) * 10, 2)
                        supabase.table("student_results").insert({"ma_de": ma_de_thi, "ho_ten": name, "lop": class_name, "diem": grade}).execute()
                        st.balloons()
                        st.success(f"Kết quả của {name.upper()}: {grade} điểm (Đúng {correct_num}/{len(quiz)} câu)")
                    else: st.error("⚠️ Điền tên và lớp nhé!")
        else: st.warning("Mã đề không tồn tại!")

with tab_gv:
    pwd = st.text_input("🔐 Nhập mật khẩu quản lý:", type="password")
    if pwd == ADMIN_PASSWORD:
        st.success("Chào cô giáo!")
        col1, col2 = st.columns([1, 1.5])
        with col1:
            new_ma = st.text_input("Mã đề:")
            word_file = st.file_uploader("Tải đề Word:", type=["docx"])
            if st.button("Kích hoạt đề"):
                if new_ma and word_file:
                    supabase.table("exam_questions").upsert({"ma_de": new_ma, "nội_dung_json": parse_docx_smart(word_file)}).execute()
                    st.success("Đã tải xong!")
        with col2:
            st.subheader("📊 Bảng điểm (Giờ Việt Nam)")
            all_data = supabase.table("student_results").select("*").execute()
            if all_data.data:
                df = pd.DataFrame(all_data.data)
                # CHUYỂN ĐỔI GIỜ TRƯỚC KHI HIỂN THỊ
                df['created_at'] = df['created_at'].apply(format_vietnam_time)
                
                sel_ma = st.selectbox("Lọc mã đề:", ["Tất cả"] + sorted(df['ma_de'].unique().tolist()))
                final_df = df if sel_ma == "Tất cả" else df[df['ma_de'] == sel_ma]
                st.dataframe(final_df[["ma_de", "ho_ten", "lop", "diem", "created_at"]].rename(columns={"created_at": "Thời gian nộp"}), use_container_width=True)
                st.download_button("📥 Tải bảng điểm", final_df.to_csv(index=False, encoding='utf-8-sig'), "Bang_diem_VN.csv")
