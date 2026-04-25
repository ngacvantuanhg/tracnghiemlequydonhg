import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime
import pytz
import io
import time
from fpdf import FPDF

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
    h1, .sub-title {{ text-align: center !important; color: #1e3a8a !important; }}
    div[data-baseweb="input"], div[data-baseweb="select"] {{
        background-color: #ffffff !important; border: 2px solid #cbd5e1 !important; border-radius: 8px !important;
    }}
    [data-testid="stForm"] {{
        background-color: rgba(255, 255, 255, 0.95); border: 2px solid #1e3a8a;
        border-radius: 15px; padding: 2rem; max-width: 850px; margin: 0 auto !important;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- HÀM TẠO PDF MINH CHỨNG (Dùng thư viện FPDF) ---
def create_pdf_report(hs_name, hs_class, mon, ma_de, ngay, diem, so_cau):
    pdf = FPDF()
    pdf.add_page()
    # Sử dụng font mặc định của FPDF (Helvetica) - Lưu ý: FPDF mặc định không hỗ trợ tiếng Việt có dấu tốt
    # Để in tiếng Việt chuẩn PDF, ta sẽ dùng định dạng bảng đơn giản.
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(200, 10, txt="PHIEU MINH CHUNG KET QUA KIEM TRA", ln=True, align='C')
    pdf.set_font("Helvetica", size=12)
    pdf.cell(200, 10, txt="Truong THCS Le Quy Don - Tuyen Quang", ln=True, align='C')
    pdf.ln(10)
    pdf.line(10, 30, 200, 30)
    
    pdf.set_font("Helvetica", 'B', 12)
    data = [
        ["Ho va ten:", hs_name.upper()],
        ["Lop:", hs_class],
        ["Mon thi:", mon],
        ["Ma de:", ma_de],
        ["Ngay thi:", ngay],
        ["Ket qua:", f"{diem} diem ({so_cau})"]
    ]
    
    pdf.ln(10)
    for row in data:
        pdf.cell(50, 10, txt=row[0], border=0)
        pdf.cell(100, 10, txt=str(row[1]), border=0)
        pdf.ln(8)
        
    pdf.ln(20)
    pdf.cell(90, 10, txt="GIAO VIEN BO MON", align='C')
    pdf.cell(90, 10, txt="HOC SINH XAC NHAN", align='C')
    pdf.ln(5)
    pdf.set_font("Helvetica", 'I', 10)
    pdf.cell(90, 10, txt="(Ky va ghi ro ho ten)", align='C')
    pdf.cell(90, 10, txt="(Ky va ghi ro ho ten)", align='C')
    
    return pdf.output(dest='S').encode('latin-1')

# --- HÀM HỖ TRỢ KHÁC (Giữ nguyên) ---
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
        if sorted_options: questions.append({"question": f"{header} {question_text}", "options": sorted_options, "answer_key": ans_k})
    return questions

# --- GIAO DIỆN ---
st.markdown("<h1>HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Trường THCS Lê Quý Đôn, phường Hà Giang 1, tỉnh Tuyên Quang</div>", unsafe_allow_html=True)

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
                st.success(f"Nộp bài thành công! Điểm: {grade}"); time.sleep(2); st.rerun()

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản lý:", type="password", key="gv_pwd")
    if pwd == ADMIN_PASSWORD:
        col1, col2 = st.columns([1, 1.8])
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
            st.subheader("📊 KẾT QUẢ & XUẤT PHIẾU")
            res_all = supabase.table("student_results").select("*").execute()
            if res_all.data:
                df = pd.DataFrame(res_all.data).sort_values(by="ho_ten")
                st.dataframe(df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de"]], use_container_width=True)
                
                st.write("---")
                sel_hs = st.selectbox("🖨️ Chọn học sinh tải Phiếu minh chứng:", ["-- Chọn --"] + df['ho_ten'].tolist())
                if sel_hs != "-- Chọn --":
                    hs = df[df['ho_ten'] == sel_hs].iloc[0]
                    
                    # Nút tải PDF trực tiếp
                    try:
                        pdf_data = create_pdf_report(hs['ho_ten'], hs['lop'], hs['lop_thi'], hs['ma_de'], hs['ngay_thi'], hs['diem'], hs['so_cau_dung'])
                        st.download_button(
                            label=f"📥 Tải Phiếu Minh Chứng ({hs['ho_ten']})",
                            data=pdf_data,
                            file_name=f"Phieu_Diem_{hs['ho_ten']}.pdf",
                            mime="application/pdf"
                        )
                        st.success("Bấm nút trên để tải file PDF về máy và in nhé!")
                    except Exception as e:
                        st.error(f"Lỗi tạo PDF: {e}")
