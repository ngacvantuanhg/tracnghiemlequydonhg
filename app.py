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
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&display=swap');
html, body, [class*="css"] {{
    font-family: 'Be Vietnam Pro', Arial, sans-serif !important;
}}
.stApp {{
    background-image: url("{BG_IMG}");
    background-attachment: fixed;
    background-size: cover;
    background-position: center;
}}
[data-testid="stForm"] {{
    background-color: rgba(255,255,255,0.96);
    border: 2px solid #1e3a8a;
    border-radius: 16px;
    padding: 1.5rem;
    max-width: 860px;
    margin: 0 auto;
}}
h1, .sub-title {{
    text-align: center !important;
    color: #1e3a8a !important;
}}
.timer-box {{
    position: sticky; top: 0; z-index: 999;
    background: linear-gradient(135deg, #1e3a8a, #2563eb);
    color: white; text-align: center;
    padding: 10px 20px; border-radius: 12px;
    font-size: 1.4em; font-weight: 700;
    margin-bottom: 16px;
    box-shadow: 0 4px 12px rgba(30,58,138,0.35);
}}
.timer-warning {{
    background: linear-gradient(135deg, #dc2626, #ef4444) !important;
    animation: pulse 1s infinite;
}}
@keyframes pulse {{
    0%,100% {{ opacity:1; }} 50% {{ opacity:0.75; }}
}}
.result-box {{
    background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
    border: 2px solid #0284c7;
    border-radius: 14px; padding: 24px 32px;
    text-align: center; margin: 16px 0;
}}
.score-big {{ font-size: 3em; font-weight: 700; }}
.ans-correct {{
    background: #dcfce7; border-left: 4px solid #16a34a;
    padding: 10px 14px; border-radius: 6px; margin: 8px 0;
}}
.ans-wrong {{
    background: #fee2e2; border-left: 4px solid #dc2626;
    padding: 10px 14px; border-radius: 6px; margin: 8px 0;
}}
.ans-skip {{
    background: #f3f4f6; border-left: 4px solid #9ca3af;
    padding: 10px 14px; border-radius: 6px; margin: 8px 0;
}}
.printable-card {{
    background: white !important; padding: 30px !important;
    border: 2px solid #1e3a8a !important;
    color: black !important; border-radius: 10px;
}}
@media (max-width: 640px) {{
    [data-testid="stForm"] {{ padding: 1rem; }}
    .score-big {{ font-size: 2.2em; }}
    .timer-box {{ font-size: 1.1em; }}
}}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HÀM TIỆN ÍCH
# ============================================================
def format_vietnam_time(utc_str: str) -> str:
    try:
        utc_dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
        return utc_dt.astimezone(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%H:%M:%S %d/%m/%Y")
    except Exception:
        return utc_str

_RED_COLORS = {"FF0000", "EE0000", "CC0000", "DC143C", "FF4D4D"}

def _is_red(run) -> bool:
    try:
        if run.font.color and run.font.color.type and run.font.color.rgb:
            return str(run.font.color.rgb).upper() in _RED_COLORS
    except:
        pass
    return False

def parse_docx(file) -> list[dict]:
    """Đọc file Word, nhận diện đáp án tô màu đỏ"""
    doc = Document(file)
    questions: list[dict] = []
    q_text = None
    options: dict[str, str] = {}
    ans_key = ""

    OPT_RE = re.compile(r'(?:^|\t|\s{2,})([A-D])[.)]\s*(.+?)(?=\s{2,}[A-D][.)]|\t|$)', re.IGNORECASE)

    def flush():
        nonlocal q_text, options, ans_key
        if q_text and len(options) >= 2 and ans_key:
            sorted_options = [f"{k}. {options[k]}" for k in sorted(options.keys())]
            questions.append({
                "question": q_text.strip(),
                "options": sorted_options,
                "answer_key": ans_key.upper(),
            })
        q_text = None
        options = {}
        ans_key = ""

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Phát hiện câu hỏi
        if re.match(r'(?i)^Câu\s+\d+[:.)]', text):
            flush()
            q_text = text
            continue

        # Xử lý đáp án
        matches = list(OPT_RE.finditer(text))
        if matches and q_text:
            red_texts = [run.text.strip() for run in para.runs if _is_red(run) and run.text.strip()]
            red_combined = " ".join(red_texts)

            for m in matches:
                label = m.group(1).upper()
                content = m.group(2).strip()
                options[label] = content

                full_opt = f"{label}. {content}"
                if (label in red_combined or 
                    full_opt in red_combined or 
                    any(label == rt[0] if rt else False for rt in red_texts) or
                    content in red_combined):
                    ans_key = label

    flush()
    return questions


def calc_score(quiz: list[dict], choices: dict) -> tuple[int, float]:
    correct = 0
    for idx, q in enumerate(quiz):
        chosen = str(choices.get(idx, "")).strip()
        key = q.get("answer_key", "").strip().upper()

        if chosen and key and (chosen.startswith(f"{key}.") or chosen.startswith(f"{key} ")):
            correct += 1

    total = len(quiz)
    grade = round((correct / total) * 10, 2) if total > 0 else 0.0
    return correct, grade


def check_duplicate(ho_ten: str, ma_de: str, ngay_thi: str) -> bool:
    try:
        res = supabase.table("student_results").select("id").eq("ho_ten", ho_ten).eq("ma_de", ma_de).eq("ngay_thi", ngay_thi).execute()
        return bool(res.data)
    except:
        return False


def save_result(state: dict, quiz: list[dict], choices: dict, c_num: int, grade: float):
    supabase.table("student_results").insert({
        "ma_de": state["ma_de_dang_thi"],
        "ho_ten": state["st_name"],
        "lop": state["st_class"],
        "diem": grade,
        "so_cau_dung": f"{c_num}/{len(quiz)}",
        "lop_thi": state.get("mon_hoc", ""),
        "lop_kiem_tra": state.get("lop_kiem_tra", ""),
        "ngay_thi": state.get("ngay_thi", ""),
    }).execute()


def render_timer(seconds_left: int, total_seconds: int):
    pct = seconds_left / total_seconds if total_seconds > 0 else 0
    warn = "timer-warning" if pct < 0.2 else ""
    m, s = divmod(seconds_left, 60)
    bar = int(pct * 100)
    st.markdown(f"""
    <div class="timer-box {warn}">
        ⏱️ Thời gian còn lại: {m:02d}:{s:02d}
        <div style="background:rgba(255,255,255,0.3);border-radius:8px;height:8px;margin-top:6px;">
            <div style="background:white;width:{bar}%;height:8px;border-radius:8px;transition:width 1s;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def go_to_result(state, quiz, choices, c_num, grade):
    state.update({
        "is_testing": False,
        "show_result": True,
        "last_grade": grade,
        "last_correct": c_num,
        "last_quiz": quiz,
        "last_choices": choices,
    })
    st.rerun()

# ============================================================
# GIAO DIỆN
# ============================================================
st.markdown("<h1>🏫 HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)
st.markdown(
    "<div class='sub-title' style='font-size:1.05em;'>"
    "Trường THCS Lê Quý Đôn – Phường Hà Giang 1 – Tỉnh Tuyên Quang"
    "</div>",
    unsafe_allow_html=True
)
st.markdown("<br>", unsafe_allow_html=True)

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])

# ============================================================
# TAB HỌC SINH
# ============================================================
with tab_hs:
    exam_res = supabase.table("exam_questions").select("ten_mon, ma_de, thoi_gian_phut").execute()
    all_exams = exam_res.data or []
    subjects = sorted({str(e.get("ten_mon", "")).strip() for e in all_exams if e.get("ten_mon")})

    ss = st.session_state

    if not ss.get("is_testing") and not ss.get("show_result"):
        reg_container = st.container()
        with reg_container:
            st.subheader("📝 Đăng ký thông tin dự thi")

            sel_subject = st.selectbox(
                "📚 Chọn Môn học:",
                ["-- Chọn môn --"] + subjects,
                key="sel_subject_outer"
            )

            filtered_codes = [e["ma_de"] for e in all_exams if str(e.get("ten_mon", "")).strip() == sel_subject]

            with st.form("info_form"):
                name = st.text_input("👤 Họ và Tên của em:")
                st_class = st.text_input("🏫 Lớp của em:")
                ma_de_opts = (["-- Chọn mã đề --"] + filtered_codes) if filtered_codes else ["-- Chọn môn trước --"]
                sel_ma_de = st.selectbox("🔑 Chọn Mã đề thi:", ma_de_opts)
                start_btn = st.form_submit_button("🚀 BẮT ĐẦU LÀM BÀI", use_container_width=True)

            if start_btn:
                valid = (name.strip() and st_class.strip() and 
                        sel_subject != "-- Chọn môn --" and 
                        sel_ma_de not in ("-- Chọn mã đề --", "-- Chọn môn trước --"))
                
                if not valid:
                    st.error("❌ Vui lòng điền đầy đủ thông tin trước khi bắt đầu!")
                else:
                    ex = supabase.table("exam_questions").select("*").eq("ma_de", sel_ma_de).execute()
                    if ex.data:
                        info = ex.data[0]
                        if check_duplicate(name.strip(), sel_ma_de, info.get("ngay_thi", "")):
                            st.error("⚠️ Bạn đã nộp bài cho đề thi này rồi. Không thể thi lại!")
                        else:
                            ss.pop("sel_subject_outer", None)
                            ss.update({
                                "quiz_data": info["nội_dung_json"],
                                "ma_de_dang_thi": sel_ma_de,
                                "st_name": name.strip(),
                                "st_class": st_class.strip(),
                                "is_testing": True,
                                "show_result": False,
                                "mon_hoc": info.get("ten_mon", ""),
                                "lop_kiem_tra": info.get("ten_lop", ""),
                                "ngay_thi": info.get("ngay_thi", ""),
                                "start_time": time.time(),
                                "total_seconds": info.get("thoi_gian_phut", 15) * 60,
                                "u_choices": {},
                                "auto_submitted": False,
                            })
                            st.rerun()
                    else:
                        st.error("❌ Không tìm thấy đề thi. Vui lòng thử lại.")
        st.stop()

    # ==================== ĐANG THI ====================
    elif ss.get("is_testing"):
        elapsed = time.time() - ss.get("start_time", time.time())
        total_s = ss.get("total_seconds", 900)
        left = max(0, int(total_s - elapsed))
        render_timer(left, total_s)

        quiz = ss["quiz_data"]

        if left == 0 and not ss.get("auto_submitted"):
            ss["auto_submitted"] = True
            choices = ss.get("u_choices", {})
            c_num, grade = calc_score(quiz, choices)
            if not check_duplicate(ss["st_name"], ss["ma_de_dang_thi"], ss["ngay_thi"]):
                save_result(ss, quiz, choices, c_num, grade)
            st.warning("⏰ Hết giờ! Bài thi đã được tự động nộp.")
            go_to_result(ss, quiz, choices, c_num, grade)

        with st.form("quiz_form"):
            st.markdown(f"### 📖 MÔN THI: {ss.get('mon_hoc', '').upper()}")
            st.info(f"👨‍🎓 **{ss['st_name'].upper()}** — Mã đề: **{ss['ma_de_dang_thi']}**")
            st.markdown("---")

            u_choices = {}
            for idx, q in enumerate(quiz):
                q_text = re.sub(r'^Câu\s*\d+\s*[:.)]?\s*', '', q["question"], flags=re.IGNORECASE).strip()
                st.markdown(f"**Câu {idx + 1}.** {q_text}")

                prev = ss.get("u_choices", {}).get(idx)
                prev_idx = q["options"].index(prev) if prev in q["options"] else None

                u_choices[idx] = st.radio(
                    label=f"dap_an_{idx}",
                    options=q["options"],
                    index=prev_idx,
                    key=f"q_{idx}",
                    label_visibility="collapsed"
                )
                st.markdown("")

            col_l, col_r = st.columns([3, 1])
            with col_l:
                confirmed = st.checkbox("✅ Tôi đã kiểm tra lại bài và muốn nộp bài thi.")
            with col_r:
                nop_btn = st.form_submit_button("📤 NỘP BÀI", use_container_width=True)

        ss["u_choices"] = u_choices

        if nop_btn:
            skipped = [i + 1 for i in range(len(quiz)) if not u_choices.get(i)]
            if skipped:
                st.warning(f"⚠️ Bạn chưa trả lời câu: **{', '.join(map(str, skipped))}**")
            elif not confirmed:
                st.warning("⚠️ Vui lòng tích xác nhận trước khi nộp bài.")
            else:
                if check_duplicate(ss["st_name"], ss["ma_de_dang_thi"], ss["ngay_thi"]):
                    st.error("⚠️ Bài thi này đã được nộp rồi!")
                else:
                    c_num, grade = calc_score(quiz, u_choices)
                    save_result(ss, quiz, u_choices, c_num, grade)
                    go_to_result(ss, quiz, u_choices, c_num, grade)

        time.sleep(5)
        st.rerun()
        st.stop()

    # ==================== KẾT QUẢ ====================
    elif ss.get("show_result"):
        grade = ss.get("last_grade", 0)
        c_num = ss.get("last_correct", 0)
        quiz = ss.get("last_quiz", [])
        choices = ss.get("last_choices", {})
        total = len(quiz)

        emoji = "🏆" if grade >= 8 else "✅" if grade >= 5 else "📖"
        color = "#15803d" if grade >= 8 else "#0284c7" if grade >= 5 else "#dc2626"

        st.markdown(f"""
        <div class="result-box">
            <div class="score-big" style="color:{color};">{emoji} {grade} điểm</div>
            <p style="font-size:1.1em;margin:8px 0;">Số câu đúng: <b>{c_num}/{total}</b></p>
            <p style="color:#64748b;margin:4px 0;">
                Học sinh: <b>{ss.get('st_name','').upper()}</b> &nbsp;|&nbsp; Lớp: <b>{ss.get('st_class','')}</b>
            </p>
            <p style="color:#64748b;margin:4px 0;">
                Môn: <b>{ss.get('mon_hoc','')}</b> &nbsp;|&nbsp; Mã đề: <b>{ss.get('ma_de_dang_thi','')}</b>
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.info("ℹ️ Bài thi đã được nộp. Vui lòng liên hệ giáo viên nếu cần hỗ trợ.")

        with st.expander("🔍 Xem lại đáp án chi tiết"):
            for idx, q in enumerate(quiz):
                chosen = str(choices.get(idx, "")).strip()
                key = q.get("answer_key", "").strip().upper()
                q_text = re.sub(r'^Câu\s*\d+\s*[:.)]?\s*', '', q["question"], flags=re.IGNORECASE).strip()

                correct_option = next((o for o in q["options"] if o.startswith(f"{key}." )), f"{key}. (Không tìm thấy)")

                st.markdown(f"**Câu {idx + 1}.** {q_text}")

                if not chosen:
                    st.markdown(f"<div class='ans-skip'>⬜ Bỏ qua — Đáp án đúng: <b>{correct_option}</b></div>", unsafe_allow_html=True)
                elif chosen.startswith(f"{key}.") or chosen.startswith(f"{key} "):
                    st.markdown(f"<div class='ans-correct'>✅ Bạn chọn đúng: <b>{chosen}</b></div>", unsafe_allow_html=True)
                else:
                    st.markdown(
                        f"<div class='ans-wrong'>❌ Bạn chọn: <b>{chosen}</b><br>"
                        f"→ Đáp án đúng: <b>{correct_option}</b></div>",
                        unsafe_allow_html=True
                    )
                st.markdown("---")

# ============================================================
# TAB QUẢN TRỊ VIÊN
# ============================================================
with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản trị:", type="password", key="admin_pwd")
    
    if pwd and pwd != ADMIN_PASSWORD:
        st.error("❌ Sai mật khẩu!")
    elif pwd == ADMIN_PASSWORD:
        col1, col2 = st.columns([1, 1.8])

        with col1:
            st.subheader("📤 ĐĂNG ĐỀ THI")
            n_ma = st.text_input("Mã đề thi:")
            t_mon = st.text_input("Môn học:")
            t_lop = st.text_input("Lớp kiểm tra:")
            t_gian = st.number_input("Thời gian (phút):", min_value=1, value=15)
            d_thi = st.date_input("Ngày thi:")
            f_word = st.file_uploader("Tải tệp Word (.docx):", type=["docx"])

            if st.button("🚀 Kích hoạt đề thi", use_container_width=True):
                if n_ma and t_mon and t_lop and f_word:
                    questions = parse_docx(f_word)
                    if not questions:
                        st.error("❌ Không đọc được câu hỏi từ file. Kiểm tra lại định dạng Word và màu đỏ của đáp án.")
                    else:
                        supabase.table("exam_questions").upsert({
                            "ma_de": n_ma.strip(),
                            "nội_dung_json": questions,
                            "ten_mon": t_mon.strip(),
                            "ten_lop": t_lop.strip(),
                            "ngay_thi": d_thi.strftime("%d/%m/%Y"),
                            "thoi_gian_phut": int(t_gian),
                        }).execute()
                        st.success(f"✅ Đã kích hoạt đề **{n_ma}** — {len(questions)} câu hỏi!")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("❌ Vui lòng điền đủ thông tin và tải file Word.")

            # Phần quản lý dữ liệu (giữ nguyên như cũ)
            st.divider()
            st.subheader("🗑️ QUẢN LÝ DỮ LIỆU")
            # ... (phần xóa đề và xóa kết quả giữ nguyên như code cũ của bạn)

        with col2:
            st.subheader("📊 KẾT QUẢ & THỐNG KÊ")
            # Phần này bạn có thể giữ nguyên code cũ của mình
