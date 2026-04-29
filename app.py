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

# --- HÀM PARSER V55 (SẮP XẾP LẠI ĐÁP ÁN TUYỆT ĐỐI) ---
def parse_docx_v55(file):
    doc = Document(file)
    questions = []
    full_text = ""
    for para in doc.paragraphs:
        para_text = ""
        for run in para.runs:
            if run.font.color and run.font.color.rgb and str(run.font.color.rgb) == "FF0000":
                para_text += f" [[RED]]{run.text}[[END]] "
            else:
                para_text += run.text
        full_text += para_text + "\n"
    
    q_blocks = re.split(r'(?i)(Câu\s+\d+[:.])', full_text)
    for i in range(1, len(q_blocks), 2):
        header = q_blocks[i].strip()
        raw_parts = re.split(r'(?i)\b([A-D]\s*[:.])', q_blocks[i+1])
        q_text = raw_parts[0].replace("[[RED]]", "").replace("[[END]]", "").strip()
        
        temp_options = {} 
        ans_key = ""
        
        for j in range(1, len(raw_parts), 2):
            label = raw_parts[j].strip().upper()[0] # A, B, C, hoặc D
            content = raw_parts[j+1]
            # Kiểm tra xem đáp án này có chữ đỏ không
            if "[[RED]]" in content or "[[RED]]" in raw_parts[j]:
                ans_key = label
            
            clean_val = content.replace("[[RED]]", "").replace("[[END]]", "").strip()
            temp_options[label] = clean_val
        
        # SẮP XẾP LẠI THEO THỨ TỰ A -> B -> C -> D
        final_options = []
        for label in sorted(temp_options.keys()): # Đảm bảo A đi trước B, B trước C...
            final_options.append(f"{label}. {temp_options[label]}")
        
        if final_options:
            questions.append({
                "question": f"{header} {q_text}", 
                "options": final_options, 
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
        c1, c2 = st.columns(2)
        with c1: name = st.text_input("👤 Họ và tên:")
        with c2: actual_class = st.text_input("🏫 Lớp (VD: 9A1):")
        
        sel_subject = st.selectbox("📚 Chọn môn học:", options=["-- Chọn môn --"] + subjects)
        filtered_codes = [i['ma_de'] for i in all_exams_data if str(i.get('ten_mon', '')).strip() == sel_subject]
        sel_ma_de = st.selectbox("🔑 Chọn mã đề:", options=["-- Chọn mã đề --"] + filtered_codes)
        
        if st.button("🚀 BẮT ĐẦU LÀM BÀI"):
            if name and actual_class and sel_ma_de != "-- Chọn mã đề --":
                # CHỐNG THI LẠI THEO HỌ TÊN + LỚP + MÃ ĐỀ
                check = supabase.table("student_results").select("id").eq("ho_ten", name).eq("lop", actual_class).eq("ma_de", sel_ma_de).execute()
                if check.data:
                    st.error(f"Thí sinh {name} lớp {actual_class} đã nộp bài mã đề {sel_ma_de} rồi. Không được thi lại!")
                else:
                    ex_res = supabase.table("exam_questions").select("*").eq("ma_de", sel_ma_de).execute()
                    if ex_res.data:
                        inf = ex_res.data[0]
                        st.session_state.update({
                            "quiz_data": inf["nội_dung_json"], "ma_de_dang_thi": sel_ma_de, 
                            "st_name": name, "st_class": actual_class, "is_testing": True, 
                            "mon_hoc": inf.get('ten_mon'), "ngay_thi": inf.get('ngay_thi')
                        })
                        st.rerun()
            else: st.warning("Điền đủ tên, lớp và chọn đề em nhé!")
    else:
        with st.form("quiz_form"):
            st.info(f"Thí sinh: {st.session_state['st_name']} - Lớp: {st.session_state['st_class']}")
            u_choices = {}
            for idx, q in enumerate(st.session_state["quiz_data"]):
                st.write(f"**Câu {idx+1}: {q['question']}**")
                # Sắp xếp hiển thị radio button
                u_choices[idx] = st.radio(f"Chọn:", q['options'], index=None, key=f"q_{idx}", label_visibility="collapsed")
            
            if st.form_submit_button("📤 NỘP BÀI"):
                c_num = 0
                for i, q in enumerate(st.session_state["quiz_data"]):
                    correct_key = str(q.get('answer_key', "")).strip()
                    user_ans = str(u_choices[i]) if u_choices[i] else ""
                    # So sánh ký tự đầu tiên cực kỳ chính xác
                    if correct_key and user_ans.strip().upper().startswith(correct_key):
                        c_num += 1
                
                grade = round((c_num / len(st.session_state["quiz_data"])) * 10, 2)
                supabase.table("student_results").insert({
                    "ma_de": st.session_state["ma_de_dang_thi"], "ho_ten": st.session_state["st_name"], 
                    "lop": st.session_state["st_class"], "diem": grade, "so_cau_dung": f"{c_num}/{len(st.session_state['quiz_data'])}",
                    "lop_thi": st.session_state["mon_hoc"], "ngay_thi": st.session_state["ngay_thi"]
                }).execute()
                st.session_state["is_testing"] = False
                st.success(f"Nộp bài thành công! Em đúng {c_num} câu. Điểm: {grade}")
                time.sleep(2); st.rerun()

with tab_gv:
    if "admin_logged_in" not in st.session_state: st.session_state["admin_logged_in"] = False
    if not st.session_state["admin_logged_in"]:
        pwd_input = st.text_input("Mật khẩu quản trị:", type="password")
        if st.button("Đăng nhập"):
            if pwd_input == ADMIN_PASSWORD: st.session_state["admin_logged_in"] = True; st.rerun()
    else:
        if st.button("🚪 Thoát Quản trị"): st.session_state["admin_logged_in"] = False; st.rerun()
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("📤 ĐĂNG ĐỀ")
            n_ma = st.text_input("Mã đề:"); t_mon = st.text_input("Môn:"); f_word = st.file_uploader("File Word:", type=["docx"])
            if st.button("🚀 CẬP NHẬT ĐỀ"):
                if n_ma and t_mon and f_word:
                    d_js = parse_docx_v55(f_word)
                    supabase.table("exam_questions").upsert({"ma_de": n_ma, "nội_dung_json": d_js, "ten_mon": t_mon, "ngay_thi": datetime.now().strftime("%d/%m/%Y")}).execute()
                    st.success("Đã nạp đề thành công!"); time.sleep(1); st.rerun()
            st.divider()
            if st.button("🧹 XÓA TẤT CẢ KẾT QUẢ"):
                supabase.table("student_results").delete().neq("id", 0).execute(); st.rerun()
            if st.button("❌ XÓA TẤT CẢ ĐỀ"):
                supabase.table("exam_questions").delete().neq("ma_de", "---").execute(); st.rerun()

        with c2:
            st.subheader("📊 BẢNG ĐIỂM")
            res = supabase.table("student_results").select("*").execute()
            if res.data:
                df = pd.DataFrame(res.data).sort_values(by="created_at", ascending=False)
                st.dataframe(df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de"]], use_container_width=True)
                # (Phần in phiếu giữ nguyên)
