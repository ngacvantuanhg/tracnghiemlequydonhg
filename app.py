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

# --- HÀM PARSER V52 (SIÊU CẤP) ---
def parse_docx_v52(file):
    doc = Document(file)
    questions = []
    full_text_with_marks = ""
    for para in doc.paragraphs:
        para_text = ""
        for run in para.runs:
            # Nhận diện chính xác mã màu đỏ chuẩn FF0000
            if run.font.color and run.font.color.rgb and str(run.font.color.rgb) == "FF0000":
                para_text += f" [[RED]]{run.text}[[END]] "
            else:
                para_text += run.text
        full_text_with_marks += para_text + "\n"
    
    q_blocks = re.split(r'(?i)(Câu\s+\d+[:.])', full_text_with_marks)
    for i in range(1, len(q_blocks), 2):
        header = q_blocks[i].strip()
        parts = re.split(r'(?i)\b([A-D]\s*[:.])', q_blocks[i+1])
        question_text = parts[0].replace("[[RED]]", "").replace("[[END]]", "").strip()
        
        options = []
        ans_key = ""
        for j in range(1, len(parts), 2):
            label = parts[j].strip().upper()[0] # A, B, C, D
            content = parts[j+1]
            if "[[RED]]" in content or "[[RED]]" in parts[j]: # Kiểm tra đỏ ở cả chữ cái hoặc nội dung
                ans_key = label
            
            clean_val = content.replace("[[RED]]", "").replace("[[END]]", "").strip()
            options.append(f"{label}. {clean_val}")
        
        if options:
            questions.append({"question": f"{header} {question_text}", "options": options, "answer_key": ans_key})
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
    else:
        with st.form("quiz_form"):
            st.info(f"Thí sinh: {st.session_state['st_name']} | Đề: {st.session_state['ma_de_dang_thi']}")
            u_choices = {}
            for idx, q in enumerate(st.session_state["quiz_data"]):
                st.write(f"**{idx+1}. {q['question']}**")
                u_choices[idx] = st.radio("Chọn:", q['options'], index=None, key=f"q_{idx}", label_visibility="collapsed")
            
            if st.form_submit_button("📤 NỘP BÀI THI"):
                c_num = 0
                for i, q in enumerate(st.session_state["quiz_data"]):
                    correct_key = q.get('answer_key', "").strip()
                    user_ans = u_choices[i] if u_choices[i] else ""
                    if correct_key and user_ans.strip().startswith(correct_key):
                        c_num += 1
                
                grade = round((c_num / len(st.session_state["quiz_data"])) * 10, 2)
                supabase.table("student_results").insert({
                    "ma_de": st.session_state["ma_de_dang_thi"], "ho_ten": st.session_state["st_name"], 
                    "lop": st.session_state["st_class"], "diem": grade, "so_cau_dung": f"{c_num}/{len(st.session_state['quiz_data'])}",
                    "lop_thi": st.session_state["mon_hoc"], "ngay_thi": st.session_state["ngay_thi"]
                }).execute()
                st.session_state["is_testing"] = False
                st.success(f"Xong! {c_num}/{len(st.session_state['quiz_data'])} câu đúng. Điểm: {grade}")
                time.sleep(2); st.rerun()

with tab_gv:
    if "admin_logged_in" not in st.session_state: st.session_state["admin_logged_in"] = False
    if not st.session_state["admin_logged_in"]:
        pwd_input = st.text_input("Nhập mật khẩu quản trị:", type="password")
        if st.button("Đăng nhập"):
            if pwd_input == ADMIN_PASSWORD:
                st.session_state["admin_logged_in"] = True; st.rerun()
    else:
        if st.button("🚪 Thoát Quản trị"):
            st.session_state["admin_logged_in"] = False; st.rerun()
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("📤 ĐĂNG ĐỀ")
            n_ma = st.text_input("Mã đề:"); t_mon = st.text_input("Môn:"); f_word = st.file_uploader("Word:", type=["docx"])
            if st.button("🚀 Kích hoạt"):
                if n_ma and t_mon and f_word:
                    d_js = parse_docx_v52(f_word)
                    supabase.table("exam_questions").upsert({"ma_de": n_ma, "nội_dung_json": d_js, "ten_mon": t_mon, "ngay_thi": datetime.now().strftime("%d/%m/%Y")}).execute()
                    st.success("Đã kích hoạt!"); time.sleep(1); st.rerun()
            st.divider()
            if st.button("🔥 XÓA TẤT CẢ KẾT QUẢ"):
                supabase.table("student_results").delete().neq("id", 0).execute(); st.rerun()

        with c2:
            st.subheader("📊 KẾT QUẢ & IN PHIẾU")
            res = supabase.table("student_results").select("*").execute()
            if res.data:
                df = pd.DataFrame(res.data).sort_values(by="created_at", ascending=False)
                st.dataframe(df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de"]], use_container_width=True)
                s_hs = st.selectbox("🖨️ In phiếu cho:", ["-- Chọn --"] + sorted(df['ho_ten'].tolist()))
                if s_hs != "-- Chọn --":
                    h = df[df['ho_ten'] == s_hs].iloc[0]
                    # PHẦN IN KẾT QUẢ ĐÃ TRỞ LẠI
                    st.markdown(f"""
                    <div style="background: white; padding: 30px; border: 2px solid #1e3a8a; color: black; border-radius: 10px;">
                        <h2 style="text-align:center;">PHIẾU MINH CHỨNG KẾT QUẢ</h2>
                        <hr>
                        <p><b>Học sinh:</b> {h['ho_ten'].upper()} | <b>Lớp:</b> {h['lop']}</p>
                        <p><b>Môn:</b> {h['lop_thi']} | <b>Mã đề:</b> {h['ma_de']}</p>
                        <p><b>Kết quả: {h['diem']} điểm ({h['so_cau_dung']})</b></p>
                        <br><br>
                        <table style="width:100%; text-align:center;">
                            <tr><td><b>GIÁO VIÊN</b><br><br><br>(Ký tên)</td><td><b>HỌC SINH</b><br><br><br>(Ký tên)</td></tr>
                        </table>
                    </div>
                    """, unsafe_allow_html=True)
                    print_html = f"<html><body onload='window.print()'><div style='border:2px solid black; padding:30px; font-family:Arial;'><h2>PHIẾU KẾT QUẢ</h2><p>Học sinh: {h['ho_ten']}</p><p>Điểm: {h['diem']}</p></div></body></html>"
                    st.download_button("📥 TẢI FILE IN", data=print_html.encode('utf-8'), file_name=f"In_{h['ho_ten']}.html", mime="text/html")
