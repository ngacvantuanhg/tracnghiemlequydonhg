import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime
import time

# --- KẾT NỐI HỆ THỐNG ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "141983") 
    supabase = create_client(url, key)
except Exception as e:
    st.error("Lỗi cấu hình Secrets!")
    st.stop()

st.set_page_config(page_title="Hệ Thống Thi Lê Quý Đôn", layout="wide", page_icon="🏫")

# --- STYLE GIAO DIỆN ---
bg_img = "https://raw.githubusercontent.com/ngacvantuanhg/tracnghiemlequydonhg/main/Anhnen.png"
st.markdown(f"""
    <style>
    .stApp {{ background-image: url("{bg_img}"); background-attachment: fixed; background-size: cover; background-position: center; }}
    .main {{ background-color: rgba(255, 255, 255, 0.95); padding: 2rem; border-radius: 20px; }}
    </style>
    """, unsafe_allow_html=True)

# --- BỘ MÁY QUÉT ĐỀ CHUẨN ---
def parse_docx_final(file):
    doc = Document(file)
    questions = []
    full_text = ""
    for para in doc.paragraphs:
        para_text = ""
        for run in para.runs:
            is_ans = False
            if run.font.color and run.font.color.rgb and str(run.font.color.rgb) != "000000": is_ans = True
            elif run.font.highlight_color and str(run.font.highlight_color) != "NONE": is_ans = True
            if is_ans: para_text += f" [[DUNG]]{run.text}[[HET]] "
            else: para_text += run.text
        full_text += para_text + "\n"

    q_blocks = re.split(r'(?i)(Câu\s+\d+[:.])', full_text)
    for i in range(1, len(q_blocks), 2):
        header = q_blocks[i].strip()
        content = q_blocks[i+1]
        content = re.sub(r'\[\[DUNG\]\](\s*[A-D]\s*[:.])', r'\1[[DUNG]]', content, flags=re.IGNORECASE)
        parts = re.split(r'(?i)\b([A-D]\s*[:.])', content)
        
        question_text = parts[0].replace("[[DUNG]]", "").replace("[[HET]]", "").strip()
        options_dict = {}
        final_answer = ""
        for j in range(1, len(parts), 2):
            label = parts[j].strip().upper()[0]
            text = parts[j+1]
            if "[[DUNG]]" in text or "[[DUNG]]" in parts[j]: final_answer = label
            clean_text = text.replace("[[DUNG]]", "").replace("[[HET]]", "").strip()
            if clean_text: options_dict[label] = f"{label}. {clean_text}"
        
        sorted_options = [options_dict[k] for k in sorted(options_dict.keys())]
        if sorted_options: questions.append({"question": f"{header} {question_text}", "options": sorted_options, "answer_key": final_answer})
    return questions

# --- TIÊU ĐỀ CHÍNH & PHỤ ---
st.markdown("""
    <h1 style='text-align:center; color:#1e3a8a; font-weight: bold; margin-bottom: 5px;'>HỆ THỐNG THI LÊ QUÝ ĐÔN</h1>
    <h4 style='text-align:center; color:#475569; font-weight: normal; margin-top: 0px;'>Trường THCS Lê Quý Đôn, phường Hà Giang 1, tỉnh Tuyên Quang</h4>
    """, unsafe_allow_html=True)

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])

with tab_hs:
    res_exams = supabase.table("exam_questions").select("ten_mon, ma_de, giao_vien, ngay_thi").execute()
    all_exams_data = res_exams.data if res_exams.data else []
    subjects = sorted(list(set([str(i.get('ten_mon', '')).strip() for i in all_exams_data if str(i.get('ten_mon', '')).strip() != ''])))

    if not st.session_state.get("is_testing", False):
        st.subheader("📝 Đăng ký dự thi")
        c1, c2 = st.columns(2)
        with c1: name = st.text_input("👤 Họ và tên:").strip().title()
        with c2: actual_class = st.text_input("🏫 Lớp:").strip().upper()
        
        sel_subject = st.selectbox("📚 Chọn môn học:", options=["-- Chọn môn --"] + subjects)
        filtered_codes = [i['ma_de'] for i in all_exams_data if str(i.get('ten_mon', '')).strip() == sel_subject and str(i.get('ma_de', '')).strip() != '']
        sel_ma_de = st.selectbox("🔑 Chọn mã đề:", options=["-- Chọn mã đề --"] + filtered_codes)
        
        if st.button("🚀 BẮT ĐẦU LÀM BÀI"):
            if name and actual_class and sel_ma_de != "-- Chọn mã đề --":
                check = supabase.table("student_results").select("id").eq("ho_ten", name).eq("lop", actual_class).eq("ma_de", sel_ma_de).execute()
                if len(check.data) > 0:
                    st.error(f"⚠️ Em {name} (Lớp {actual_class}) đã nộp bài rồi. Không được thi lại!")
                else:
                    ex_res = supabase.table("exam_questions").select("*").eq("ma_de", sel_ma_de).execute()
                    if ex_res.data:
                        inf = ex_res.data[0]
                        st.session_state.update({
                            "quiz_data": inf["nội_dung_json"], "ma_de_dang_thi": sel_ma_de, 
                            "st_name": name, "st_class": actual_class, "is_testing": True, 
                            "mon_hoc": inf.get('ten_mon'), "ngay_thi": inf.get('ngay_thi', ''),
                            "giao_vien": inf.get('giao_vien', '')
                        })
                        st.rerun()
            else: st.warning("Vui lòng điền đủ thông tin!")
    else:
        with st.form("quiz_form"):
            st.info(f"Thí sinh: {st.session_state['st_name']} - Lớp: {st.session_state['st_class']}")
            u_choices = {}
            for idx, q in enumerate(st.session_state["quiz_data"]):
                st.write(f"**{q['question']}**")
                u_choices[idx] = st.radio("Chọn:", q['options'], index=None, key=f"q_{idx}", label_visibility="collapsed")
            
            if st.form_submit_button("📤 NỘP BÀI"):
                c_num = 0
                for i, q in enumerate(st.session_state["quiz_data"]):
                    correct_key = str(q.get('answer_key', "")).strip().upper()
                    user_ans = str(u_choices[i]).strip().upper() if u_choices[i] else ""
                    if correct_key and user_ans.startswith(correct_key): c_num += 1
                
                grade = round((c_num / len(st.session_state["quiz_data"])) * 10, 2)
                supabase.table("student_results").insert({
                    "ma_de": st.session_state["ma_de_dang_thi"], "ho_ten": st.session_state["st_name"], 
                    "lop": st.session_state["st_class"], "diem": grade, "so_cau_dung": f"{c_num}/{len(st.session_state['quiz_data'])}",
                    "lop_thi": st.session_state["mon_hoc"], "ngay_thi": st.session_state["ngay_thi"],
                    "giao_vien": st.session_state.get("giao_vien", "")
                }).execute()
                st.session_state["is_testing"] = False
                st.success(f"Nộp bài thành công! Điểm: {grade}")
                time.sleep(2); st.rerun()

with tab_gv:
    if "admin_logged_in" not in st.session_state: st.session_state["admin_logged_in"] = False
    if not st.session_state["admin_logged_in"]:
        pwd_input = st.text_input("Mật khẩu quản trị:", type="password")
        if st.button("Đăng nhập"):
            if pwd_input == ADMIN_PASSWORD: st.session_state["admin_logged_in"] = True; st.rerun()
    else:
        if st.button("🚪 Thoát Quản trị"): st.session_state["admin_logged_in"] = False; st.rerun()
        c1, c2 = st.columns([1.2, 2])
        with c1:
            st.subheader("📤 QUẢN LÝ ĐỀ")
            n_ma = st.text_input("Mã đề:").strip()
            t_mon = st.text_input("Môn học:").strip()
            t_gv = st.text_input("Giáo viên coi thi (In lên phiếu):").strip().title()
            d_thi = st.date_input("Ngày thi:") # ĐÃ BỔ SUNG NGÀY THI
            f_word = st.file_uploader("File Word:", type=["docx"])
            
            if st.button("🚀 CẬP NHẬT ĐỀ"):
                if n_ma and t_mon and t_gv and f_word:
                    d_js = parse_docx_final(f_word)
                    supabase.table("exam_questions").upsert({
                        "ma_de": n_ma, "nội_dung_json": d_js, "ten_mon": t_mon, 
                        "giao_vien": t_gv, "ngay_thi": d_thi.strftime("%d/%m/%Y") # Lưu Ngày thi
                    }).execute()
                    st.success(f"Đã nạp đề {n_ma} thành công!")
                    ans_preview = [f"C{i+1}: {q.get('answer_key', 'LỖI')}" for i, q in enumerate(d_js)]
                    st.info(f"🔍 **Máy tính nhận diện đáp án:**\n\n" + " | ".join(ans_preview))
                else:
                    st.error("Cần nhập đủ Mã đề, Môn học, Tên Giáo viên và File Word!")
                    
            st.divider()
            if st.button("❌ XÓA TẤT CẢ ĐỀ THI"):
                try:
                    supabase.table("exam_questions").delete().neq("ma_de", "DUMMY").execute()
                    st.success("Đã xóa sạch đề thi!")
                    time.sleep(1); st.rerun()
                except: st.warning("Vào trang Supabase -> Table Editor -> exam_questions để xóa.")
                    
            if st.button("🧹 XÓA TẤT CẢ KẾT QUẢ THI"):
                try:
                    supabase.table("student_results").delete().neq("id", 0).execute()
                    st.success("Đã xóa sạch bảng điểm!")
                    time.sleep(1); st.rerun()
                except: st.warning("Vào trang Supabase -> Table Editor -> student_results để xóa.")

        with c2:
            st.subheader("📊 BẢNG ĐIỂM")
            res = supabase.table("student_results").select("*").execute()
            if res.data:
                df = pd.DataFrame(res.data).sort_values(by="created_at", ascending=False)
                # HIỂN THỊ THÊM NGÀY THI VÀO BẢNG
                st.dataframe(df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de", "ngay_thi"]], use_container_width=True)
                
                s_hs = st.selectbox("🖨️ In phiếu cho:", ["-- Chọn --"] + sorted(df['ho_ten'].unique().tolist()))
                if s_hs != "-- Chọn --":
                    h = df[df['ho_ten'] == s_hs].iloc[0]
                    ten_gv_in = str(h['giao_vien']).upper() if 'giao_vien' in h and h['giao_vien'] else ""
                    ten_hs_in = str(h['ho_ten']).upper()
                    ngay_thi_in = str(h['ngay_thi']) if 'ngay_thi' in h and h['ngay_thi'] else ""
                    
                    # PHIẾU IN TRÊN WEB (CÓ NGÀY THI)
                    st.markdown(f"""
                    <div style="background: white; padding: 25px; border: 2px solid #1e3a8a; color: black; border-radius: 10px;">
                        <h2 style="text-align:center;">PHIẾU XÁC NHẬN KẾT QUẢ</h2>
                        <hr>
                        <p><b>Thí sinh:</b> {h['ho_ten'].upper()} &nbsp;&nbsp; <b>Lớp:</b> {h['lop']}</p>
                        <p><b>Môn thi:</b> {h['lop_thi']} &nbsp;&nbsp; <b>Mã đề:</b> {h['ma_de']}</p>
                        <p><b>Ngày thi:</b> {ngay_thi_in} &nbsp;&nbsp; <b>Điểm số: <span style="color:red;">{h['diem']}</span></b> ({h['so_cau_dung']} câu đúng)</p>
                        <br><br>
                        <table style="width:100%; text-align:center;">
                            <tr>
                                <td style="width:50%;"><b>GIÁO VIÊN</b><br><br><br><br><br><b>{ten_gv_in}</b></td>
                                <td style="width:50%;"><b>HỌC SINH</b><br><br><br><br><br><b>{ten_hs_in}</b></td>
                            </tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # FILE HTML TẢI VỀ IN (CÓ NGÀY THI)
                    print_html = f"""
                    <html>
                    <body onload='window.print()'>
                        <div style='border:2px solid black; padding:40px; font-family:Arial;'>
                            <h2 style='text-align:center;'>PHIẾU XÁC NHẬN KẾT QUẢ</h2>
                            <p style='text-align:center;'>Trường THCS Lê Quý Đôn, phường Hà Giang 1, tỉnh Tuyên Quang</p>
                            <hr>
                            <table style='width:100%; line-height:2.5em; font-size: 1.1em;'>
                                <tr><td width="30%"><b>Thí sinh:</b></td><td>{h['ho_ten'].upper()}</td></tr>
                                <tr><td><b>Lớp:</b></td><td>{h['lop']}</td></tr>
                                <tr><td><b>Môn thi:</b></td><td>{h['lop_thi']}</td></tr>
                                <tr><td><b>Mã đề:</b></td><td>{h['ma_de']}</td></tr>
                                <tr><td><b>Ngày thi:</b></td><td>{ngay_thi_in}</td></tr>
                                <tr><td><b>Điểm số:</b></td><td><b>{h['diem']}</b> ({h['so_cau_dung']} câu đúng)</td></tr>
                            </table>
                            <br><br><br>
                            <table style='width:100%; text-align:center;'>
                                <tr>
                                    <td style="width:50%;"><b>GIÁO VIÊN</b><br><br><br><br><br><b>{ten_gv_in}</b></td>
                                    <td style="width:50%;"><b>HỌC SINH</b><br><br><br><br><br><b>{ten_hs_in}</b></td>
                                </tr>
                            </table>
                        </div>
                    </body>
                    </html>
                    """
                    st.download_button("📥 TẢI PHIẾU IN", data=print_html.encode('utf-8'), file_name=f"Phieu_{h['ho_ten']}.html", mime="text/html")
