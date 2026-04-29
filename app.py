import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime
import pytz
import time

# --- KẾT NỐI HỆ THỐNG ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "141983") 
    supabase = create_client(url, key)
except Exception as e:
    st.error("Lỗi cấu hình hệ thống. Vui lòng kiểm tra Secrets!")
    st.stop()

st.set_page_config(page_title="Hệ Thống Thi Lê Quý Đôn", layout="wide", page_icon="🏫")
bg_img = "https://raw.githubusercontent.com/ngacvantuanhg/tracnghiemlequydonhg/main/Anhnen.png"

# --- STYLE GIAO DIỆN ---
st.markdown(f"""
    <style>
    .stApp {{ background-image: url("{bg_img}"); background-attachment: fixed; background-size: cover; background-position: center; }}
    .main {{ background-color: rgba(255, 255, 255, 0.9); padding: 2rem; border-radius: 20px; }}
    div[data-baseweb="input"], div[data-baseweb="select"] {{
        background-color: #ffffff !important; border: 2px solid #cbd5e1 !important;
    }}
    .printable-card {{
        background: white; padding: 40px; border: 2px solid #1e3a8a; color: black; border-radius: 10px;
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

def parse_docx_strict(file):
    doc = Document(file)
    questions = []
    full_text_with_marks = ""
    for para in doc.paragraphs:
        para_text = ""
        for run in para.runs:
            # Kiểm tra mã màu đỏ FF0000 cực kỳ nghiêm ngặt
            is_red = run.font.color and run.font.color.rgb and str(run.font.color.rgb) == "FF0000"
            if is_red:
                para_text += f"[[DUNG]]{run.text}[[HET]]"
            else:
                para_text += run.text
        full_text_with_marks += para_text + "\n"
    
    q_blocks = re.split(r'(?i)(Câu\s+\d+[:.])', full_text_with_marks)
    for i in range(1, len(q_blocks), 2):
        header = q_blocks[i].strip()
        parts = re.split(r'(?i)\b([A-D]\s*[:.])', q_blocks[i+1])
        question_text = parts[0].replace("[[DUNG]]", "").replace("[[HET]]", "").strip()
        
        options = []
        ans_key = ""
        for j in range(1, len(parts), 2):
            label = parts[j].strip().upper()[0]
            content = parts[j+1]
            if "[[DUNG]]" in content:
                ans_key = label # Ghi nhận đáp án đúng
            clean_val = content.replace("[[DUNG]]", "").replace("[[HET]]", "").strip()
            options.append(f"{label}. {clean_val}")
        
        if options:
            questions.append({
                "question": f"{header} {question_text}",
                "options": options,
                "answer_key": ans_key
            })
    return questions

# --- TIÊU ĐỀ ---
st.markdown("<h1 style='text-align:center; color:#1e3a8a;'>HỆ THỐNG THI LÊ QUÝ ĐÔN</h1>", unsafe_allow_html=True)
tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI", "👩‍🏫 QUẢN TRỊ"])

with tab_hs:
    res_exams = supabase.table("exam_questions").select("ten_mon, ma_de").execute()
    all_exams_data = res_exams.data if res_exams.data else []
    subjects = sorted(list(set([str(i.get('ten_mon', '')).strip() for i in all_exams_data if i.get('ten_mon')])))

    if not st.session_state.get("is_testing", False):
        st.subheader("📝 Đăng ký dự thi")
        name = st.text_input("👤 Họ tên:")
        actual_class = st.text_input("🏫 Lớp:")
        sel_subject = st.selectbox("📚 Môn học:", options=["-- Chọn môn --"] + subjects)
        filtered_codes = [i['ma_de'] for i in all_exams_data if str(i.get('ten_mon', '')).strip() == sel_subject]
        sel_ma_de = st.selectbox("🔑 Mã đề:", options=["-- Chọn mã đề --"] + filtered_codes)
        
        if st.button("🚀 BẮT ĐẦU"):
            if name and actual_class and sel_ma_de != "-- Chọn mã đề --":
                ex_res = supabase.table("exam_questions").select("*").eq("ma_de", sel_ma_de).execute()
                if ex_res.data:
                    inf = ex_res.data[0]
                    st.session_state.update({
                        "quiz_data": inf["nội_dung_json"], "ma_de_dang_thi": sel_ma_de, 
                        "st_name": name, "st_class": actual_class, "is_testing": True, 
                        "mon_hoc": inf.get('ten_mon'), "ngay_thi": inf.get('ngay_thi')
                    })
                    st.rerun()
            else: st.error("Thiếu thông tin bạn ơi!")
    else:
        with st.form("quiz_form"):
            st.info(f"Thí sinh: {st.session_state['st_name']} | Đề: {st.session_state['ma_de_dang_thi']}")
            u_choices = {}
            for idx, q in enumerate(st.session_state["quiz_data"]):
                st.write(f"**{idx+1}. {q['question']}**")
                u_choices[idx] = st.radio("Chọn:", q['options'], index=None, key=f"q_{idx}", label_visibility="collapsed")
            if st.form_submit_button("📤 NỘP BÀI"):
                c_num = 0
                for i, q in enumerate(st.session_state["quiz_data"]):
                    if u_choices[i] and q['answer_key'] and u_choices[i].startswith(q['answer_key']):
                        c_num += 1
                grade = round((c_num / len(st.session_state["quiz_data"])) * 10, 2)
                supabase.table("student_results").insert({
                    "ma_de": st.session_state["ma_de_dang_thi"], "ho_ten": st.session_state["st_name"], 
                    "lop": st.session_state["st_class"], "diem": grade, "so_cau_dung": f"{c_num}/{len(st.session_state['quiz_data'])}",
                    "lop_thi": st.session_state["mon_hoc"], "ngay_thi": st.session_state["ngay_thi"]
                }).execute()
                st.session_state["is_testing"] = False
                st.success(f"Nộp bài thành công! Điểm: {grade}"); time.sleep(2); st.rerun()

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu:", type="password")
    if pwd == ADMIN_PASSWORD:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("📤 ĐĂNG ĐỀ")
            n_ma = st.text_input("Mã đề:"); t_mon = st.text_input("Môn:"); f_word = st.file_uploader("File Word:", type=["docx"])
            if st.button("🚀 Kích hoạt"):
                if n_ma and t_mon and f_word:
                    d_js = parse_docx_strict(f_word)
                    supabase.table("exam_questions").upsert({"ma_de": n_ma, "nội_dung_json": d_js, "ten_mon": t_mon, "ngay_thi": datetime.now().strftime("%d/%m/%Y")}).execute()
                    st.success("Đã đăng đề!"); time.sleep(1); st.rerun()
            st.divider()
            if st.button("🔥 XÓA TẤT CẢ KẾT QUẢ"):
                supabase.table("student_results").delete().neq("id", 0).execute(); st.rerun()

        with c2:
            st.subheader("📊 KẾT QUẢ & IN PHIẾU")
            res = supabase.table("student_results").select("*").execute()
            if res.data:
                df = pd.DataFrame(res.data)
                st.dataframe(df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de"]], use_container_width=True)
                s_hs = st.selectbox("🖨️ Chọn học sinh in phiếu:", ["-- Chọn --"] + sorted(df['ho_ten'].tolist()))
                if s_hs != "-- Chọn --":
                    h = df[df['ho_ten'] == s_hs].iloc[0]
                    # KHÔI PHỤC PHẦN IN KÝ TÊN
                    st.markdown(f"""
                    <div class="printable-card">
                        <h2 style="text-align:center;">PHIẾU MINH CHỨNG KẾT QUẢ</h2>
                        <p style="text-align:center;">Trường THCS Lê Quý Đôn - Tuyên Quang</p>
                        <hr>
                        <p><b>Học sinh:</b> {h['ho_ten'].upper()} &nbsp;&nbsp;&nbsp; <b>Lớp:</b> {h['lop']}</p>
                        <p><b>Môn thi:</b> {h['lop_thi']} &nbsp;&nbsp;&nbsp; <b>Mã đề:</b> {h['ma_de']}</p>
                        <p><b>Kết quả: {h['diem']} điểm ({h['so_cau_dung']})</b></p>
                        <br><br>
                        <table style="width:100%; text-align:center;">
                            <tr>
                                <td><b>GIÁO VIÊN BỘ MÔN</b><br><br><br>(Ký tên)</td>
                                <td><b>HỌC SINH XÁC NHẬN</b><br><br><br>(Ký tên)</td>
                            </tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                    # Nút tải file in cực ổn định
                    html_print = f"<html><head><meta charset='utf-8'></head><body onload='window.print()'><div style='border:2px solid black; padding:30px; font-family:Arial;'> <h2 style='text-align:center;'>PHIẾU KẾT QUẢ</h2> <p>Học sinh: {h['ho_ten'].upper()}</p> <p>Lớp: {h['lop']}</p> <p>Điểm: {h['diem']}</p> <br><br> <table style='width:100%;'><tr><td>Giáo viên</td><td>Học sinh</td></tr></table> </div></body></html>"
                    st.download_button("📥 TẢI FILE IN", data=html_print, file_name=f"KetQua_{h['ho_ten']}.html", mime="text/html")
