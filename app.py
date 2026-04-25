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

# --- STYLE GIAO DIỆN V34 ---
st.markdown(f"""
    <style>
    .stApp {{ background-image: url("{bg_img}"); background-attachment: fixed; background-size: cover; background-position: center; }}
    .main {{ background-color: rgba(255, 255, 255, 0.85); padding: 2rem; border-radius: 20px; }}
    h1, .sub-title {{ text-align: center !important; color: #1e3a8a !important; }}
    div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="datepicker"] {{
        background-color: #ffffff !important; border: 2px solid #cbd5e1 !important; border-radius: 8px !important;
    }}
    [data-testid="stForm"] {{
        background-color: rgba(255, 255, 255, 0.95); border: 2px solid #1e3a8a;
        border-radius: 15px; padding: 2rem; max-width: 850px; margin: 0 auto !important;
    }}
    @media print {{
        header, footer, .stTabs, [data-testid="stHeader"], [data-testid="stSidebar"], .no-print, button, .stButton {{ display: none !important; }}
        .main {{ background: white !important; padding: 0 !important; width: 100% !important; }}
        .print-area {{ display: block !important; width: 100% !important; color: black !important; }}
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
        question_text = parts[0].replace("[[DUNG]]", "").replace("[[HET]]", "").strip()
        options_dict = {}
        ans_key = ""
        for j in range(1, len(parts), 2):
            label = parts[j].strip().upper()[0]
            val = parts[j+1].replace('[[DUNG]]', '').replace('[[HET]]', '').strip()
            options_dict[label] = f"{label}. {val}"
            if "[[DUNG]]" in parts[j+1]: ans_key = label
        sorted_options = [options_dict[k] for k in sorted(options_dict.keys())]
        if sorted_options: questions.append({"question": f"{header} {question_text}", "options": sorted_options, "answer_key": ans_key})
    return questions

# --- TIÊU ĐỀ ---
st.markdown("<h1 class='no-print'>HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)
st.markdown("<div class='sub-title no-print'>Trường THCS Lê Quý Đôn, phường Hà Giang 1, tỉnh Tuyên Quang</div>", unsafe_allow_html=True)

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])

with tab_hs:
    exam_list_res = supabase.table("exam_questions").select("ma_de").execute()
    list_ma_de = [item['ma_de'] for item in exam_list_res.data] if exam_list_res.data else []

    if not st.session_state.get("is_testing", False):
        with st.form("info_form"):
            st.subheader("📝 Thông tin thí sinh")
            name = st.text_input("👤 Họ và Tên của em:")
            actual_class = st.text_input("🏫 Lớp của em:")
            sel_ma_de = st.selectbox("🔑 Chọn Mã đề thi:", options=["-- Chọn mã đề --"] + list_ma_de)
            if st.form_submit_button("🚀 BẮT ĐẦU LÀM BÀI"):
                if name and actual_class and sel_ma_de != "-- Chọn mã đề --":
                    ex_res = supabase.table("exam_questions").select("*").eq("ma_de", sel_ma_de).execute()
                    if ex_res.data:
                        ex_info = ex_res.data[0]
                        st.session_state.update({
                            "quiz_data": ex_info["nội_dung_json"], "time_limit": ex_info.get('thoi_gian_phut', 15),
                            "ma_de_dang_thi": sel_ma_de, "st_name": name, "st_class": actual_class,
                            "is_testing": True, "mon_lop": ex_info.get('ten_lop'), "ngay_thi": ex_info.get('ngay_thi')
                        })
                        st.rerun()
                else: st.error("❌ Em hãy điền đầy đủ thông tin nhé!")
    else:
        with st.form("quiz_form"):
            st.info(f"👨‍🎓: **{st.session_state['st_name'].upper()}** | Lớp: **{st.session_state['st_class']}** | Đề: **{st.session_state['ma_de_dang_thi']}**")
            u_choices = {}
            for idx, q in enumerate(st.session_state["quiz_data"]):
                st.write(f"**{q['question']}**")
                u_choices[idx] = st.radio("Chọn:", q['options'], index=None, key=f"q_{idx}", label_visibility="collapsed")
            
            st.write("---")
            confirm = st.checkbox("Em xác nhận đã kiểm tra kỹ bài làm và muốn nộp bài.")
            if st.form_submit_button("📤 NỘP BÀI THI"):
                if not confirm:
                    st.error("❌ Em hãy tích vào ô xác nhận nộp bài nhé!"); st.stop()
                
                c_num = 0
                for i, q in enumerate(st.session_state["quiz_data"]):
                    ans_k = q.get('answer_key', "")
                    if u_choices[i] and ans_k and u_choices[i].startswith(ans_k):
                        c_num += 1
                
                grade = round((c_num / len(st.session_state["quiz_data"])) * 10, 2)
                supabase.table("student_results").insert({
                    "ma_de": st.session_state["ma_de_dang_thi"], "ho_ten": st.session_state["st_name"], 
                    "lop": st.session_state["st_class"], "diem": grade, "so_cau_dung": f"{c_num}/{len(st.session_state['quiz_data'])}",
                    "lop_thi": st.session_state["mon_lop"], "ngay_thi": st.session_state["ngay_thi"]
                }).execute()
                
                st.session_state["is_testing"] = False
                if grade >= 8: st.balloons()
                st.success(f"Nộp bài thành công! Điểm của em: {grade}"); time.sleep(2); st.rerun()

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản lý:", type="password", key="gv_pwd")
    if pwd == ADMIN_PASSWORD:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("📤 QUẢN LÝ ĐỀ")
            n_ma = st.text_input("Mã đề:"); t_mon = st.text_input("Môn/Lớp:")
            t_gian = st.number_input("Thời gian (phút):", min_value=1, value=15)
            d_thi = st.date_input("Ngày thi:"); f_word = st.file_uploader("Tải Word:", type=["docx"])
            if st.button("🚀 Kích hoạt đề"):
                if n_ma and f_word:
                    d_js = parse_docx_simple(f_word)
                    supabase.table("exam_questions").upsert({"ma_de": n_ma, "nội_dung_json": d_js, "ten_lop": t_mon, "ngay_thi": d_thi.strftime("%d/%m/%Y"), "thoi_gian_phut": t_gian}).execute()
                    st.success("Xong!"); time.sleep(1); st.rerun()
            st.divider()
            if st.button("🔥 Xóa sạch kết quả"):
                supabase.table("student_results").delete().neq("id", 0).execute(); st.rerun()

        with col2:
            st.subheader("📊 KẾT QUẢ & IN PHIẾU")
            res_all = supabase.table("student_results").select("*").execute()
            if res_all.data:
                df = pd.DataFrame(res_all.data).sort_values(by="ho_ten")
                df['created_at'] = df['created_at'].apply(format_vietnam_time)
                st.dataframe(df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de", "created_at"]], use_container_width=True)
                
                st.write("---")
                sel_hs = st.selectbox("🖨️ Chọn học sinh in phiếu:", ["-- Chọn --"] + df['ho_ten'].tolist())
                if sel_hs != "-- Chọn --":
                    hs = df[df['ho_ten'] == sel_hs].iloc[0]
                    st.markdown(f"""
                    <div class="print-area" style="background: white; padding: 40px; border: 2px solid #1e3a8a; color: black !important; font-family: 'Arial';">
                        <h2 style="text-align: center; color: #1e3a8a; margin-bottom: 5px;">PHIẾU MINH CHỨNG KẾT QUẢ KIỂM TRA</h2>
                        <p style="text-align: center; margin-top: 0;">Trường THCS Lê Quý Đôn - Tuyên Quang</p>
                        <hr style="border: 1px solid #1e3a8a;">
                        <br>
                        <table style="width: 100%; color: black; border: none; font-size: 1.2em; line-height: 2em;">
                            <tr><td width="40%"><b>Họ và tên học sinh:</b></td><td>{hs['ho_ten'].upper()}</td></tr>
                            <tr><td><b>Lớp học:</b></td><td>{hs['lop']}</td></tr>
                            <tr><td><b>Môn kiểm tra:</b></td><td>{hs['lop_thi']}</td></tr>
                            <tr><td><b>Mã đề thi:</b></td><td>{hs['ma_de']}</td></tr>
                            <tr><td><b>Ngày thi:</b></td><td>{hs['ngay_thi']}</td></tr>
                            <tr><td><b>Thời gian nộp bài:</b></td><td>{hs['created_at']}</td></tr>
                            <tr><td><b>Kết quả đạt được:</b></td><td><b style="font-size: 1.3em; color: #1e3a8a;">{hs['diem']} điểm ({hs['so_cau_dung']})</b></td></tr>
                        </table>
                        <br><br><br>
                        <table style="width: 100%; text-align: center; color: black;">
                            <tr>
                                <td width="50%"><b>GIÁO VIÊN BỘ MÔN</b><br><br><br><br>(Ký và ghi rõ họ tên)</td>
                                <td width="50%"><b>HỌC SINH XÁC NHẬN</b><br><br><br><br>(Ký và ghi rõ họ tên)</td>
                            </tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                    st.info("💡 Nhấn Ctrl + P để in phiếu sạch sẽ này.")
