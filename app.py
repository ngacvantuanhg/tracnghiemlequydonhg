import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime
import pytz
import io
import plotly.express as px

# --- KẾT NỐI HỆ THỐNG ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)
st.set_page_config(page_title="Quản Lý Thi Online Lê Quý Đôn", layout="wide", page_icon="🏫")
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
st.title("🏫 Hệ Thống Quản Lý Thi & Báo Cáo Chuyên Sâu")
tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN LÝ GIÁO VIÊN"])

with tab_hs:
    ma_de_thi = st.text_input("🔑 Nhập Mã đề thi:")
    if ma_de_thi:
        res = supabase.table("exam_questions").select("*").eq("ma_de", ma_de_thi).execute()
        if res.data:
            exam_info = res.data[0]
            quiz = exam_info["nội_dung_json"]
            st.info(f"📋 **Lớp ra đề:** {exam_info.get('ten_lop')} | **Ngày kiểm tra:** {exam_info.get('ngay_thi')}")
            
            with st.form("quiz_form"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Họ và Tên học sinh:")
                actual_class = c2.text_input("Lớp (của em):")
                st.write("---")
                user_selections = {idx: st.radio(f"**{q['question']}**", q['options'], index=None, key=f"q_{idx}") for idx, q in enumerate(quiz)}
                
                if st.form_submit_button("NỘP BÀI THI", use_container_width=True):
                    if name and actual_class:
                        correct_num = sum(1 for i, q in enumerate(quiz) if user_selections[i] and user_selections[i].startswith(q['answer']))
                        total_q = len(quiz)
                        grade = round((correct_num / total_q) * 10, 2)
                        
                        # Ghi cả thông tin lớp và ngày thi vào kết quả để tra cứu
                        supabase.table("student_results").insert({
                            "ma_de": ma_de_thi, "ho_ten": name, "lop": actual_class, 
                            "diem": grade, "so_cau_dung": f"{correct_num}/{total_q}",
                            "lop_thi": exam_info.get('ten_lop'), "ngay_thi": exam_info.get('ngay_thi')
                        }).execute()
                        st.balloons()
                        st.success(f"Kết quả của {name.upper()}: {grade} điểm (Đúng {correct_num}/{total_q})")
                    else: st.error("⚠️ Điền tên và lớp nhé!")
        else: st.warning("Mã đề không tồn tại!")

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản lý:", type="password")
    if pwd == ADMIN_PASSWORD:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("📤 Đăng đề mới")
            new_ma = st.text_input("Mã đề (Ví dụ: 001):")
            ten_lop = st.text_input("Tên lớp kiểm tra (Ví dụ: 9A1):")
            ngay_thi = st.date_input("Ngày kiểm tra:", value=datetime.now())
            word_file = st.file_uploader("Tải đề Word:", type=["docx"])
            if st.button("Kích hoạt đề"):
                if new_ma and word_file:
                    data = parse_docx_smart(word_file)
                    supabase.table("exam_questions").upsert({
                        "ma_de": new_ma, "nội_dung_json": data, 
                        "ten_lop": ten_lop, "ngay_thi": ngay_thi.strftime("%d/%m/%Y")
                    }).execute()
                    st.success(f"Đã kích hoạt đề lớp {ten_lop}!")
            
            st.divider()
            if st.button("🔥 Xóa tất cả kết quả thi"):
                supabase.table("student_results").delete().neq("id", 0).execute()
                st.toast("Đã dọn dẹp sạch dữ liệu kết quả!")
                st.rerun()

        with col2:
            st.subheader("📊 Báo cáo & Bảng điểm")
            all_res = supabase.table("student_results").select("*").execute()
            if all_res.data:
                df = pd.DataFrame(all_res.data)
                df['created_at'] = df['created_at'].apply(format_vietnam_time)
                
                # Sắp xếp mặc định theo ngày thi và lớp thi
                df = df.sort_values(by=['ngay_thi', 'lop_thi', 'ho_ten'], ascending=[False, True, True])
                
                sel_ma = st.selectbox("Lọc theo Mã đề để xem báo cáo:", ["Tất cả"] + sorted(df['ma_de'].unique().tolist()))
                final_df = df if sel_ma == "Tất cả" else df[df['ma_de'] == sel_ma]
                
                # Hiển thị thông tin lớp/ngày nếu lọc theo mã đề
                if sel_ma != "Tất cả":
                    st.write(f"📌 **Lớp:** {final_df.iloc[0]['lop_thi']} | **Ngày thi:** {final_df.iloc[0]['ngay_thi']}")

                # Biểu đồ phân bổ điểm
                fig = px.histogram(final_df, x="diem", nbins=10, title=f"Phân phối điểm - {sel_ma}", color_discrete_sequence=['#17a2b8'])
                st.plotly_chart(fig, use_container_width=True)

                show_cols = ["ma_de", "lop_thi", "ngay_thi", "ho_ten", "lop", "so_cau_dung", "diem", "created_at"]
                st.dataframe(final_df[show_cols].rename(columns={
                    "lop_thi": "Lớp kiểm tra", "ngay_thi": "Ngày ra đề", 
                    "created_at": "Thời gian nộp", "so_cau_dung": "Đúng/Tổng"
                }), use_container_width=True)

                # Xuất Excel có đầy đủ thông tin
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    final_df[show_cols].to_excel(writer, index=False, sheet_name='Bao_cao_chi_tiet')
                    workbook = writer.book
                    worksheet = writer.sheets['Bao_cao_chi_tiet']
                    h_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center'})
                    for c_num, val in enumerate(show_cols): worksheet.write(0, c_num, val, h_format)
                    worksheet.set_column('A:H', 18)
                
                st.download_button("📥 Tải Báo Cáo Excel", data=output.getvalue(), file_name=f"Bao_cao_{sel_ma}.xlsx")
