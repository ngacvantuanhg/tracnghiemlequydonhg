import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime
import pytz
import time

# --- KẾT NỐI HỆ THỐNG ---
# Bảo mật: Lấy mật khẩu và cấu hình từ secrets
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

# --- STYLE GIAO DIỆN TỐI ƯU ---
st.markdown(f"""
    <style>
    .stApp {{ background-image: url("{bg_img}"); background-attachment: fixed; background-size: cover; background-position: center; }}
    .main {{ background-color: rgba(255, 255, 255, 0.85); padding: 2rem; border-radius: 20px; }}
    h1, .sub-title {{ text-align: center !important; color: #1e3a8a !important; font-family: 'Arial'; }}
    div[data-baseweb="input"], div[data-baseweb="select"] {{
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

def clean_text(text):
    """Validate dữ liệu đầu vào, loại bỏ ký tự nguy hiểm"""
    return re.sub(r'[^\w\s\dÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠàáâãèéêìíòóôõùúăđĩũơƯĂÂÊÔƠƯưăâêôơư]', '', str(text)).strip()

def parse_docx_simple(file):
    try:
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
    except:
        st.error("Lỗi định dạng file Word. Vui lòng kiểm tra lại!")
        return []

# --- GIAO DIỆN CHÍNH ---
st.markdown("<h1>HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Trường THCS Lê Quý Đôn, phường Hà Giang 1, tỉnh Tuyên Quang</div>", unsafe_allow_html=True)

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])

with tab_hs:
    # Tối ưu: Lấy danh sách đề thi một lần duy nhất
    if "all_exams" not in st.session_state:
        res = supabase.table("exam_questions").select("ten_mon, ma_de").execute()
        st.session_state.all_exams = res.data if res.data else []

    all_exams = st.session_state.all_exams
    subjects = sorted(list(set([str(item.get('ten_mon', '')).strip() for item in all_exams if item.get('ten_mon')])))

    if not st.session_state.get("is_testing", False):
        with st.form("info_form"):
            st.subheader("📝 Đăng ký thông tin dự thi")
            name = st.text_input("👤 Họ và Tên của em:")
            actual_class = st.text_input("🏫 Lớp của em:")
            sel_subject = st.selectbox("📚 Chọn Môn học:", options=["-- Chọn môn --"] + subjects)
            
            # Logic lọc mã đề nhạy bén
            filtered_codes = [item['ma_de'] for item in all_exams if str(item.get('ten_mon', '')).strip() == sel_subject]
            sel_ma_de = st.selectbox("🔑 Chọn Mã đề thi:", options=["-- Chọn mã đề --"] + filtered_codes)
            
            if st.form_submit_button("🚀 BẮT ĐẦU LÀM BÀI"):
                v_name = clean_text(name)
                v_class = clean_text(actual_class)
                
                if v_name and v_class and sel_subject != "-- Chọn môn --" and sel_ma_de != "-- Chọn mã đề --":
                    # Kiểm tra xem học sinh đã thi mã đề này chưa (Chống gian lận)
                    check_exists = supabase.table("student_results").select("id").eq("ho_ten", v_name).eq("lop", v_class).eq("ma_de", sel_ma_de).execute()
                    if check_exists.data:
                        st.error("⚠️ Em đã nộp bài thi cho mã đề này rồi!")
                    else:
                        ex_res = supabase.table("exam_questions").select("*").eq("ma_de", sel_ma_de).execute()
                        if ex_res.data:
                            ex_info = ex_res.data[0]
                            st.session_state.update({
                                "quiz_data": ex_info["nội_dung_json"], "ma_de_dang_thi": sel_ma_de, 
                                "st_name": v_name, "st_class": v_class, "is_testing": True, 
                                "mon_hoc": ex_info.get('ten_mon'), "lop_thi": ex_info.get('ten_lop'), "ngay_thi": ex_info.get('ngay_thi')
                            })
                            st.rerun()
                else: st.error("❌ Vui lòng điền đủ thông tin!")
    else:
        # PHÒNG THI (Đã bỏ đếm ngược thời gian)
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
                    "lop_thi": st.session_state["mon_hoc"], "ngay_thi": st.session_state["ngay_thi"]
                }).execute()
                
                st.session_state["is_testing"] = False
                st.success(f"Nộp bài thành công! Điểm: {grade}")
                time.sleep(2)
                st.rerun()

with tab_gv:
    # Quản trị (Dùng secrets để bảo mật mật khẩu)
    pwd = st.text_input("🔐 Mật khẩu quản trị:", type="password")
    if pwd == ADMIN_PASSWORD:
        col1, col2 = st.columns([1, 1.8])
        with col1:
            st.subheader("📤 ĐĂNG ĐỀ THI")
            n_ma = clean_text(st.text_input("Mã đề thi:"))
            t_mon = st.text_input("Môn học:")
            t_lop = st.text_input("Lớp kiểm tra:")
            t_gian = st.number_input("Thời gian (phút):", 1, 180, 15)
            f_word = st.file_uploader("Tải tệp Word:", type=["docx"])
            if st.form_submit_button if False else st.button("🚀 Kích hoạt đề"):
                if n_ma and t_mon and f_word:
                    d_js = parse_docx_simple(f_word)
                    if d_js:
                        supabase.table("exam_questions").upsert({
                            "ma_de": n_ma, "nội_dung_json": d_js, "ten_mon": t_mon.strip(), 
                            "ten_lop": t_lop.strip(), "ngay_thi": datetime.now().strftime("%d/%m/%Y"), "thoi_gian_phut": t_gian
                        }).execute()
                        st.session_state.pop("all_exams", None) # Clear cache để cập nhật mã đề mới
                        st.success("Đã đăng đề!"); time.sleep(1); st.rerun()

        with col2:
            st.subheader("📊 KẾT QUẢ & IN PHIẾU")
            # Tối ưu: Chỉ load kết quả khi cần (hoặc dùng pagination nếu dữ liệu quá lớn)
            res_all = supabase.table("student_results").select("*").limit(1000).execute()
            if res_all.data:
                df = pd.DataFrame(res_all.data).sort_values(by="ho_ten")
                df['created_at_vn'] = df['created_at'].apply(format_vietnam_time)
                st.dataframe(df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de"]], use_container_width=True)
                
                s_hs = st.selectbox("🖨️ Chọn học sinh in phiếu:", ["-- Chọn --"] + df['ho_ten'].tolist())
                if s_hs != "-- Chọn --":
                    hs = df[df['ho_ten'] == s_hs].iloc[0]
                    # Nội dung HTML để in ấn cực ổn định
                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head><meta charset="utf-8"><style>
                        body {{ font-family: Arial; padding: 50px; }}
                        .container {{ border: 2px solid #1e3a8a; padding: 40px; border-radius: 10px; max-width: 800px; margin: auto; }}
                        h2 {{ text-align: center; color: #1e3a8a; }}
                        table {{ width: 100%; line-height: 3em; font-size: 1.2em; }}
                    </style></head>
                    <body onload="window.print()">
                        <div class="container">
                            <h2>PHIẾU MINH CHỨNG KẾT QUẢ KIỂM TRA</h2>
                            <p style="text-align: center;">Trường THCS Lê Quý Đôn - Tuyên Quang</p>
                            <hr>
                            <table>
                                <tr><td width="40%"><b>Học sinh:</b></td><td>{hs['ho_ten'].upper()}</td></tr>
                                <tr><td><b>Lớp học:</b></td><td>{hs['lop']}</td></tr>
                                <tr><td><b>Môn kiểm tra:</b></td><td>{hs['lop_thi']}</td></tr>
                                <tr><td><b>Ngày nộp:</b></td><td>{hs['created_at_vn']}</td></tr>
                                <tr><td><b>Kết quả:</b></td><td><b>{hs['diem']} điểm ({hs['so_cau_dung']})</b></td></tr>
                            </table>
                            <div style="display: flex; justify-content: space-between; margin-top: 60px; text-align: center;">
                                <div><b>GIÁO VIÊN</b><br><br><br>(Ký tên)</div>
                                <div><b>HỌC SINH</b><br><br><br>(Ký tên)</div>
                            </div>
                        </div>
                    </body></html>
                    """
                    st.download_button(label=f"🚀 TẢI PHIẾU IN ({hs['ho_ten']})", data=html_content, file_name=f"Phieu_In_{hs['ho_ten']}.html", mime="text/html")
