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
    padding: 7px 14px; border-radius: 6px; margin: 5px 0;
}}
.ans-wrong {{
    background: #fee2e2; border-left: 4px solid #dc2626;
    padding: 7px 14px; border-radius: 6px; margin: 5px 0;
}}
.ans-skip {{
    background: #f3f4f6; border-left: 4px solid #9ca3af;
    padding: 7px 14px; border-radius: 6px; margin: 5px 0;
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


def parse_docx(file) -> list[dict]:
    """
    Đọc file Word, trả về danh sách câu hỏi.
    Đáp án đúng được đánh dấu bằng màu chữ đỏ (FF0000).
    Giữ nguyên thứ tự câu hỏi và đáp án từ file gốc.
    """
    doc = Document(file)
    full_text = ""

    for para in doc.paragraphs:
        para_text = ""
        for run in para.runs:
            try:
                is_red = run.font.color and str(run.font.color.rgb) == "FF0000"
            except Exception:
                is_red = False
            para_text += f"[[DUNG]]{run.text}[[HET]]" if is_red else run.text
        full_text += para_text + "\n"

    questions = []
    blocks = re.split(r'(?i)(Câu\s+\d+\s*[:.)])', full_text)

    for i in range(1, len(blocks), 2):
        header = blocks[i].strip()
        body   = blocks[i + 1]

        # Tách các lựa chọn A/B/C/D
        parts = re.split(r'(?i)(?<!\w)([A-D]\s*[.:])\s*', body)
        raw_question = parts[0].replace("[[DUNG]]", "").replace("[[HET]]", "").strip()

        options   = {}
        ans_key   = ""

        for j in range(1, len(parts) - 1, 2):
            label   = re.sub(r'[.:\s]', '', parts[j]).upper()          # "A", "B", "C", "D"
            content_raw = parts[j + 1]
            is_correct  = "[[DUNG]]" in content_raw
            content     = content_raw.replace("[[DUNG]]", "").replace("[[HET]]", "").strip()
            # Loại bỏ ký tự xuống dòng thừa ở cuối nội dung mỗi lựa chọn
            content     = re.sub(r'\s+$', '', content)
            options[label] = f"{label}. {content}"
            if is_correct:
                ans_key = label

        # Chỉ lấy câu hỏi hợp lệ (có ít nhất 2 lựa chọn và có đáp án)
        sorted_opts = [options[k] for k in sorted(options.keys()) if k in options]
        if len(sorted_opts) >= 2 and ans_key:
            questions.append({
                "question":   f"{header} {raw_question}",
                "options":    sorted_opts,
                "answer_key": ans_key,          # ví dụ: "B"
            })

    return questions


def calc_score(quiz: list[dict], choices: dict) -> tuple[int, float]:
    """
    Tính điểm chuẩn:
      - Mỗi câu đúng = 10 / tổng_số_câu điểm
      - So sánh: lựa chọn của HS bắt đầu bằng đúng answer_key + "."
      - Làm tròn 2 chữ số thập phân, tối đa 10.
    Returns: (số_câu_đúng, điểm)
    """
    correct = 0
    for idx, q in enumerate(quiz):
        chosen = choices.get(idx, "")
        key    = q.get("answer_key", "")
        if chosen and key and chosen.startswith(f"{key}."):
            correct += 1
    total = len(quiz)
    grade = round((correct / total) * 10, 2) if total > 0 else 0.0
    return correct, grade


def check_duplicate(ho_ten: str, ma_de: str, ngay_thi: str) -> bool:
    """Kiểm tra học sinh đã nộp bài cho đề này chưa."""
    try:
        res = (supabase.table("student_results")
               .select("id")
               .eq("ho_ten", ho_ten)
               .eq("ma_de",  ma_de)
               .eq("ngay_thi", ngay_thi)
               .execute())
        return bool(res.data)
    except Exception:
        return False


def save_result(state: dict, quiz: list[dict], choices: dict, c_num: int, grade: float):
    supabase.table("student_results").insert({
        "ma_de":       state["ma_de_dang_thi"],
        "ho_ten":      state["st_name"],
        "lop":         state["st_class"],
        "diem":        grade,
        "so_cau_dung": f"{c_num}/{len(quiz)}",
        "lop_thi":     state["mon_hoc"],
        "lop_kiem_tra":state["lop_kiem_tra"],
        "ngay_thi":    state["ngay_thi"],
    }).execute()


def render_timer(seconds_left: int, total_seconds: int):
    pct = seconds_left / total_seconds if total_seconds > 0 else 0
    warn = "timer-warning" if pct < 0.2 else ""
    m, s = divmod(seconds_left, 60)
    bar  = int(pct * 100)
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
        "is_testing":   False,
        "show_result":  True,
        "last_grade":   grade,
        "last_correct": c_num,
        "last_quiz":    quiz,
        "last_choices": choices,
    })
    st.rerun()


# ============================================================
# TIÊU ĐỀ
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
    exam_res  = supabase.table("exam_questions").select("ten_mon, ma_de, thoi_gian_phut").execute()
    all_exams = exam_res.data or []
    subjects  = sorted({str(e.get("ten_mon", "")).strip() for e in all_exams if e.get("ten_mon")})

    ss = st.session_state  # alias ngắn gọn

    # ── TRẠNG THÁI 1: ĐĂNG KÝ ──────────────────────────────
    if not ss.get("is_testing") and not ss.get("show_result"):

        # Dùng container — khi st.rerun() toàn bộ block này không còn render
        reg_container = st.container()
        with reg_container:
            st.subheader("📝 Đăng ký thông tin dự thi")

            # Chọn môn NGOÀI form để filter mã đề kịp thời
            # Xóa key cũ nếu còn sót từ lần trước để tránh ghost widget
            sel_subject = st.selectbox(
                "📚 Chọn Môn học:",
                ["-- Chọn môn --"] + subjects,
                key="sel_subject_outer"
            )
            filtered_codes = [
                e["ma_de"] for e in all_exams
                if str(e.get("ten_mon", "")).strip() == sel_subject
            ]

            with st.form("info_form"):
                name        = st.text_input("👤 Họ và Tên của em:")
                st_class    = st.text_input("🏫 Lớp của em:")
                ma_de_opts  = (["-- Chọn mã đề --"] + filtered_codes) if filtered_codes else ["-- Chọn môn trước --"]
                sel_ma_de   = st.selectbox("🔑 Chọn Mã đề thi:", ma_de_opts)
                start_btn   = st.form_submit_button("🚀 BẮT ĐẦU LÀM BÀI", use_container_width=True)

            if start_btn:
                valid = (
                    name.strip() and st_class.strip()
                    and sel_subject != "-- Chọn môn --"
                    and sel_ma_de not in ("-- Chọn mã đề --", "-- Chọn môn trước --")
                )
                if not valid:
                    st.error("❌ Vui lòng điền đầy đủ thông tin trước khi bắt đầu!")
                else:
                    ex = supabase.table("exam_questions").select("*").eq("ma_de", sel_ma_de).execute()
                    if ex.data:
                        info = ex.data[0]
                        if check_duplicate(name.strip(), sel_ma_de, info.get("ngay_thi", "")):
                            st.error("⚠️ Bạn đã nộp bài cho đề thi này rồi. Không thể thi lại!")
                        else:
                            # Xóa key selectbox môn để không bị ghost widget sau rerun
                            ss.pop("sel_subject_outer", None)
                            ss.update({
                                "quiz_data":      info["nội_dung_json"],
                                "ma_de_dang_thi": sel_ma_de,
                                "st_name":        name.strip(),
                                "st_class":       st_class.strip(),
                                "is_testing":     True,
                                "show_result":    False,
                                "mon_hoc":        info.get("ten_mon", ""),
                                "lop_kiem_tra":   info.get("ten_lop", ""),
                                "ngay_thi":       info.get("ngay_thi", ""),
                                "start_time":     time.time(),
                                "total_seconds":  info.get("thoi_gian_phut", 15) * 60,
                                "u_choices":      {},
                                "auto_submitted": False,
                            })
                            st.rerun()
                    else:
                        st.error("❌ Không tìm thấy đề thi. Vui lòng thử lại.")
        st.stop()  # Không render thêm bất cứ thứ gì khi đang ở trạng thái đăng ký

    # ── TRẠNG THÁI 2: ĐANG THI ──────────────────────────────
    elif ss.get("is_testing"):
        elapsed  = time.time() - ss.get("start_time", time.time())
        total_s  = ss.get("total_seconds", 900)
        left     = max(0, int(total_s - elapsed))

        render_timer(left, total_s)

        quiz = ss["quiz_data"]

        # Hết giờ → tự nộp
        if left == 0 and not ss.get("auto_submitted"):
            ss["auto_submitted"] = True
            choices = ss.get("u_choices", {})
            c_num, grade = calc_score(quiz, choices)
            if not check_duplicate(ss["st_name"], ss["ma_de_dang_thi"], ss["ngay_thi"]):
                save_result(ss, quiz, choices, c_num, grade)
            st.warning("⏰ Hết giờ! Bài thi đã được tự động nộp.")
            go_to_result(ss, quiz, choices, c_num, grade)

        # Form bài thi
        with st.form("quiz_form"):
            st.markdown(f"### 📖 MÔN THI: {ss.get('mon_hoc', '').upper()}")
            st.info(f"👨‍🎓 **{ss['st_name'].upper()}** — Mã đề: **{ss['ma_de_dang_thi']}**")
            st.markdown("---")

            u_choices = {}
            for idx, q in enumerate(quiz):
                # Hiển thị nội dung câu hỏi (bỏ phần "Câu X:" ở đầu nếu trùng)
                q_text = re.sub(r'^Câu\s*\d+\s*[:.)]?\s*', '', q["question"], flags=re.IGNORECASE).strip()
                st.markdown(f"**Câu {idx + 1}.** {q_text}")

                prev     = ss.get("u_choices", {}).get(idx)
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

        # Lưu lựa chọn sau mỗi lần render (ngoài form)
        ss["u_choices"] = u_choices

        if nop_btn:
            skipped = [i + 1 for i in range(len(quiz)) if not u_choices.get(i)]
            if skipped:
                st.warning(f"⚠️ Bạn chưa trả lời câu: **{', '.join(map(str, skipped))}**. Vui lòng kiểm tra lại!")
            elif not confirmed:
                st.warning("⚠️ Vui lòng tích xác nhận trước khi nộp bài.")
            else:
                if check_duplicate(ss["st_name"], ss["ma_de_dang_thi"], ss["ngay_thi"]):
                    st.error("⚠️ Bài thi này đã được nộp rồi. Không thể nộp lại!")
                else:
                    c_num, grade = calc_score(quiz, u_choices)
                    save_result(ss, quiz, u_choices, c_num, grade)
                    go_to_result(ss, quiz, u_choices, c_num, grade)

        # Tự reload mỗi 5 giây để cập nhật đồng hồ
        time.sleep(5)
        st.rerun()
        st.stop()  # Không render trạng thái khác

    # ── TRẠNG THÁI 3: KẾT QUẢ (chỉ xem, không thi lại) ────
    elif ss.get("show_result"):
        grade   = ss.get("last_grade", 0)
        c_num   = ss.get("last_correct", 0)
        quiz    = ss.get("last_quiz", [])
        choices = ss.get("last_choices", {})
        total   = len(quiz)

        if grade >= 8:
            emoji, color = "🏆", "#15803d"
        elif grade >= 5:
            emoji, color = "✅", "#0284c7"
        else:
            emoji, color = "📖", "#dc2626"

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
                chosen       = choices.get(idx)
                key          = q.get("answer_key", "")
                correct_text = next((o for o in q["options"] if o.startswith(f"{key}.")), key)
                q_text       = re.sub(r'^Câu\s*\d+\s*[:.)]?\s*', '', q["question"], flags=re.IGNORECASE).strip()

                st.markdown(f"**Câu {idx + 1}.** {q_text}")

                if not chosen:
                    st.markdown(
                        f"<div class='ans-skip'>⬜ Bỏ qua — Đáp án đúng: <b>{correct_text}</b></div>",
                        unsafe_allow_html=True
                    )
                elif chosen.startswith(f"{key}."):
                    st.markdown(
                        f"<div class='ans-correct'>✅ Bạn chọn: <b>{chosen}</b></div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f"<div class='ans-wrong'>❌ Bạn chọn: <b>{chosen}</b>"
                        f" &nbsp;→&nbsp; Đáp án đúng: <b>{correct_text}</b></div>",
                        unsafe_allow_html=True
                    )
                st.markdown("")


# ============================================================
# TAB QUẢN TRỊ VIÊN
# ============================================================
with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản trị:", type="password", key="admin_pwd")

    if pwd and pwd != ADMIN_PASSWORD:
        st.error("❌ Sai mật khẩu!")

    elif pwd == ADMIN_PASSWORD:
        col1, col2 = st.columns([1, 1.8])

        # ── CỘT 1: ĐĂNG ĐỀ & QUẢN LÝ ──────────────────────
        with col1:
            st.subheader("📤 ĐĂNG ĐỀ THI")
            n_ma   = st.text_input("Mã đề thi:")
            t_mon  = st.text_input("Môn học:")
            t_lop  = st.text_input("Lớp kiểm tra:")
            t_gian = st.number_input("Thời gian (phút):", min_value=1, value=15)
            d_thi  = st.date_input("Ngày thi:")
            f_word = st.file_uploader("Tải tệp Word (.docx):", type=["docx"])

            if st.button("🚀 Kích hoạt đề thi", use_container_width=True):
                if n_ma and t_mon and t_lop and f_word:
                    questions = parse_docx(f_word)
                    if not questions:
                        st.error("❌ Không đọc được câu hỏi từ file. Kiểm tra lại định dạng Word.")
                    else:
                        supabase.table("exam_questions").upsert({
                            "ma_de":          n_ma.strip(),
                            "nội_dung_json":  questions,
                            "ten_mon":        t_mon.strip(),
                            "ten_lop":        t_lop.strip(),
                            "ngay_thi":       d_thi.strftime("%d/%m/%Y"),
                            "thoi_gian_phut": int(t_gian),
                        }).execute()
                        st.success(f"✅ Đã kích hoạt đề **{n_ma}** — {len(questions)} câu hỏi!")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("❌ Vui lòng điền đủ thông tin và tải file Word.")

            st.divider()
            st.subheader("🗑️ QUẢN LÝ DỮ LIỆU")

            q_list = supabase.table("exam_questions").select("ma_de, ten_mon").execute()
            if q_list.data:
                de_opts = [f"{e['ma_de']} ({e.get('ten_mon','')})" for e in q_list.data]
                to_del  = st.selectbox("Chọn đề để xóa:", ["-- Chọn --"] + de_opts)
                if to_del != "-- Chọn --":
                    real_ma = to_del.split(" (")[0]
                    if st.button(f"🗑️ Xóa đề **{real_ma}**", use_container_width=True):
                        supabase.table("exam_questions").delete().eq("ma_de", real_ma).execute()
                        st.success(f"Đã xóa đề {real_ma}!")
                        time.sleep(1)
                        st.rerun()

            st.markdown("")
            with st.expander("⚠️ Xóa toàn bộ kết quả thi"):
                if st.button("🔥 XÁC NHẬN XÓA TẤT CẢ KẾT QUẢ", type="primary", use_container_width=True):
                    supabase.table("student_results").delete().neq("id", 0).execute()
                    st.success("Đã xóa toàn bộ kết quả!")
                    st.rerun()

        # ── CỘT 2: KẾT QUẢ & THỐNG KÊ ─────────────────────
        with col2:
            st.subheader("📊 KẾT QUẢ & THỐNG KÊ")

            r_all = supabase.table("student_results").select("*").execute()
            if not r_all.data:
                st.info("Chưa có kết quả nào.")
            else:
                df = pd.DataFrame(r_all.data)
                df["diem"]          = pd.to_numeric(df["diem"], errors="coerce")
                df["created_at_vn"] = df["created_at"].apply(format_vietnam_time)
                df = df.sort_values("ho_ten")

                # Bộ lọc môn
                mon_opts    = ["Tất cả"] + sorted(df["lop_thi"].dropna().unique().tolist())
                sel_mon     = st.selectbox("Lọc theo môn:", mon_opts)
                df_f        = df if sel_mon == "Tất cả" else df[df["lop_thi"] == sel_mon]

                # 4 chỉ số nhanh
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Tổng bài thi",    len(df_f))
                c2.metric("Điểm trung bình", f"{df_f['diem'].mean():.2f}" if len(df_f) else "—")
                c3.metric("Điểm cao nhất",   f"{df_f['diem'].max():.2f}"  if len(df_f) else "—")
                c4.metric("Tỉ lệ đậu (≥5)",  f"{(df_f['diem'] >= 5).mean()*100:.0f}%" if len(df_f) else "—")

                # Biểu đồ phân phối điểm
                try:
                    import plotly.express as px
                    fig = px.histogram(
                        df_f, x="diem", nbins=10,
                        title="Phân phối điểm số",
                        labels={"diem": "Điểm", "count": "Số học sinh"},
                        color_discrete_sequence=["#2563eb"]
                    )
                    fig.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font_family="Be Vietnam Pro, Arial",
                        margin=dict(t=40, b=20, l=10, r=10)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    st.bar_chart(df_f["diem"].value_counts().sort_index())

                # Bảng kết quả
                st.dataframe(
                    df_f[["ho_ten","lop","so_cau_dung","diem","ma_de","created_at_vn"]].rename(columns={
                        "ho_ten":       "Họ tên",
                        "lop":          "Lớp",
                        "so_cau_dung":  "Câu đúng",
                        "diem":         "Điểm",
                        "ma_de":        "Mã đề",
                        "created_at_vn":"Thời gian nộp",
                    }),
                    use_container_width=True,
                    hide_index=True
                )

                # Xuất phiếu
                st.divider()
                st.subheader("🖨️ XUẤT PHIẾU KẾT QUẢ")

                # Danh sách học sinh dạng "Họ tên — Lớp — Mã đề"
                hs_opts = [
                    f"{r['ho_ten']} | {r['lop']} | {r['ma_de']}"
                    for _, r in df.iterrows()
                ]
                sel_hs = st.selectbox("Chọn học sinh:", ["-- Chọn --"] + hs_opts)

                if sel_hs != "-- Chọn --":
                    idx_hs = hs_opts.index(sel_hs)
                    hs     = df.iloc[idx_hs]

                    st.markdown(f"""
                    <div class='printable-card'>
                        <h3 style='text-align:center;color:#1e3a8a;'>PHIẾU MINH CHỨNG KẾT QUẢ KIỂM TRA</h3>
                        <p style='text-align:center;'>Trường THCS Lê Quý Đôn – Phường Hà Giang 1 – Tỉnh Tuyên Quang</p>
                        <hr>
                        <table style='width:100%;font-size:1.1em;line-height:2.4em;color:black;'>
                            <tr><td width='42%'><b>Học sinh:</b></td><td>{hs['ho_ten'].upper()}</td></tr>
                            <tr><td><b>Lớp:</b></td><td>{hs['lop']}</td></tr>
                            <tr><td><b>Môn kiểm tra:</b></td><td>{hs.get('lop_thi','')}</td></tr>
                            <tr><td><b>Ngày nộp bài:</b></td><td>{hs['created_at_vn']}</td></tr>
                            <tr><td><b>Kết quả:</b></td>
                                <td><b style='font-size:1.25em;color:#1e3a8a;'>
                                    {hs['diem']} điểm ({hs['so_cau_dung']})
                                </b></td>
                            </tr>
                        </table>
                        <br><br>
                        <div style='display:flex;justify-content:space-between;text-align:center;color:black;'>
                            <div style='width:45%;'><b>GIÁO VIÊN BỘ MÔN</b><br><br><br><br>(Ký và ghi rõ họ tên)</div>
                            <div style='width:45%;'><b>HỌC SINH XÁC NHẬN</b><br><br><br><br>(Ký và ghi rõ họ tên)</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    html_phieu = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="utf-8">
    <title>Phieu_{hs['ho_ten']}</title>
    <style>
        body      {{ font-family: Arial, sans-serif; padding: 50px; }}
        .wrap     {{ border: 2px solid #1e3a8a; padding: 40px; border-radius: 10px; max-width: 800px; margin: auto; }}
        h2        {{ text-align: center; color: #1e3a8a; }}
        hr        {{ border: 1px solid #1e3a8a; }}
        table     {{ width: 100%; line-height: 3em; font-size: 1.15em; }}
        .footer   {{ display: flex; justify-content: space-between; margin-top: 60px; text-align: center; }}
    </style>
</head>
<body onload="window.print()">
<div class="wrap">
    <h2>PHIẾU MINH CHỨNG KẾT QUẢ KIỂM TRA</h2>
    <p style="text-align:center;">Trường THCS Lê Quý Đôn – Phường Hà Giang 1 – Tỉnh Tuyên Quang</p>
    <hr>
    <table>
        <tr><td width="42%"><b>Họ và tên học sinh:</b></td><td>{hs['ho_ten'].upper()}</td></tr>
        <tr><td><b>Lớp học:</b></td><td>{hs['lop']}</td></tr>
        <tr><td><b>Môn kiểm tra:</b></td><td>{hs.get('lop_thi','')}</td></tr>
        <tr><td><b>Ngày nộp bài:</b></td><td>{hs['created_at_vn']}</td></tr>
        <tr><td><b>Kết quả đạt được:</b></td><td><b>{hs['diem']} điểm ({hs['so_cau_dung']})</b></td></tr>
    </table>
    <div class="footer">
        <div style="width:45%;"><b>GIÁO VIÊN BỘ MÔN</b><br><br><br><br>(Ký và ghi rõ họ tên)</div>
        <div style="width:45%;"><b>HỌC SINH XÁC NHẬN</b><br><br><br><br>(Ký và ghi rõ họ tên)</div>
    </div>
</div>
</body>
</html>"""

                    st.download_button(
                        label="🚀 TẢI PHIẾU IN VỀ MÁY",
                        data=html_phieu,
                        file_name=f"Phieu_{hs['ho_ten'].replace(' ','_')}.html",
                        mime="text/html",
                        use_container_width=True
                    )
