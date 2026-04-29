import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime
import pytz
import time

# ============================================================
# KẾT NỐI & CẤU HÌNH
# ============================================================
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

st.set_page_config(
    page_title="Hệ Thống Thi Lê Quý Đôn",
    layout="wide",
    page_icon="🏫"
)

ADMIN_PASSWORD = "141983"
BG_IMG = "https://raw.githubusercontent.com/ngacvantuanhg/tracnghiemlequydonhg/main/Anhnen.png"

# ============================================================
# STYLE
# ============================================================
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&display=swap');
    .stApp {{
        background-image: url("{BG_IMG}");
        background-attachment: fixed;
        background-size: cover;
        background-position: center;
    }}
    [data-testid="stForm"] {{
        background-color: rgba(255,255,255,0.96) !important;
        border: 2px solid #1e3a8a;
        border-radius: 16px;
        padding: 2rem;
        max-width: 860px;
        margin: 0 auto;
    }}
    h1, .sub-title {{ text-align: center; color: #1e3a8a; }}
    .timer-box {{
        position: sticky; top: 0; z-index: 999;
        background: linear-gradient(135deg, #1e3a8a, #2563eb);
        color: white; text-align: center; padding: 12px; border-radius: 12px;
        font-size: 1.45em; font-weight: 700; margin-bottom: 16px;
    }}
    .timer-warning {{ background: linear-gradient(135deg, #dc2626, #ef4444) !important; animation: pulse 1s infinite; }}
    @keyframes pulse {{ 0%,100% {{opacity:1}} 50% {{opacity:0.8}} }}
    .result-box {{
        background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
        border: 2px solid #0284c7; border-radius: 14px; padding: 25px; text-align: center;
    }}
    .score-big {{ font-size: 3.2em; font-weight: 700; }}
    .ans-correct {{ background: #dcfce7; border-left: 5px solid #16a34a; padding: 10px; border-radius: 6px; margin: 8px 0; }}
    .ans-wrong   {{ background: #fee2e2; border-left: 5px solid #dc2626; padding: 10px; border-radius: 6px; margin: 8px 0; }}
    .ans-skip    {{ background: #f3f4f6; border-left: 5px solid #9ca3af; padding: 10px; border-radius: 6px; margin: 8px 0; }}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HÀM HỖ TRỢ
# ============================================================
def format_vietnam_time(utc_str):
    try:
        utc_dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
        return utc_dt.astimezone(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%H:%M:%S %d/%m/%Y")
    except:
        return utc_str

def _is_red(run):
    try:
        if run.font.color and run.font.color.rgb:
            return str(run.font.color.rgb).upper() in {"FF0000", "EE0000", "DC143C", "FF4D4D"}
    except:
        pass
    return False

def parse_docx(file):
    """Phiên bản ổn định hơn để đọc đáp án tô màu đỏ"""
    doc = Document(file)
    questions = []
    q_text = None
    options = {}
    ans_key = ""

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        if re.match(r'(?i)^Câu\s+\d+[:.)]', text):
            if q_text and options and ans_key:
                sorted_opts = [f"{k}. {options[k]}" for k in sorted(options.keys())]
                questions.append({
                    "question": q_text,
                    "options": sorted_opts,
                    "answer_key": ans_key
                })
            q_text = text
            options = {}
            ans_key = ""
            continue

        # Thu thập text màu đỏ
        red_text = "".join([run.text for run in para.runs if _is_red(run)]).strip()

        # Tìm các đáp án A. B. C. D.
        matches = re.findall(r'([A-D])[.)]\s*(.+?)(?=\s+[A-D][.)]|\Z)', text, re.IGNORECASE | re.DOTALL)
        
        for label, content in matches:
            label = label.upper()
            content = content.strip()
            options[label] = content
            
            full_ans = f"{label}. {content}"
            if label in red_text or full_ans in red_text or content in red_text:
                ans_key = label

    # Flush câu cuối
    if q_text and options and ans_key:
        sorted_opts = [f"{k}. {options[k]}" for k in sorted(options.keys())]
        questions.append({
            "question": q_text,
            "options": sorted_opts,
            "answer_key": ans_key
        })

    return questions


def calc_score(quiz, choices):
    correct = 0
    for i, q in enumerate(quiz):
        chosen = choices.get(i, "")
        key = q.get("answer_key", "")
        if chosen and key and chosen.startswith(f"{key}."):
            correct += 1
    total = len(quiz)
    grade = round((correct / total) * 10, 2) if total else 0
    return correct, grade


# ============================================================
# GIAO DIỆN
# ============================================================
st.markdown("<h1>🏫 HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title' style='font-size:1.1em'>Trường THCS Lê Quý Đôn – Phường Hà Giang 1 – Tỉnh Tuyên Quang</p>", unsafe_allow_html=True)

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])

# ====================== TAB HỌC SINH ======================
with tab_hs:
    exams = supabase.table("exam_questions").select("ten_mon, ma_de, thoi_gian_phut").execute().data or []
    subjects = sorted(set(e.get("ten_mon", "") for e in exams if e.get("ten_mon")))

    ss = st.session_state

    if not ss.get("is_testing") and not ss.get("show_result"):
        with st.form("info_form"):
            st.subheader("📝 Đăng ký thông tin dự thi")
            name = st.text_input("👤 Họ và Tên của em:")
            st_class = st.text_input("🏫 Lớp của em:")
            sel_subject = st.selectbox("📚 Chọn Môn học:", ["-- Chọn môn --"] + subjects)
            filtered = [e["ma_de"] for e in exams if e.get("ten_mon") == sel_subject]
            sel_ma_de = st.selectbox("🔑 Chọn Mã đề thi:", ["-- Chọn mã đề --"] + filtered)

            if st.form_submit_button("🚀 BẮT ĐẦU LÀM BÀI", use_container_width=True):
                if name and st_class and sel_subject != "-- Chọn môn --" and sel_ma_de != "-- Chọn mã đề --":
                    ex = supabase.table("exam_questions").select("*").eq("ma_de", sel_ma_de).execute()
                    if ex.data:
                        info = ex.data[0]
                        ss.update({
                            "quiz_data": info["nội_dung_json"],
                            "ma_de_dang_thi": sel_ma_de,
                            "st_name": name.strip(),
                            "st_class": st_class.strip(),
                            "is_testing": True,
                            "mon_hoc": info.get("ten_mon"),
                            "lop_kiem_tra": info.get("ten_lop"),
                            "ngay_thi": info.get("ngay_thi"),
                            "start_time": time.time(),
                            "total_seconds": info.get("thoi_gian_phut", 45) * 60,
                            "u_choices": {}
                        })
                        st.rerun()
                else:
                    st.error("❌ Vui lòng điền đầy đủ thông tin!")

    elif ss.get("is_testing"):
        # Timer
        elapsed = time.time() - ss.get("start_time", time.time())
        left = max(0, int(ss.get("total_seconds", 2700) - elapsed))
        
        if left < 300:
            st.markdown(f"<div class='timer-box timer-warning'>⏰ Còn {left//60:02d}:{left%60:02d}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='timer-box'>⏰ Còn {left//60:02d}:{left%60:02d}</div>", unsafe_allow_html=True)

        quiz = ss["quiz_data"]
        choices = ss.get("u_choices", {})

        with st.form("quiz_form"):
            st.markdown(f"### 📖 MÔN: {ss.get('mon_hoc','').upper()}")
            st.info(f"**Học sinh:** {ss['st_name'].upper()} | **Mã đề:** {ss['ma_de_dang_thi']}")
            st.markdown("---")

            for idx, q in enumerate(quiz):
                q_text = re.sub(r'^Câu\s*\d+[:.)]\s*', '', q["question"], flags=re.I)
                st.markdown(f"**Câu {idx+1}.** {q_text}")
                choices[idx] = st.radio("", q["options"], key=f"q_{idx}", label_visibility="collapsed")
                st.markdown("")

            confirmed = st.checkbox("✅ Tôi đã kiểm tra kỹ và muốn nộp bài")
            if st.form_submit_button("📤 NỘP BÀI", use_container_width=True):
                if not confirmed:
                    st.warning("Vui lòng tick xác nhận trước khi nộp!")
                else:
                    c_num, grade = calc_score(quiz, choices)
                    supabase.table("student_results").insert({
                        "ma_de": ss["ma_de_dang_thi"],
                        "ho_ten": ss["st_name"],
                        "lop": ss["st_class"],
                        "diem": grade,
                        "so_cau_dung": f"{c_num}/{len(quiz)}",
                        "lop_thi": ss["mon_hoc"],
                        "lop_kiem_tra": ss.get("lop_kiem_tra"),
                        "ngay_thi": ss["ngay_thi"]
                    }).execute()

                    ss["last_grade"] = grade
                    ss["last_correct"] = c_num
                    ss["last_quiz"] = quiz
                    ss["last_choices"] = choices
                    ss["is_testing"] = False
                    ss["show_result"] = True
                    st.rerun()

    elif ss.get("show_result"):
        grade = ss.get("last_grade", 0)
        c_num = ss.get("last_correct", 0)
        quiz = ss.get("last_quiz", [])
        choices = ss.get("last_choices", {})

        emoji = "🏆" if grade >= 8 else "✅" if grade >= 5 else "📖"
        color = "#15803d" if grade >= 8 else "#0284c7" if grade >= 5 else "#dc2626"

        st.markdown(f"""
        <div class="result-box">
            <div class="score-big" style="color:{color}">{emoji} {grade} điểm</div>
            <p><b>Số câu đúng: {c_num}/{len(quiz)}</b></p>
            <p>Học sinh: <b>{ss.get('st_name','')}</b> | Lớp: <b>{ss.get('st_class','')}</b></p>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("🔍 Xem đáp án chi tiết"):
            for idx, q in enumerate(quiz):
                chosen = choices.get(idx, "")
                key = q.get("answer_key", "")
                correct_opt = next((opt for opt in q["options"] if opt.startswith(f"{key}." )), "Không tìm thấy")
                q_text = re.sub(r'^Câu\s*\d+[:.)]\s*', '', q["question"], flags=re.I)

                st.markdown(f"**Câu {idx+1}.** {q_text}")
                if not chosen:
                    st.markdown(f"<div class='ans-skip'>⬜ Bỏ qua — Đáp án đúng: <b>{correct_opt}</b></div>", unsafe_allow_html=True)
                elif chosen.startswith(f"{key}."):
                    st.markdown(f"<div class='ans-correct'>✅ Đúng: <b>{chosen}</b></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='ans-wrong'>❌ Sai: <b>{chosen}</b><br>→ Đúng: <b>{correct_opt}</b></div>", unsafe_allow_html=True)
                st.markdown("---")

# ====================== TAB QUẢN TRỊ ======================
with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản trị:", type="password")
    if pwd == ADMIN_PASSWORD:
        col1, col2 = st.columns([1, 1.8])
        with col1:
            st.subheader("📤 Đăng đề thi mới")
            n_ma = st.text_input("Mã đề thi")
            t_mon = st.text_input("Môn học")
            t_lop = st.text_input("Lớp kiểm tra")
            t_gian = st.number_input("Thời gian làm bài (phút)", min_value=5, value=45)
            d_thi = st.date_input("Ngày thi")
            f_word = st.file_uploader("Tải file Word (.docx)", type=["docx"])

            if st.button("🚀 Kích hoạt đề thi", use_container_width=True):
                if all([n_ma, t_mon, t_lop, f_word]):
                    questions = parse_docx(f_word)
                    if questions:
                        supabase.table("exam_questions").upsert({
                            "ma_de": n_ma.strip(),
                            "nội_dung_json": questions,
                            "ten_mon": t_mon.strip(),
                            "ten_lop": t_lop.strip(),
                            "ngay_thi": d_thi.strftime("%d/%m/%Y"),
                            "thoi_gian_phut": int(t_gian)
                        }).execute()
                        st.success(f"✅ Đã kích hoạt đề {n_ma} ({len(questions)} câu)")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Không đọc được câu hỏi. Kiểm tra file Word và màu đỏ đáp án.")
                else:
                    st.error("Vui lòng điền đầy đủ thông tin")

        with col2:
            st.subheader("📊 Kết quả thi")
            # Phần hiển thị kết quả và in phiếu giữ nguyên như code cũ của bạn (bạn có thể copy phần col2 từ code cũ vào đây)
