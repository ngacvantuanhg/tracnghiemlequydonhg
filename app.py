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

bg_img = "https://raw.githubusercontent.com/ngacvantuanhg/tracnghiemlequydonhg/main/Anhnen.png"

# --- STYLE GIAO DIỆN V26 ---
st.markdown(f"""
    <style>
    .stApp {{ background-image: url("{bg_img}"); background-attachment: fixed; background-size: cover; background-position: center; }}
    .main {{ background-color: rgba(255, 255, 255, 0.8); padding: 2rem; border-radius: 20px; }}
    h1, .sub-title {{ text-align: center !important; color: #1e3a8a !important; }}
    
    /* Làm trắng ô nhập liệu */
    div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="datepicker"] {{
        background-color: #ffffff !important; border: 2px solid #cbd5e1 !important; border-radius: 8px !important;
    }}
    
    [data-testid="stForm"] {{
        background-color: rgba(255, 255, 255, 0.95); border: 2px solid #1e3a8a;
        border-radius: 15px; padding: 2rem; max-width: 850px; margin: 0 auto !important;
    }}
    
    .timer-box {{ position: fixed; top: 20px; right: 20px; padding: 10px 20px; background: #1e3a8a; color: white; border-radius: 10px; z-index: 1000; text-align: center; border: 2px solid white; }}
    
    /* Định dạng dành riêng cho bản in (Print Media) */
    @media print {{
        .no-print, [data-testid="stHeader"], [data-testid="stSidebar"], .stTabs, .stButton {{ display: none !important; }}
        .print-only {{ display: block !important; background: white !important; padding: 20px; }}
        .main {{ background: white !important; }}
    }}
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 class='no-print'>HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)
st.markdown("<div class='sub-title no-print'>Trường THCS Lê Quý Đôn, phường Hà Giang 1, tỉnh Tuyên Quang</div>", unsafe_allow_html=True)

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
        if sorted_options: questions.append({"question": f"{header} {question_text}", "options": sorted_options, "answer": final_answer})
    return questions

# --- TAB GIAO DIỆN ---
tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])

with tab_hs:
    exam_list_res = supabase.table("exam_questions").select("ma_de").execute()
    list_ma_de = [item['ma_de'] for item in exam_list_res.data] if exam_list_res.data else []

    if not st.session_state.get("is_testing", False):
        with st.form("info_form"):
            name = st.text_input("👤 Họ và Tên của em:")
            actual_class = st.text_input("🏫 Lớp của em:")
            sel_ma_de = st.selectbox("🔑 Chọn Mã đề thi:", options=["-- Chọn mã đề --"] + list_ma_de)
            if st.form_submit_button("🚀 BẮT ĐẦU LÀM BÀI"):
                if name and actual_class and sel_ma_de != "-- Chọn mã đề --":
                    exam_res = supabase.table("exam_questions").select("*").eq("ma_de", sel_ma_de).execute()
                    if exam_res.data:
                        exam_info = exam_res.data[0]
                        st.session_state.update({
                            "quiz_data": exam_info["nội_dung_json"],
                            "time_limit": exam_info.get('thoi_gian_phut', 15),
                            "ma_de_dang_thi": sel_ma_de,
                            "st_name": name, "st_class": actual_class,
                            "end_time": time.time() + (exam_info.get('thoi_gian_phut', 15) * 60),
                            "is_testing": True,
                            "lop_thi_hs": exam_info.get('ten_lop'),
                            "ngay_thi_hs": exam_info.get('ngay_thi')
                        })
                        st.rerun()
                else: st.error("❌ Điền đủ thông tin em nhé!")
    else:
        # XỬ LÝ ĐỒNG HỒ ĐẾM NGƯỢC (Chạy bằng JavaScript để mượt hơn)
        time_left = int(st.session_state["end_time"] - time.time())
        if time_left > 0:
            mm, ss = divmod(time_left, 60)
            st.markdown(f'<div class="timer-box"><small>⏳ CÒN LẠI</small><br><b style="font-size:24px;">{mm:02d}:{ss:02d}</b></div>', unsafe_allow_html=True)
            # Tự động reload sau 1 giây
            st.empty()
            time.sleep(1)
            
        with st.form("quiz_form"):
            st.info(f"👨‍🎓: **{st.session_state['st_name'].upper()}** | Lớp: **{st.session_state['st_class']}** | Đề: **{st.session_state['ma_de_dang_thi']}**")
            user_selections = {}
            for idx, q in enumerate(st.session_state["quiz_data"]):
                st.write(f"**Câu {idx+1}: {q['question']}**")
                user_selections[idx] = st.radio("Chọn:", q['options'], index=None, key=f"q_{idx}", label_visibility="collapsed")
            
            st.write("---")
            confirm = st.checkbox("Em đã kiểm tra kỹ và muốn nộp bài.")
            if st.form_submit_button("📤 NỘP BÀI THI") or time_left <= 0:
                if time_left > 0 and not confirm: st.error("❌ Em hãy tích xác nhận trước khi nộp!"); st.stop()
                
                correct_num = 0
                bai_lam_text = []
                for i, q in enumerate(st.session_state["quiz_data"]):
                    choice = user_selections[i][0] if user_selections[i] else "Chưa chọn"
                    bai_lam_text.append(f"{i+1}:{choice}")
                    if user_selections[i] and user_selections[i].startswith(q['answer']): correct_num += 1
                
                grade = round((correct_num / len(st.session_state["quiz_data"])) * 10, 2)
                supabase.table("student_results").insert({
                    "ma_de": st.session_state["ma_de_dang_thi"], "ho_ten": st.session_state["st_name"], 
                    "lop": st.session_state["st_class"], "diem": grade, 
                    "so_cau_dung": f"{correct_num}/{len(st.session_state['quiz_data'])}",
                    "lop_thi": st.session_state["lop_thi_hs"], "ngay_thi": st.session_state["ngay_thi_hs"],
                    "chi_tiet_bai_lam": ",".join(bai_lam_text)
                }).execute()
                
                st.session_state["is_testing"] = False
                st.balloons(); st.success(f"Nộp bài thành công! Điểm: {grade}"); time.sleep(3); st.rerun()

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản lý:", type="password", key="pass_gv")
    if pwd == ADMIN_PASSWORD:
        all_res = supabase.table("student_results").select("*").execute()
        if all_res.data:
            df = pd.DataFrame(all_res.data)
            df['created_at'] = df['created_at'].apply(format_vietnam_time)
            
            # CHỌN HỌC SINH ĐỂ IN
            st.subheader("🖨️ XUẤT MINH CHỨNG BÀI LÀM (Dạng phiếu)")
            sel_hs = st.selectbox("Chọn học sinh muốn in phiếu bài làm:", ["-- Chọn học sinh --"] + sorted(df['ho_ten'].tolist()))
            
            if sel_hs != "-- Chọn học sinh --":
                hs_res = df[df['ho_ten'] == sel_hs].iloc[0]
                de_res = supabase.table("exam_questions").select("nội_dung_json").eq("ma_de", hs_res['ma_de']).execute()
                
                if de_res.data:
                    quiz_content = de_res.data[0]['nội_dung_json']
                    # Giải mã bài làm: "1:A,2:B" -> {"1":"A", "2":"B"}
                    bai_lam_dict = dict(item.split(":") for item in hs_res['chi_tiet_bai_lam'].split(","))
                    
                    # VÙNG IN (Dùng Class print-only để chỉ in vùng này)
                    st.markdown("---")
                    with st.container():
                        st.markdown(f"""
                        <div class="print-only" style="background: white; padding: 30px; border: 2px solid #1e3a8a; color: black !important;">
                            <h2 style="text-align: center; color: #1e3a8a;">PHIẾU MINH CHỨNG KẾT QUẢ BÀI LÀM</h2>
                            <p style="text-align: center;">Trường THCS Lê Quý Đôn - Tuyên Quang</p>
                            <hr>
                            <table style="width: 100%; border: none;">
                                <tr><td><b>Họ và tên:</b> {hs_res['ho_ten'].upper()}</td><td><b>Mã đề:</b> {hs_res['ma_de']}</td></tr>
                                <tr><td><b>Lớp học:</b> {hs_res['lop']}</td><td><b>Ngày thi:</b> {hs_res['ngay_thi']}</td></tr>
                                <tr><td><b>Môn thi:</b> {hs_res['lop_thi']}</td><td><b>Kết quả:</b> {hs_res['diem']} điểm ({hs_res['so_cau_dung']})</td></tr>
                            </table>
                            <hr>
                            <p><b>CHI TIẾT CÁC CÂU HỎI:</b></p>
                        """, unsafe_allow_html=True)
                        
                        for i, q in enumerate(quiz_content):
                            em_chon = bai_lam_dict.get(str(i+1), "N/A")
                            dung_sai = "✅" if em_chon == q['answer'] else "❌"
                            st.markdown(f"""
                            <div style="margin-bottom: 15px; border-bottom: 1px dashed #ccc; padding-bottom: 5px; color: black !important;">
                                <b>Câu {i+1}:</b> {q['question']}<br>
                                &nbsp;&nbsp;&nbsp; - Em chọn: <b>{em_chon}</b> {dung_sai} | 
                                Đáp án đúng: <b style="color: green;">{q['answer']}</b>
                            </div>
                            """, unsafe_allow_html=True)
                            
                        st.markdown("</div>", unsafe_allow_html=True)
                        st.warning("👉 Nhấn **Ctrl + P** (Windows) hoặc **Cmd + P** (Mac) để in hoặc lưu PDF phiếu này.")
