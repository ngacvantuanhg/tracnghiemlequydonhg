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

# --- STYLE GIAO DIỆN V43 ---
st.markdown(f"""
    <style>
    .stApp {{ background-image: url("{bg_img}"); background-attachment: fixed; background-size: cover; background-position: center; }}
    .main {{ background-color: rgba(255, 255, 255, 0.85); padding: 2rem; border-radius: 20px; }}
    h1, .sub-title {{ text-align: center !important; color: #1e3a8a !important; font-family: 'Arial'; }}
    
    div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="datepicker"] {{
        background-color: #ffffff !important; border: 2px solid #cbd5e1 !important; border-radius: 8px !important;
    }}
    
    /* STYLE CHO VÙNG IN */
    #print-section {{
        background-color: white !important;
        padding: 40px !important;
        border: 2px solid #1e3a8a !important;
        color: black !important;
        border-radius: 10px;
    }}

    @media print {{
        /* Ẩn mọi thứ của Streamlit */
        header, footer, .stTabs, [data-testid="stHeader"], [data-testid="stSidebar"], .no-print, button, .stButton, .stMarkdownContainer > *:not(#print-section) {{
            display: none !important;
        }}
        /* Ép vùng in hiện ra rạng rỡ */
        .main, .stApp {{ background: white !important; }}
        #print-section {{ display: block !important; position: absolute; top: 0; left: 0; width: 100% !important; }}
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

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])

with tab_hs:
    raw_res = supabase.table("exam_questions").select("ten_mon, ma_de").execute()
    data_all = raw_res.data if raw_res.data else []
    sub_list = sorted(list(set([str(i.get('ten_mon', '')).strip() for i in data_all if i.get('ten_mon')])))

    if not st.session_state.get("is_testing", False):
        with st.form("info_form"):
            st.subheader("📝 Đăng ký dự thi")
            name = st.text_input("👤 Họ và Tên của em:")
            actual_class = st.text_input("🏫 Lớp của em:")
            s_sub = st.selectbox("📚 Chọn Môn học:", options=["-- Chọn môn --"] + sub_list)
            m_list = [i['ma_de'] for i in data_all if str(i.get('ten_mon', '')).strip() == s_sub]
            s_ma = st.selectbox("🔑 Chọn Mã đề thi:", options=["-- Chọn mã đề --"] + m_list)
            if st.form_submit_button("🚀 BẮT ĐẦU LÀM BÀI"):
                if name and actual_class and s_sub != "-- Chọn môn --" and s_ma != "-- Chọn mã đề --":
                    ex_res = supabase.table("exam_questions").select("*").eq("ma_de", s_ma).execute()
                    if ex_res.data:
                        inf = ex_res.data[0]
                        st.session_state.update({"quiz_data": inf["nội_dung_json"], "st_name": name, "st_class": actual_class, "is_testing": True, "mon_hoc": inf.get('ten_mon'), "ngay_thi": inf.get('ngay_thi')})
                        st.rerun()
    else:
        with st.form("quiz_form"):
            st.info(f"👨‍🎓: **{st.session_state['st_name'].upper()}** | Môn: **{st.session_state['mon_hoc']}**")
            u_choices = {}
            for idx, q in enumerate(st.session_state["quiz_data"]):
                st.write(f"**{idx+1}. {q['question']}**")
                u_choices[idx] = st.radio("Chọn:", q['options'], index=None, key=f"q_{idx}", label_visibility="collapsed")
            if st.form_submit_button("📤 NỘP BÀI THI"):
                c_num = sum(1 for i, q in enumerate(st.session_state["quiz_data"]) if u_choices[i] and u_choices[i].startswith(q.get('answer_key', '')))
                grade = round((c_num / len(st.session_state["quiz_data"])) * 10, 2)
                supabase.table("student_results").insert({"ma_de": st.session_state["ma_de_dang_thi"], "ho_ten": st.session_state["st_name"], "lop": st.session_state["st_class"], "diem": grade, "so_cau_dung": f"{c_num}/{len(st.session_state['quiz_data'])}", "lop_thi": st.session_state["mon_hoc"], "ngay_thi": st.session_state["ngay_thi"]}).execute()
                st.session_state["is_testing"] = False
                st.success(f"Nộp bài thành công! Điểm: {grade}"); time.sleep(2); st.rerun()

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản trị:", type="password")
    if pwd == ADMIN_PASSWORD:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("📤 ĐĂNG ĐỀ")
            n_ma = st.text_input("Mã đề:"); t_mon = st.text_input("Môn học:"); t_lop = st.text_input("Lớp:"); d_thi = st.date_input("Ngày:"); f_word = st.file_uploader("File Word:", type=["docx"])
            if st.button("🚀 Kích hoạt đề"):
                if n_ma and t_mon and f_word:
                    d_js = parse_docx_simple(f_word)
                    supabase.table("exam_questions").upsert({"ma_de": n_ma, "nội_dung_json": d_js, "ten_mon": t_mon.strip(), "ten_lop": t_lop.strip(), "ngay_thi": d_thi.strftime("%d/%m/%Y")}).execute()
                    st.success("Đã đăng!"); st.rerun()
            st.divider()
            if st.button("🔥 XÓA TẤT CẢ KẾT QUẢ"):
                supabase.table("student_results").delete().neq("id", 0).execute(); st.rerun()

        with c2:
            st.subheader("📊 KẾT QUẢ VÀ IN PHIẾU")
            r_all = supabase.table("student_results").select("*").execute()
            if r_all.data:
                df = pd.DataFrame(r_all.data).sort_values(by="ho_ten")
                df['created_at'] = df['created_at'].apply(format_vietnam_time)
                st.dataframe(df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de"]], use_container_width=True)
                
                s_hs = st.selectbox("🖨️ Chọn học sinh in phiếu:", ["-- Chọn --"] + df['ho_ten'].tolist())
                if s_hs != "-- Chọn --":
                    hs = df[df['ho_ten'] == s_hs].iloc[0]
                    # --- ĐÂY LÀ PHẦN QUAN TRỌNG NHẤT ---
                    st.markdown(f"""
                    <div id="print-section">
                        <h2 style="text-align: center; color: #1e3a8a;">PHIẾU MINH CHỨNG KẾT QUẢ KIỂM TRA</h2>
                        <p style="text-align: center; color: black;">Trường THCS Lê Quý Đôn - Tuyên Quang</p>
                        <hr style="border: 1px solid #1e3a8a;">
                        <br>
                        <table style="width: 100%; color: black; font-size: 1.2em; line-height: 2.5em;">
                            <tr><td width="40%"><b>Họ và tên học sinh:</b></td><td>{hs['ho_ten'].upper()}</td></tr>
                            <tr><td><b>Lớp học:</b></td><td>{hs['lop']}</td></tr>
                            <tr><td><b>Môn kiểm tra:</b></td><td>{hs['lop_thi']}</td></tr>
                            <tr><td><b>Ngày nộp bài:</b></td><td>{hs['created_at']}</td></tr>
                            <tr><td><b>Kết quả:</b></td><td><b style="font-size: 1.3em;">{hs['diem']} điểm ({hs['so_cau_dung']})</b></td></tr>
                        </table>
                        <br><br><br>
                        <table style="width: 100%; text-align: center; color: black;">
                            <tr>
                                <td><b>GIÁO VIÊN BỘ MÔN</b><br><br><br><br><br>(Ký tên)</td>
                                <td><b>HỌC SINH XÁC NHẬN</b><br><br><br><br><br>(Ký tên)</td>
                            </tr>
                        </table>
                    </div>
                    <br>
                    <div class="no-print" style="text-align: center;">
                        <button onclick="window.print()" style="background-color: #1e3a8a; color: white; padding: 10px 30px; border-radius: 20px; cursor: pointer; border: none; font-weight: bold;">
                            🖨️ NHẤN VÀO ĐÂY ĐỂ IN PHIẾU
                        </button>
                    </div>
                    """, unsafe_allow_html=True)
