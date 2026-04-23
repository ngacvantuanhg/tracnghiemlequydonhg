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

# --- STYLE GIAO DIỆN NAVY & WHITE ---
st.markdown("""
    <style>
    /* Nền chính */
    .stApp { background-color: #ffffff; }
    
    /* Tùy chỉnh Header */
    h1 { color: #1e3a8a; text-align: center; font-family: 'Helvetica Neue', sans-serif; font-weight: 800; letter-spacing: 1px; }
    .sub-title { text-align: center; color: #1e40af; font-weight: 500; margin-bottom: 30px; font-size: 1.2em; border-bottom: 2px solid #1e3a8a; padding-bottom: 10px; }
    
    /* Thanh Timer cố định - Màu Navy */
    .timer-box { 
        position: fixed; top: 80px; right: 30px; padding: 15px 25px; 
        background: #1e3a8a; color: white; border-radius: 10px;
        z-index: 9999; text-align: center; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border: 2px solid #ffffff;
    }

    /* Tùy chỉnh các nút bấm */
    .stButton>button { 
        background-color: #1e3a8a; color: white; border-radius: 8px; 
        padding: 0.6rem 2rem; border: none; font-weight: 600; width: 100%;
        transition: all 0.3s ease;
    }
    .stButton>button:hover { background-color: #1e40af; color: white; border: none; transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    
    /* Khu vực Form */
    [data-testid="stForm"] { border: 1px solid #e5e7eb; border-radius: 12px; padding: 2rem; background-color: #f8fafc; }
    
    /* Màu sắc Radio button */
    .stRadio > div { gap: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- TIÊU ĐỀ CHÍNH ---
st.markdown("<h1>HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Trường THCS Lê Quý Đôn, phường Hà Giang 1, thành phố Tuyên Quang</div>", unsafe_allow_html=True)

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

# --- PHÂN CHIA KHU VỰC ---
tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])

with tab_hs:
    ma_de_input = st.text_input("🔑 Nhập Mã đề thi:", placeholder="Nhập mã cô giáo cung cấp...")
    
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
                    col_a, col_b = st.columns(2)
                    name = col_a.text_input("👤 Họ và Tên của em:")
                    actual_class = col_b.text_input("🏫 Lớp của em:")
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
                # --- ĐỒNG HỒ ĐẾM NGƯỢC ---
                time_left = int(st.session_state[f"end_time_{ma_de_input}"] - time.time())
                
                if time_left > 0:
                    mm, ss = divmod(time_left, 60)
                    st.markdown(f'<div class="timer-box"><small>⏳ THỜI GIAN CÒN LẠI</small><br><b style="font-size:26px;">{mm:02d}:{ss:02d}</b></div>', unsafe_allow_html=True)
                
                with st.form("quiz_form"):
                    st.markdown(f"**Thí sinh:** {st.session_state[f'st_name_{ma_de_input}'].upper()} | **Lớp:** {st.session_state[f'st_class_{ma_de_input}']}")
                    user_selections = {}
                    for idx, q in enumerate(quiz):
                        st.write(f"**{q['question']}**")
                        user_selections[idx] = st.radio("Chọn đáp án:", q['options'], index=None, key=f"q_{ma_de_input}_{idx}", label_visibility="collapsed")
                        st.write("")
                    
                    st.divider()
                    confirm = st.checkbox("Em xác nhận đã kiểm tra kỹ và muốn nộp bài.")
                    submitted = st.form_submit_button("📤 NỘP BÀI THI")

                    if submitted or time_left <= 0:
                        if time_left <= 0: st.error("⏰ Hết giờ! Hệ thống đang tự động nộp bài...")
                        elif not confirm: 
                            st.error("❌ Em cần tích vào ô xác nhận trước khi nộp bài!")
                            st.stop()
                            
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
                            st.error(f"### Điểm của em: {grade}. Hãy nỗ lực hơn nhé!")
                        elif grade <= 7:
                            st.markdown("<h1 style='font-size:80px;'>🙂</h1>", unsafe_allow_html=True)
                            st.warning(f"### Điểm của em: {grade}. Em làm khá tốt!")
                        else:
                            st.balloons(); st.snow()
                            st.markdown("<h1 style='font-size:80px;'>🎉 😍 🎉</h1>", unsafe_allow_html=True)
                            st.success(f"### Điểm tuyệt vời: {grade}! Chúc mừng em!")
                        
                        del st.session_state[f"started_{ma_de_input}"]
                        st.stop()

                if time_left > 0:
                    time.sleep(1)
                    st.rerun()
        else: st.warning("🔎 Không tìm thấy mã đề!")

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản lý:", type="password")
    if pwd == ADMIN_PASSWORD:
        col1, col2 = st.columns([1, 2.5])
        with col1:
            st.subheader("📤 Đăng đề mới")
            new_ma = st.text_input("Mã đề:")
            ten_lop = st.text_input("Môn/Lớp:")
            thoi_gian = st.number_input("Thời gian (phút):", min_value=1, value=15)
            ngay_thi = st.date_input("Ngày kiểm tra:")
            word_file = st.file_uploader("Tải đề Word:", type=["docx"])
            if st.button("🚀 Kích hoạt đề"):
                if new_ma and word_file:
                    data = parse_docx_smart(word_file)
                    supabase.table("exam_questions").upsert({
                        "ma_de": new_ma, "nội_dung_json": data, "ten_lop": ten_lop, 
                        "ngay_thi": ngay_thi.strftime("%d/%m/%Y"), "thoi_gian_phut": thoi_gian
                    }).execute()
                    st.success("Đã kích hoạt đề thành công!")
            st.divider()
            if st.button("🔥 Xóa sạch kết quả"):
                supabase.table("student_results").delete().neq("id", 0).execute()
                st.rerun()

        with col2:
            st.subheader("📊 Bảng điểm tổng hợp")
            all_res = supabase.table("student_results").select("*").execute()
            if all_res.data:
                df = pd.DataFrame(all_res.data)
                df['created_at'] = df['created_at'].apply(format_vietnam_time)
                list_lop = sorted(df['lop_thi'].dropna().unique().tolist())
                sel_lop = st.selectbox("📌 Chọn Lớp:", list_lop)
                df_lop = df[df['lop_thi'] == sel_lop]
                list_ngay = sorted(df_lop['ngay_thi'].dropna().unique().tolist(), reverse=True)
                sel_ngay = st.selectbox("📅 Chọn Ngày:", list_ngay)
                final_df = df_lop[df_lop['ngay_thi'] == sel_ngay].sort_values(by="ho_ten")
                
                fig = px.histogram(final_df, x="diem", nbins=10, title=f"Phân phối điểm {sel_lop}", color_discrete_sequence=['#1e3a8a'])
                st.plotly_chart(fig, use_container_width=True)

                mapping_cols = {"ho_ten": "Họ và Tên", "lop": "Lớp học", "so_cau_dung": "Đúng/Tổng", "diem": "Điểm số", "created_at": "Thời gian nộp", "ma_de": "Mã đề"}
                st.dataframe(final_df[list(mapping_cols.keys())].rename(columns=mapping_cols), use_container_width=True)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    final_df[list(mapping_cols.keys())].rename(columns=mapping_cols).to_excel(writer, index=False, sheet_name='Báo cáo')
                    workbook, worksheet = writer.book, writer.sheets['Báo cáo']
                    h_format = workbook.add_format({'bold': True, 'bg_color': '#D1D5DB', 'border': 1, 'align': 'center'})
                    for c_num, val in enumerate(mapping_cols.values()): worksheet.write(0, c_num, val, h_format)
                    worksheet.set_column('A:F', 20)
                st.download_button("📥 Tải Báo cáo Excel", data=output.getvalue(), file_name=f"Bao_cao_{sel_lop}.xlsx")
