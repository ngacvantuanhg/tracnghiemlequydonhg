import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime
import pytz
import io
import plotly.express as px # Thư viện vẽ biểu đồ

# --- KẾT NỐI HỆ THỐNG ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)
st.set_page_config(page_title="Hệ Thống Thi Online Lê Quý Đôn", layout="wide", page_icon="🏫")
ADMIN_PASSWORD = "141983" 

# --- HÀM HỖ TRỢ ---
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

# --- GIAO DIỆN ---
st.title("🏫 Hệ Thống Thi Trực Tuyến & Thống Kê Điểm Số")
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
                        st.success(f"Kết quả của {name.upper()}: {grade} điểm")
                    else: st.error("⚠️ Điền tên và lớp nhé!")
        else: st.warning("Mã đề không tồn tại!")

with tab_gv:
    pwd = st.text_input("🔐 Nhập mật khẩu quản lý:", type="password")
    if pwd == ADMIN_PASSWORD:
        st.success("Chào cô giáo!")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("📤 Đăng đề mới")
            new_ma = st.text_input("Mã đề:")
            word_file = st.file_uploader("Tải đề Word:", type=["docx"])
            if st.button("Kích hoạt đề"):
                if new_ma and word_file:
                    supabase.table("exam_questions").upsert({"ma_de": new_ma, "nội_dung_json": parse_docx_smart(word_file)}).execute()
                    st.success("Đã tải xong!")
        with col2:
            st.subheader("📊 Thống kê & Bảng điểm")
            all_data = supabase.table("student_results").select("*").execute()
            if all_data.data:
                df = pd.DataFrame(all_data.data)
                df['created_at'] = df['created_at'].apply(format_vietnam_time)
                # Tự động lọc & xếp theo mã đề
                df = df.sort_values(by=['ma_de', 'ho_ten'])
                
                sel_ma = st.selectbox("Xem bảng điểm mã đề:", ["Tất cả"] + sorted(df['ma_de'].unique().tolist()))
                final_df = df if sel_ma == "Tất cả" else df[df['ma_de'] == sel_ma]
                
                # Hiển thị biểu đồ
                fig = px.histogram(final_df, x="diem", nbins=10, title=f"Phân phối điểm số - Mã đề: {sel_ma}", 
                                   labels={'diem':'Điểm số', 'count':'Số lượng học sinh'}, color_discrete_sequence=['#28a745'])
                st.plotly_chart(fig, use_container_width=True)

                st.dataframe(final_df[["ma_de", "ho_ten", "lop", "diem", "created_at"]].rename(columns={"created_at": "Thời gian nộp"}), use_container_width=True)

                # --- XUẤT FILE EXCEL ĐẸP ---
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    final_df[["ma_de", "ho_ten", "lop", "diem", "created_at"]].to_excel(writer, index=False, sheet_name='BangDiem')
                    workbook = writer.book
                    worksheet = writer.sheets['BangDiem']
                    # Trang trí
                    header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
                    for col_num, value in enumerate(final_df[["ma_de", "ho_ten", "lop", "diem", "created_at"]].columns.values):
                        worksheet.write(0, col_num, value, header_format)
                    worksheet.set_column('A:E', 20)
                
                st.download_button(label="📥 Tải Bảng Điểm Excel (XLSX)", data=output.getvalue(), 
                                   file_name=f"Bang_diem_{sel_ma}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
