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

# --- STYLE GIAO DIỆN V32 (Ổn định & Sang trọng) ---
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
    .info-box {{
        position: fixed; top: 20px; right: 20px; padding: 10px 20px; 
        background: #1e3a8a; color: white; border-radius: 10px;
        z-index: 9999; text-align: center; border: 2px solid white;
    }}
    @media print {{
        header, footer, .stTabs, [data-testid="stHeader"], [data-testid="stSidebar"], .no-print, button, .stButton {{ display: none !important; }}
        .main {{ background: white !important; padding: 0 !important; }}
        .print-area {{ display: block !important; color: black !important; }}
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
            val = parts[j+1].replace('[[DUNG]]', '').replace('[[HET]]', '').strip()
            if "[[DUNG]]" in parts[j+1]: final_answer = f"{label}. {val}"
            options_dict[label] = f"{label}. {val}"
        sorted_options = [options_dict[k] for k in sorted(options_dict.keys())]
        if sorted_options: questions.append({"question": f"{header} {question_text}", "options": sorted_options, "answer": final_answer})
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
                            "quiz_data": ex_info["nội_dung_json"],
                            "time_limit": ex_info.get('thoi_gian_phut', 15),
                            "ma_de_dang_thi": sel_ma_de, "st_name": name, "st_class": actual_class,
                            "is_testing": True, "mon": ex_info.get('ten_lop'), "ngay": ex_info.get('ngay_thi')
                        })
                        st.rerun()
                else: st.error("❌ Em điền đủ thông tin nhé!")
    else:
        # CHỈ HIỆN THÔNG TIN THỜI GIAN CỐ ĐỊNH (Không chạy giây để tránh treo máy)
        st.markdown(f'<div class="info-box no-print">⏱️ THỜI GIAN<br><b style="font-size:22px;">{st.session_state["time_limit"]} PHÚT</b></div>', unsafe_allow_html=True)
        
        with st.form("quiz_form"):
            st.info(f"👨‍🎓: **{st.session_state['st_name'].upper()}** | Lớp: **{st.session_state['st_class']}** | Môn: **{st.session_state['mon']}**")
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
                b_lam = []
                for i, q in enumerate(st.session_state["quiz_data"]):
                    ch = u_choices[i] if u_choices[i] else "Chưa chọn"
                    b_lam.append(f"{i+1}:{ch}")
                    ans_correct = q.get('answer', "")
                    if u_choices[i] and len(ans_correct) > 0 and u_choices[i].startswith(ans_correct[0]):
                        c_num += 1
                
                grade = round((c_num / len(st.session_state["quiz_data"])) * 10, 2)
                supabase.table("student_results").insert({
                    "ma_de": st.session_state["ma_de_dang_thi"], "ho_ten": st.session_state["st_name"], 
                    "lop": st.session_state["st_class"], "diem": grade, "so_cau_dung": f"{c_num}/{len(st.session_state['quiz_data'])}",
                    "lop_thi": st.session_state["mon"], "ngay_thi": st.session_state["ngay"], "chi_tiet_bai_lam": ",".join(b_lam)
                }).execute()
                
                st.session_state["is_testing"] = False
                if grade >= 8: st.balloons()
                st.success(f"Nộp bài thành công! Điểm của em là: {grade}"); time.sleep(3); st.rerun()

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
                    d_js = parse_docx_smart(f_word)
                    supabase.table("exam_questions").upsert({"ma_de": n_ma, "nội_dung_json": d_js, "ten_lop": t_mon, "ngay_thi": d_thi.strftime("%d/%m/%Y"), "thoi_gian_phut": t_gian}).execute()
                    st.success("Đã đăng đề!"); st.rerun()
            st.divider()
            ex_res = supabase.table("exam_questions").select("ma_de").execute()
            if ex_res.data:
                ma_xoa = st.selectbox("Xóa đề:", ["-- Chọn --"] + [i['ma_de'] for i in ex_res.data])
                if ma_xoa != "-- Chọn --" and st.button(f"Xác nhận xóa {ma_xoa}"):
                    supabase.table("student_results").delete().eq("ma_de", ma_xoa).execute()
                    supabase.table("exam_questions").delete().eq("ma_de", ma_xoa).execute()
                    st.success("Đã xóa!"); st.rerun()

        with col2:
            st.subheader("📊 KẾT QUẢ & IN PHIẾU")
            res_all = supabase.table("student_results").select("*").execute()
            if res_all.data:
                df = pd.DataFrame(res_all.data); df['created_at'] = df['created_at'].apply(format_vietnam_time)
                st.dataframe(df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de"]], use_container_width=True)
                
                st.write("---")
                sel_hs = st.selectbox("🖨️ Chọn học sinh in phiếu:", ["-- Chọn --"] + sorted(df['ho_ten'].tolist()))
                if sel_hs != "-- Chọn --":
                    hs = df[df['ho_ten'] == sel_hs].iloc[0]
                    de = supabase.table("exam_questions").select("nội_dung_json").eq("ma_de", hs['ma_de']).execute()
                    if de.data:
                        quiz_js = de.data[0]['nội_dung_json']
                        chi_tiet = dict(i.split(":") for i in hs['chi_tiet_bai_lam'].split(","))
                        
                        st.markdown(f"""
                        <div class="print-area" style="background: white; padding: 25px; border: 2px solid #1e3a8a; color: black !important;">
                            <h2 style="text-align: center; color: #1e3a8a;">PHIẾU MINH CHỨNG KẾT QUẢ</h2>
                            <p style="text-align: center;">Trường THCS Lê Quý Đôn - Tuyên Quang</p>
                            <hr>
                            <table style="width: 100%; color: black;">
                                <tr><td><b>Học sinh:</b> {hs['ho_ten'].upper()}</td><td><b>Lớp:</b> {hs['lop']}</td></tr>
                                <tr><td><b>Môn thi:</b> {hs['lop_thi']}</td><td><b>Mã đề:</b> {hs['ma_de']}</td></tr>
                                <tr><td><b>Ngày nộp:</b> {hs['created_at']}</td><td><b>Điểm: {hs['diem']} ({hs['so_cau_dung']})</b></td></tr>
                            </table>
                            <hr>
                        """, unsafe_allow_html=True)
                        for i, q in enumerate(quiz_js):
                            ec = chi_tiet.get(str(i+1), "Chưa chọn")
                            d_dung = q.get('answer', "Không có đáp án")
                            # So sánh ký tự đầu tiên
                            is_right = (ec != "Chưa chọn" and len(d_dung) > 0 and ec[0] == d_dung[0])
                            icon = "✅ Đúng" if is_right else f"❌ Sai (Đáp án đúng: <b>{d_dung}</b>)"
                            st.markdown(f"""
                            <div style="color: black !important; border-bottom: 1px dashed #ccc; padding: 10px 0;">
                                <b>Câu {i+1}:</b> {q['question']}<br>
                                👉 Em chọn: <b>{ec}</b> | Kết quả: {icon}
                            </div>
                            """, unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                        st.info("💡 Nhấn Ctrl + P để in phiếu minh chứng này.")
