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

# --- LINK ẢNH NỀN GITHUB ---
bg_img = "https://raw.githubusercontent.com/ngacvantuanhg/tracnghiemlequydonhg/main/Anhnen.png"

# --- STYLE GIAO DIỆN V21 (Ô NHẬP LIỆU TRẮNG SÁNG & CĂN GIỮA) ---
st.markdown(f"""
    <style>
    .stApp {{
        background-image: url("{bg_img}");
        background-attachment: fixed;
        background-size: cover;
        background-position: center;
    }}
    .main {{
        background-color: rgba(255, 255, 255, 0.8);
        padding: 2rem;
        border-radius: 20px;
    }}
    h1, .sub-title {{
        text-align: center !important;
        color: #1e3a8a !important;
    }}
    input, div[data-baseweb="input"], div[data-baseweb="select"], .stTextArea textarea {{
        background-color: #ffffff !important;
        color: #1e3a8a !important;
        border: 2px solid #cbd5e1 !important;
        border-radius: 8px !important;
    }}
    [data-testid="stForm"] {{
        background-color: rgba(255, 255, 255, 0.95);
        border: 2px solid #1e3a8a;
        border-radius: 15px;
        padding: 2rem;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        max-width: 850px;
        margin: 0 auto !important;
    }}
    .stButton>button {{
        display: block;
        margin: 0 auto !important;
        background-color: #1e3a8a;
        color: white;
        border-radius: 30px;
        padding: 10px 40px;
        font-weight: bold;
    }}
    .timer-box {{ 
        position: fixed; top: 20px; right: 20px; padding: 10px 20px; 
        background: #1e3a8a; color: white; border-radius: 10px;
        z-index: 1000; text-align: center;
    }}
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1>HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Trường THCS Lê Quý Đôn, phường Hà Giang 1, tỉnh Tuyên Quang</div>", unsafe_allow_html=True)

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
    # Lấy danh sách mã đề từ Database để học sinh chọn
    exam_list_res = supabase.table("exam_questions").select("ma_de").execute()
    list_ma_de = [item['ma_de'] for item in exam_list_res.data] if exam_list_res.data else []

    if not st.session_state.get("is_testing", False):
        with st.form("info_form"):
            st.subheader("📝 Thông tin thí sinh")
            name = st.text_input("👤 Họ và Tên của em:", placeholder="Nhập đầy đủ họ tên...")
            actual_class = st.text_input("🏫 Lớp của em:", placeholder="Ví dụ: 9A1, 9A2...")
            sel_ma_de = st.selectbox("🔑 Chọn Mã đề thi:", options=["-- Chọn mã đề --"] + list_ma_de)
            
            st.write("---")
            if st.form_submit_button("🚀 BẮT ĐẦU LÀM BÀI"):
                if name and actual_class and sel_ma_de != "-- Chọn mã đề --":
                    # Lấy thông tin đề đã chọn
                    exam_res = supabase.table("exam_questions").select("*").eq("ma_de", sel_ma_de).execute()
                    if exam_res.data:
                        exam_info = exam_res.data[0]
                        st.session_state["quiz_data"] = exam_info["nội_dung_json"]
                        st.session_state["time_limit"] = exam_info.get('thoi_gian_phut', 15)
                        st.session_state["ten_mon"] = exam_info.get('ten_lop')
                        st.session_state["ngay_thi_chuan"] = exam_info.get('ngay_thi')
                        st.session_state["ma_de_dang_thi"] = sel_ma_de
                        st.session_state["st_name"] = name
                        st.session_state["st_class"] = actual_class
                        st.session_state["end_time"] = time.time() + (st.session_state["time_limit"] * 60)
                        st.session_state["is_testing"] = True
                        st.rerun()
                else:
                    st.error("❌ Em hãy điền đủ Họ tên, Lớp và Chọn đúng mã đề nhé!")
    
    else:
        # GIAO DIỆN ĐANG LÀM BÀI
        time_left = int(st.session_state["end_time"] - time.time())
        if time_left > 0:
            mm, ss = divmod(time_left, 60)
            st.markdown(f'<div class="timer-box"><small>⏳ CÒN LẠI</small><br><b style="font-size:24px;">{mm:02d}:{ss:02d}</b></div>', unsafe_allow_html=True)
        
        with st.form("quiz_form"):
            st.info(f"👨‍🎓: **{st.session_state['st_name'].upper()}** | Lớp: **{st.session_state['st_class']}** | Đề: **{st.session_state['ma_de_dang_thi']}**")
            user_selections = {}
            for idx, q in enumerate(st.session_state["quiz_data"]):
                st.write(f"**Câu {idx+1}: {q['question']}**")
                user_selections[idx] = st.radio("Chọn đáp án:", q['options'], index=None, key=f"q_{idx}", label_visibility="collapsed")
                st.write("")
            
            st.divider()
            confirm = st.checkbox("Em xác nhận đã kiểm tra kỹ và muốn nộp bài.")
            submitted = st.form_submit_button("📤 NỘP BÀI THI")

            if submitted or time_left <= 0:
                if time_left <= 0: st.error("⏰ Hết giờ! Hệ thống tự động nộp bài...")
                elif not confirm: 
                    st.error("❌ Em cần tích xác nhận trước khi nộp!")
                    st.stop()
                
                correct_num = sum(1 for i, q in enumerate(st.session_state["quiz_data"]) if user_selections[i] and user_selections[i].startswith(q['answer']))
                grade = round((correct_num / len(st.session_state["quiz_data"])) * 10, 2)
                
                supabase.table("student_results").insert({
                    "ma_de": st.session_state["ma_de_dang_thi"], "ho_ten": st.session_state["st_name"], 
                    "lop": st.session_state["st_class"], "diem": grade, 
                    "so_cau_dung": f"{correct_num}/{len(st.session_state['quiz_data'])}", 
                    "lop_thi": st.session_state["ten_mon"], "ngay_thi": st.session_state["ngay_thi_chuan"]
                }).execute()

                st.markdown("---")
                if grade < 5:
                    st.markdown("<h1 style='font-size:80px;'>😔</h1>", unsafe_allow_html=True)
                    st.error(f"### Điểm của em: {grade}. Cố gắng hơn nhé!")
                elif grade <= 7:
                    st.markdown("<h1 style='font-size:80px;'>🙂</h1>", unsafe_allow_html=True)
                    st.warning(f"### Điểm của em: {grade}. Khá tốt!")
                else:
                    st.balloons(); st.snow()
                    st.markdown("<h1 style='font-size:80px;'>🎉 😍 🎉</h1>", unsafe_allow_html=True)
                    st.success(f"### Điểm tuyệt vời: {grade}!")
                
                st.session_state["is_testing"] = False
                st.stop()

        if time_left > 0:
            time.sleep(1)
            st.rerun()

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản lý:", type="password")
    if pwd == ADMIN_PASSWORD:
        col1, col2 = st.columns([1, 2.5])
        
        with col1:
            st.subheader("📤 Đăng đề mới")
            n_ma = st.text_input("Mã đề (Ví dụ: 001):")
            t_mon = st.text_input("Môn/Lớp:")
            t_gian = st.number_input("Thời gian (phút):", min_value=1, value=15)
            d_thi = st.date_input("Ngày thi:")
            f_word = st.file_uploader("Tải Word:", type=["docx"])
            if st.button("🚀 Kích hoạt"):
                if n_ma and f_word:
                    d_json = parse_docx_smart(f_word)
                    supabase.table("exam_questions").upsert({
                        "ma_de": n_ma, "nội_dung_json": d_json, "ten_lop": t_mon, 
                        "ngay_thi": d_thi.strftime("%d/%m/%Y"), "thoi_gian_phut": t_gian
                    }).execute()
                    st.success(f"Đã kích hoạt đề {n_ma}!")
                    st.rerun()

            st.divider()
            
            # --- KHU VỰC QUẢN LÝ XÓA DỮ LIỆU ---
            st.subheader("🗑️ Quản lý kho đề")
            
            # Lấy danh sách đề hiện có để chọn xóa
            exam_res = supabase.table("exam_questions").select("ma_de, ten_lop").execute()
            if exam_res.data:
                list_de_xoa = [f"{item['ma_de']} - {item['ten_lop']}" for item in exam_res.data]
                de_chon_xoa = st.selectbox("Chọn đề muốn xóa:", ["-- Chọn đề --"] + list_de_xoa)
                
                if de_chon_xoa != "-- Chọn đề --":
                    ma_de_thuc_te = de_chon_xoa.split(" - ")[0]
                    st.warning(f"⚠️ Lưu ý: Xóa đề **{ma_de_thuc_te}** sẽ xóa sạch cả kết quả thi của học sinh kèm theo.")
                    
                    # Nút xác nhận xóa từng đề
                    if st.button(f"Xác nhận xóa đề {ma_de_thuc_te}"):
                        # 1. Xóa kết quả thi liên quan
                        supabase.table("student_results").delete().eq("ma_de", ma_de_thuc_te).execute()
                        # 2. Xóa chính cái đề đó
                        supabase.table("exam_questions").delete().eq("ma_de", ma_de_thuc_te).execute()
                        
                        st.success(f"Đã xóa sạch sẽ đề {ma_de_thuc_te} và dữ liệu liên quan!")
                        time.sleep(1)
                        st.rerun()
            
            st.divider()
            # Nút xóa tất cả (Cần cảnh báo mạnh)
            st.error("🚨 KHU VỰC NGUY HIỂM")
            if st.button("🔥 XÓA TẤT CẢ DỮ LIỆU"):
                st.session_state["confirm_delete_all"] = True
            
            if st.session_state.get("confirm_delete_all"):
                st.warning("Bạn có chắc chắn muốn xóa TOÀN BỘ đề thi và kết quả không? Hành động này không thể hoàn tác!")
                col_y, col_n = st.columns(2)
                if col_y.button("CÓ, XÓA HẾT"):
                    supabase.table("student_results").delete().neq("id", 0).execute()
                    supabase.table("exam_questions").delete().neq("ma_de", "NULL").execute()
                    st.session_state["confirm_delete_all"] = False
                    st.success("Hệ thống đã sạch bóng dữ liệu!")
                    st.rerun()
                if col_n.button("KHÔNG, HỦY"):
                    st.session_state["confirm_delete_all"] = False
                    st.rerun()

        with col2:
            st.subheader("📊 Bảng điểm & Báo cáo")
            # (Phần hiển thị bảng điểm và xuất Excel giữ nguyên như bản V21 nhé)
            all_res = supabase.table("student_results").select("*").execute()
            if all_res.data:
                df = pd.DataFrame(all_res.data)
                df['created_at'] = df['created_at'].apply(format_vietnam_time)
                l_lop = sorted(df['lop_thi'].dropna().unique().tolist())
                s_lop = st.selectbox("📌 Lớp:", l_lop)
                f_df = df[df['lop_thi'] == s_lop].sort_values(by="ho_ten")
                st.dataframe(f_df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de", "created_at"]], use_container_width=True)
                
                # Nút tải Excel (giữ nguyên code cũ)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    f_df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de", "created_at"]].to_excel(writer, index=False, sheet_name='Báo cáo')
                    workbook, worksheet = writer.book, writer.sheets['Báo cáo']
                    h_format = workbook.add_format({'bold': True, 'bg_color': '#D1D5DB', 'border': 1, 'align': 'center'})
                    for c_num, val in enumerate(["Họ và Tên", "Lớp", "Đúng/Tổng", "Điểm", "Mã đề", "Thời gian"]):
                        worksheet.write(0, c_num, val, h_format)
                    worksheet.set_column('A:F', 20)
                st.download_button("📥 Tải Báo cáo Excel", data=output.getvalue(), file_name=f"Bao_cao_{s_lop}.xlsx")
            else:
                st.info("Chưa có kết quả thi nào để hiển thị.")
