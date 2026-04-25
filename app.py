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

# --- STYLE GIAO DIỆN ---
st.markdown(f"""
    <style>
    .stApp {{ background-image: url("{bg_img}"); background-attachment: fixed; background-size: cover; background-position: center; }}
    .main {{ background-color: rgba(255, 255, 255, 0.85); padding: 2rem; border-radius: 20px; }}
    h1, .sub-title {{ text-align: center !important; color: #1e3a8a !important; font-family: 'Arial'; }}
    div[data-baseweb="input"], div[data-baseweb="select"], div[data-baseweb="datepicker"] {{
        background-color: #ffffff !important; border: 2px solid #cbd5e1 !important; border-radius: 8px !important;
    }}
    [data-testid="stForm"] {{
        background-color: rgba(255, 255, 255, 0.95); border: 2px solid #1e3a8a;
        border-radius: 15px; padding: 2rem; max-width: 850px; margin: 0 auto !important;
    }}
    .printable-card {{
        background-color: white !important; padding: 30px !important;
        border: 2px solid #1e3a8a !important; color: black !important; border-radius: 10px;
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
        ans_k = ""
        for j in range(1, len(parts), 2):
            label = parts[j].strip().upper()[0]
            val = parts[j+1].replace('[[DUNG]]', '').replace('[[HET]]', '').strip()
            options_dict[label] = f"{label}. {val}"
            if "[[DUNG]]" in parts[j+1]: ans_k = label
        sorted_options = [options_dict[k] for k in sorted(options_dict.keys())]
        if sorted_options:
            questions.append({"question": f"{header} {question_text}", "options": sorted_options, "answer_key": ans_k})
    return questions

# --- GIAO DIỆN CHÍNH ---
st.markdown("<h1>HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Trường THCS Lê Quý Đôn, phường Hà Giang 1, tỉnh Tuyên Quang</div>", unsafe_allow_html=True)

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])

with tab_hs:
    raw_exam_res = supabase.table("exam_questions").select("ten_mon, ma_de").execute()
    all_exams = raw_exam_res.data if raw_exam_res.data else []
    subjects = sorted(list(set([str(item.get('ten_mon', '')).strip() for item in all_exams if item.get('ten_mon')])))

    if not st.session_state.get("is_testing", False):
        with st.form("info_form"):
            st.subheader("📝 Đăng ký thông tin dự thi")
            name = st.text_input("👤 Họ và Tên của em:")
            actual_class = st.text_input("🏫 Lớp của em:")
            sel_subject = st.selectbox("📚 Chọn Môn học:", options=["-- Chọn môn --"] + subjects)
            filtered_codes = [item['ma_de'] for item in all_exams if str(item.get('ten_mon', '')).strip() == sel_subject]
            sel_ma_de = st.selectbox("🔑 Chọn Mã đề thi:", options=["-- Chọn mã đề --"] + filtered_codes)
            
            if st.form_submit_button("🚀 BẮT ĐẦU LÀM BÀI"):
                if name and actual_class and sel_subject != "-- Chọn môn --" and sel_ma_de != "-- Chọn mã đề --":
                    ex_res = supabase.table("exam_questions").select("*").eq("ma_de", sel_ma_de).execute()
                    if ex_res.data:
                        ex_info = ex_res.data[0]
                        st.session_state.update({
                            "quiz_data": ex_info["nội_dung_json"], "ma_de_dang_thi": sel_ma_de, 
                            "st_name": name, "st_class": actual_class, "is_testing": True, 
                            "mon_hoc": ex_info.get('ten_mon'), "lop_kiem_tra": ex_info.get('ten_lop'), "ngay_thi": ex_info.get('ngay_thi')
                        })
                        st.rerun()
                else: st.error("❌ Vui lòng điền đủ thông tin!")
    else:
        with st.form("quiz_form"):
            st.markdown(f"### MÔN THI: {st.session_state.get('mon_hoc', '').upper()}")
            st.info(f"👨‍🎓: **{st.session_state['st_name'].upper()}** | Đề: **{st.session_state['ma_de_dang_thi']}**")
            u_choices = {}
            for idx, q in enumerate(st.session_state["quiz_data"]):
                st.write(f"**{idx+1}. {q['question']}**")
                u_choices[idx] = st.radio("Chọn đáp án:", q['options'], index=None, key=f"q_{idx}", label_visibility="collapsed")
            if st.form_submit_button("📤 NỘP BÀI THI"):
                c_num = sum(1 for i, q in enumerate(st.session_state["quiz_data"]) if u_choices[i] and u_choices[i].startswith(q.get('answer_key', '')))
                grade = round((c_num / len(st.session_state["quiz_data"])) * 10, 2)
                supabase.table("student_results").insert({
                    "ma_de": st.session_state["ma_de_dang_thi"], "ho_ten": st.session_state["st_name"], 
                    "lop": st.session_state["st_class"], "diem": grade, "so_cau_dung": f"{c_num}/{len(st.session_state['quiz_data'])}",
                    "lop_thi": st.session_state["mon_hoc"], "lop_kiem_tra": st.session_state["lop_kiem_tra"], "ngay_thi": st.session_state["ngay_thi"]
                }).execute()
                st.session_state["is_testing"] = False
                st.success(f"Nộp bài thành công! Điểm: {grade}"); time.sleep(2); st.rerun()

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản trị:", type="password", key="final_admin_pwd")
    if pwd == ADMIN_PASSWORD:
        col1, col2 = st.columns([1, 1.8])
        
        with col1:
            st.subheader("📤 ĐĂNG ĐỀ THI")
            n_ma = st.text_input("Mã đề thi:")
            t_mon = st.text_input("Môn học:")
            t_lop = st.text_input("Lớp kiểm tra:")
            t_gian = st.number_input("Thời gian (phút):", min_value=1, value=15)
            d_thi = st.date_input("Ngày thi:")
            f_word = st.file_uploader("Tải tệp Word:", type=["docx"])
            if st.button("🚀 Kích hoạt đề"):
                if n_ma and t_mon and t_lop and f_word:
                    d_js = parse_docx_simple(f_word)
                    supabase.table("exam_questions").upsert({
                        "ma_de": n_ma, "nội_dung_json": d_js, "ten_mon": t_mon.strip(), "ten_lop": t_lop.strip(), 
                        "ngay_thi": d_thi.strftime("%d/%m/%Y"), "thoi_gian_phut": t_gian
                    }).execute()
                    st.success("Đã đăng đề!"); time.sleep(1); st.rerun()
            
            st.divider()
            st.subheader("🗑️ QUẢN LÝ DỮ LIỆU")
            # Xóa đề thi
            q_res = supabase.table("exam_questions").select("ma_de").execute()
            if q_res.data:
                ma_x = st.selectbox("Chọn mã đề để xóa:", ["-- Chọn --"] + [i['ma_de'] for i in q_res.data])
                if ma_x != "-- Chọn --" and st.button(f"Xác nhận xóa đề {ma_x}"):
                    supabase.table("exam_questions").delete().eq("ma_de", ma_x).execute()
                    st.success(f"Đã xóa đề {ma_x}!"); time.sleep(1); st.rerun()
            
            if st.button("🔥 XÓA TẤT CẢ KẾT QUẢ THI"):
                supabase.table("student_results").delete().neq("id", 0).execute()
                st.success("Đã dọn sạch kết quả!"); st.rerun()

        with col2:
            st.subheader("📊 KẾT QUẢ VÀ XUẤT PHIẾU")
            r_all = supabase.table("student_results").select("*").execute()
            if r_all.data:
                df = pd.DataFrame(r_all.data).sort_values(by="ho_ten")
                df['created_at_vn'] = df['created_at'].apply(format_vietnam_time)
                st.dataframe(df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de"]], use_container_width=True)
                
                s_hs = st.selectbox("🖨️ Chọn học sinh dự kiến in:", ["-- Chọn --"] + df['ho_ten'].tolist())
                if s_hs != "-- Chọn --":
                    hs = df[df['ho_ten'] == s_hs].iloc[0]
                    st.markdown(f"""
                    <div class='printable-card'>
                        <h3 style='text-align: center; color: #1e3a8a;'>PHIẾU MINH CHỨNG KẾT QUẢ KIỂM TRA</h3>
                        <p style='text-align: center;'>Trường THCS Lê Quý Đôn - Tuyên Quang</p>
                        <hr>
                        <table style='width: 100%; font-size: 1.1em; line-height: 2.2em; color: black;'>
                            <tr><td width='40%'><b>Học sinh:</b></td><td>{hs['ho_ten'].upper()}</td></tr>
                            <tr><td><b>Lớp:</b></td><td>{hs['lop']}</td></tr>
                            <tr><td><b>Môn kiểm tra:</b></td><td>{hs['lop_thi']}</td></tr>
                            <tr><td><b>Ngày nộp:</b></td><td>{hs['created_at_vn']}</td></tr>
                            <tr><td><b>Điểm số:</b></td><td><b style='font-size: 1.2em;'>{hs['diem']} điểm ({hs['so_cau_dung']})</b></td></tr>
                        </table>
                        <br><br>
                        <div style='display: flex; justify-content: space-between; text-align: center; color: black;'>
                            <div style='width: 45%;'><b>GIÁO VIÊN BỘ MÔN</b><br><br><br><br>(Ký và ghi rõ họ tên)</div>
                            <div style='width: 45%;'><b>HỌC SINH XÁC NHẬN</b><br><br><br><br>(Ký và ghi rõ họ tên)</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Nút tải file HTML in ấn (Cực kỳ ổn định)
                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <title>In_Phieu_{hs['ho_ten']}</title>
                        <style>
                            body {{ font-family: Arial; padding: 50px; }}
                            .container {{ border: 2px solid #1e3a8a; padding: 40px; border-radius: 10px; max-width: 800px; margin: auto; }}
                            h2 {{ text-align: center; color: #1e3a8a; }}
                            hr {{ border: 1px solid #1e3a8a; }}
                            table {{ width: 100%; line-height: 3em; font-size: 1.2em; }}
                            .footer {{ display: flex; justify-content: space-between; margin-top: 60px; text-align: center; }}
                        </style>
                    </head>
                    <body onload="window.print()">
                        <div class="container">
                            <h2>PHIẾU MINH CHỨNG KẾT QUẢ KIỂM TRA</h2>
                            <p style="text-align: center;">Trường THCS Lê Quý Đôn - Tuyên Quang</p>
                            <hr>
                            <table>
                                <tr><td width="40%"><b>Họ và tên học sinh:</b></td><td>{hs['ho_ten'].upper()}</td></tr>
                                <tr><td><b>Lớp học:</b></td><td>{hs['lop']}</td></tr>
                                <tr><td><b>Môn kiểm tra:</b></td><td>{hs['lop_thi']}</td></tr>
                                <tr><td><b>Ngày nộp bài:</b></td><td>{hs['created_at_vn']}</td></tr>
                                <tr><td><b>Kết quả đạt được:</b></td><td><b>{hs['diem']} điểm ({hs['so_cau_dung']})</b></td></tr>
                            </table>
                            <div class="footer">
                                <div style="width: 45%;"><b>GIÁO VIÊN BỘ MÔN</b><br><br><br><br>(Ký và ghi rõ họ tên)</div>
                                <div style="width: 45%;"><b>HỌC SINH XÁC NHẬN</b><br><br><br><br>(Ký và ghi rõ họ tên)</div>
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                    st.download_button(
                        label=f"🚀 TẢI PHIẾU IN VỀ MÁY",
                        data=html_content,
                        file_name=f"Phieu_In_{hs['ho_ten']}.html",
                        mime="text/html"
                    )
