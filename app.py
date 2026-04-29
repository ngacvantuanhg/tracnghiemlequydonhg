import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime, timezone
import pytz
import time
import random
import hashlib

# ============================================================
# KẾT NỐI HỆ THỐNG
# ============================================================
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(
    page_title="Hệ Thống Thi Lê Quý Đôn",
    layout="wide",
    page_icon="🏫"
)

ADMIN_PASSWORD = "141983"
bg_img = "https://raw.githubusercontent.com/ngacvantuanhg/tracnghiemlequydonhg/main/Anhnen.png"

# ============================================================
# STYLE GIAO DIỆN — tối ưu mobile + desktop
# ============================================================
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Be Vietnam Pro', Arial, sans-serif !important;
}}

.stApp {{
    background-image: url("{bg_img}");
    background-attachment: fixed;
    background-size: cover;
    background-position: center;
}}

/* Form container */
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

/* Timer box */
.timer-box {{
    position: sticky;
    top: 0;
    z-index: 999;
    background: linear-gradient(135deg, #1e3a8a, #2563eb);
    color: white;
    text-align: center;
    padding: 10px 20px;
    border-radius: 12px;
    font-size: 1.4em;
    font-weight: 700;
    margin-bottom: 16px;
    box-shadow: 0 4px 12px rgba(30,58,138,0.35);
}}

.timer-warning {{
    background: linear-gradient(135deg, #dc2626, #ef4444) !important;
    animation: pulse 1s infinite;
}}

@keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.75; }}
}}

/* Thẻ phiếu in */
.printable-card {{
    background-color: white !important;
    padding: 30px !important;
    border: 2px solid #1e3a8a !important;
    color: black !important;
    border-radius: 10px;
}}

/* Kết quả học sinh */
.result-box {{
    background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
    border: 2px solid #0284c7;
    border-radius: 14px;
    padding: 20px 30px;
    text-align: center;
    margin: 16px 0;
}}

.score-big {{
    font-size: 3em;
    font-weight: 700;
    color: #1e3a8a;
}}

/* Đáp án review */
.ans-correct {{ background:#dcfce7; border-left: 4px solid #16a34a; padding: 6px 12px; border-radius: 6px; margin: 4px 0; }}
.ans-wrong   {{ background:#fee2e2; border-left: 4px solid #dc2626; padding: 6px 12px; border-radius: 6px; margin: 4px 0; }}
.ans-skip    {{ background:#f3f4f6; border-left: 4px solid #9ca3af; padding: 6px 12px; border-radius: 6px; margin: 4px 0; }}

/* Responsive mobile */
@media (max-width: 640px) {{
    [data-testid="stForm"] {{ padding: 1rem; }}
    .score-big {{ font-size: 2.2em; }}
    .timer-box {{ font-size: 1.1em; }}
}}
</style>
""", unsafe_allow_html=True)


# ============================================================
# HÀM HỖ TRỢ
# ============================================================
def format_vietnam_time(utc_time_str):
    try:
        if utc_time_str and isinstance(utc_time_str, str):
            utc_dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
            vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
            return utc_dt.astimezone(vn_tz).strftime("%H:%M:%S %d/%m/%Y")
    except:
        pass
    return utc_time_str if utc_time_str else ""


def parse_docx_simple(file):
    """Đọc file Word, nhận diện đáp án đúng bằng màu đỏ."""
    try:
        doc = Document(file)
        questions = []
        full_text_with_marks = ""

        for para in doc.paragraphs:
            para_text = ""
            for r in para.runs:
                try:
                    is_red = r.font.color and str(r.font.color.rgb) == "FF0000"
                except Exception:
                    is_red = False
                para_text += f" [[DUNG]]{r.text}[[HET]] " if is_red else r.text
            full_text_with_marks += para_text + "\n"

        q_blocks = re.split(r'(?i)(Câu\s+\d+[:.])', full_text_with_marks)
        for i in range(1, len(q_blocks), 2):
            header = q_blocks[i].strip()
            parts = re.split(r'(?i)\b([A-D]\s*[:.])', q_blocks[i + 1])
            
            if len(parts) < 2:
                continue
                
            question_text = parts[0].replace("[[DUNG]]", "").replace("[[HET]]", "").strip()
            options_dict = {}
            ans_k = ""
            
            for j in range(1, len(parts), 2):
                label = parts[j].strip().upper()[0]
                val = parts[j + 1].replace('[[DUNG]]', '').replace('[[HET]]', '').strip()
                options_dict[label] = f"{label}. {val}"
                if "[[DUNG]]" in parts[j + 1]:
                    ans_k = label
                    
            sorted_options = [options_dict[k] for k in sorted(options_dict.keys())]
            if sorted_options and ans_k:
                questions.append({
                    "question": f"{header} {question_text}",
                    "options": sorted_options,
                    "answer_key": ans_k
                })
        return questions
    except Exception as e:
        st.error(f"Lỗi đọc file Word: {str(e)}")
        return []


def shuffle_questions(questions):
    """Trộn câu hỏi và đáp án, ghi nhớ đáp án đúng sau khi trộn."""
    shuffled = []
    for q in random.sample(questions, len(questions)):
        opts = q["options"].copy()
        correct_text = next((o for o in opts if o.startswith(q["answer_key"] + ".")), None)
        random.shuffle(opts)
        # Gán lại nhãn A/B/C/D theo thứ tự mới
        relabeled = []
        new_ans = ""
        for idx, opt in enumerate(opts):
            new_label = chr(65 + idx)
            content = re.sub(r'^[A-D]\.\s*', '', opt)
            relabeled.append(f"{new_label}. {content}")
            if correct_text and content == re.sub(r'^[A-D]\.\s*', '', correct_text):
                new_ans = new_label
        shuffled.append({
            "question": q["question"],
            "options": relabeled,
            "answer_key": new_ans
        })
    return shuffled


def make_fingerprint():
    """Tạo fingerprint đơn giản chống spam nộp bài."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
    raw = f"{st.session_state.get('st_name','')}-{st.session_state.get('st_class','')}-{st.session_state.get('ma_de_dang_thi','')}-{now}"
    return hashlib.md5(raw.encode()).hexdigest()


def check_duplicate(fingerprint):
    try:
        res = supabase.table("student_results").select("id").eq("fingerprint", fingerprint).execute()
        return bool(res.data)
    except:
        return False


def render_timer(seconds_left, total_seconds):
    pct = seconds_left / total_seconds if total_seconds > 0 else 1
    warn_class = "timer-warning" if pct < 0.2 else ""
    mins, secs = divmod(seconds_left, 60)
    bar_width = int(pct * 100)
    st.markdown(f"""
    <div class="timer-box {warn_class}">
        ⏱️ Thời gian còn lại: {mins:02d}:{secs:02d}
        <div style="background:rgba(255,255,255,0.3);border-radius:8px;height:8px;margin-top:6px;">
            <div style="background:white;width:{bar_width}%;height:8px;border-radius:8px;transition:width 1s;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# TIÊU ĐỀ
# ============================================================
st.markdown("<h1>🏫 HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)
st.markdown("<div class='sub-title' style='font-size:1.05em;'>Trường THCS Lê Quý Đôn – Phường Hà Giang 1 – Tỉnh Tuyên Quang</div>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])


# ============================================================
# TAB HỌC SINH
# ============================================================
with tab_hs:
    try:
        raw_exam_res = supabase.table("exam_questions").select("ten_mon, ma_de, thoi_gian_phut").execute()
        all_exams = raw_exam_res.data if raw_exam_res.data else []
        subjects = sorted(list(set([
            str(item.get('ten_mon', '')).strip()
            for item in all_exams if item.get('ten_mon')
        ])))
    except:
        subjects = []
        all_exams = []
        st.warning("Không thể kết nối đến cơ sở dữ liệu")

    state = st.session_state

    # ---------- TRẠNG THÁI: ĐĂNG KÝ ----------
    if not state.get("is_testing") and not state.get("show_result"):

        st.subheader("📝 Đăng ký thông tin dự thi")

        # ── Chọn môn NGOÀI form để Streamlit cập nhật ngay lập tức ──
        if subjects:
            sel_subject = st.selectbox(
                "📚 Chọn Môn học:",
                options=["-- Chọn môn --"] + subjects,
                key="sel_subject_outer"
            )
            filtered_codes = [
                item['ma_de'] for item in all_exams
                if str(item.get('ten_mon', '')).strip() == sel_subject
            ]
        else:
            sel_subject = "-- Chọn môn --"
            filtered_codes = []

        with st.form("info_form"):
            name = st.text_input("👤 Họ và Tên của em:")
            actual_class = st.text_input("🏫 Lớp của em:")
            sel_ma_de = st.selectbox(
                "🔑 Chọn Mã đề thi:",
                options=(["-- Chọn mã đề --"] + filtered_codes) if filtered_codes else ["-- Chọn môn trước --"]
            )
            submitted = st.form_submit_button("🚀 BẮT ĐẦU LÀM BÀI", use_container_width=True)

        if submitted:
            if name.strip() and actual_class.strip() and sel_subject != "-- Chọn môn --" and sel_ma_de not in ("-- Chọn mã đề --", "-- Chọn môn trước --"):
                try:
                    ex_res = supabase.table("exam_questions").select("*").eq("ma_de", sel_ma_de).execute()
                    if ex_res.data:
                        ex_info = ex_res.data[0]
                        thoi_gian = ex_info.get("thoi_gian_phut", 15) * 60
                        quiz = shuffle_questions(ex_info["nội_dung_json"])
                        state.update({
                            "quiz_data": quiz,
                            "ma_de_dang_thi": sel_ma_de,
                            "st_name": name.strip(),
                            "st_class": actual_class.strip(),
                            "is_testing": True,
                            "show_result": False,
                            "mon_hoc": ex_info.get('ten_mon'),
                            "lop_kiem_tra": ex_info.get('ten_lop'),
                            "ngay_thi": ex_info.get('ngay_thi'),
                            "start_time": time.time(),
                            "total_seconds": thoi_gian,
                            "u_choices": {},
                            "confirm_submit": False,
                            "last_update": time.time()
                        })
                        st.rerun()
                    else:
                        st.error("Không tìm thấy đề thi!")
                except Exception as e:
                    st.error(f"Lỗi tải đề thi: {str(e)}")
            else:
                st.error("❌ Vui lòng điền đầy đủ thông tin trước khi bắt đầu!")

    # ---------- TRẠNG THÁI: ĐANG THI ----------
    elif state.get("is_testing"):
        elapsed = time.time() - state.get("start_time", time.time())
        total_s = state.get("total_seconds", 900)
        left = max(0, int(total_s - elapsed))

        render_timer(left, total_s)

        # Hết giờ → tự nộp
        if left == 0 and not state.get("auto_submitted"):
            state["auto_submitted"] = True
            st.warning("⏰ Hết giờ! Bài thi đã được tự động nộp.")
            
            u_choices = state.get("u_choices", {})
            quiz = state["quiz_data"]
            c_num = sum(
                1 for i, q in enumerate(quiz)
                if u_choices.get(i) and u_choices[i].startswith(q.get('answer_key', ''))
            )
            grade = round((c_num / len(quiz)) * 10, 2) if len(quiz) > 0 else 0
            fp = make_fingerprint()
            
            if not check_duplicate(fp):
                try:
                    supabase.table("student_results").insert({
                        "ma_de": state["ma_de_dang_thi"], "ho_ten": state["st_name"],
                        "lop": state["st_class"], "diem": grade,
                        "so_cau_dung": f"{c_num}/{len(quiz)}",
                        "lop_thi": state["mon_hoc"], "lop_kiem_tra": state["lop_kiem_tra"],
                        "ngay_thi": state["ngay_thi"], "fingerprint": fp
                    }).execute()
                except Exception as e:
                    st.error(f"Lỗi lưu kết quả: {str(e)}")
                    
            state.update({"is_testing": False, "show_result": True,
                          "last_grade": grade, "last_correct": c_num,
                          "last_quiz": quiz, "last_choices": u_choices})
            st.rerun()

        with st.form("quiz_form"):
            st.markdown(f"### 📖 MÔN THI: {state.get('mon_hoc', '').upper()}")
            st.info(f"👨‍🎓 **{state['st_name'].upper()}** — Mã đề: **{state['ma_de_dang_thi']}**")
            st.markdown("---")

            quiz = state["quiz_data"]
            u_choices = {}
            unanswered_warning = st.empty()

            for idx, q in enumerate(quiz):
                st.markdown(f"**Câu {idx+1}.** {q['question'].split(':', 1)[-1].strip()}")
                prev = state.get("u_choices", {}).get(idx)
                prev_idx = q["options"].index(prev) if prev and prev in q["options"] else None
                
                # Loại bỏ key cũ nếu có để tránh lỗi
                radio_key = f"q_{idx}"
                u_choices[idx] = st.radio(
                    f"câu_{idx}", q["options"],
                    index=prev_idx,
                    key=radio_key,
                    label_visibility="collapsed"
                )
                st.markdown("")

            col_a, col_b = st.columns([3, 1])
            with col_a:
                confirm = st.checkbox("✅ Tôi đã kiểm tra lại bài và muốn nộp bài thi.")
            with col_b:
                nop = st.form_submit_button("📤 NỘP BÀI", use_container_width=True)
            
            # Cập nhật lựa chọn vào session state khi form được render
            if u_choices:
                state["u_choices"] = u_choices

        if nop:
            # Kiểm tra câu chưa trả lời
            unanswered = [i+1 for i, q in enumerate(quiz) if not state["u_choices"].get(i)]
            
            if unanswered:
                st.warning(f"⚠️ Bạn chưa trả lời câu: **{', '.join(map(str, unanswered))}**. Hãy kiểm tra lại!")
            elif not confirm:
                st.warning("⚠️ Vui lòng tích xác nhận trước khi nộp bài.")
            else:
                # Tính điểm
                correct_count = sum(
                    1 for i, q in enumerate(quiz)
                    if state["u_choices"].get(i) and state["u_choices"][i].startswith(q.get('answer_key', ''))
                )
                grade = round((correct_count / len(quiz)) * 10, 2) if len(quiz) > 0 else 0
                fp = make_fingerprint()
                
                if check_duplicate(fp):
                    st.error("⚠️ Bài thi này đã được nộp. Không thể nộp lại!")
                else:
                    try:
                        supabase.table("student_results").insert({
                            "ma_de": state["ma_de_dang_thi"], "ho_ten": state["st_name"],
                            "lop": state["st_class"], "diem": grade,
                            "so_cau_dung": f"{correct_count}/{len(quiz)}",
                            "lop_thi": state["mon_hoc"], "lop_kiem_tra": state["lop_kiem_tra"],
                            "ngay_thi": state["ngay_thi"], "fingerprint": fp
                        }).execute()
                        
                        state.update({
                            "is_testing": False, "show_result": True,
                            "last_grade": grade, "last_correct": correct_count,
                            "last_quiz": quiz, "last_choices": state["u_choices"]
                        })
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi khi nộp bài: {str(e)}")

        # Tự động refresh để cập nhật timer
        current_time = time.time()
        if current_time - state.get("last_update", current_time) >= 1:
            state["last_update"] = current_time
            time.sleep(0.1)
            st.rerun()

    # ---------- TRẠNG THÁI: XEM KẾT QUẢ ----------
    elif state.get("show_result"):
        grade = state.get("last_grade", 0)
        c_num = state.get("last_correct", 0)
        quiz = state.get("last_quiz", [])
        choices = state.get("last_choices", {})
        total = len(quiz)

        if total > 0:
            if grade >= 8:
                emoji, color = "🏆", "#15803d"
            elif grade >= 5:
                emoji, color = "✅", "#0284c7"
            else:
                emoji, color = "📖", "#dc2626"

            st.markdown(f"""
            <div class="result-box">
                <div class="score-big" style="color:{color};">{emoji} {grade} điểm</div>
                <p style="font-size:1.1em; margin:6px 0;">Số câu đúng: <b>{c_num}/{total}</b></p>
                <p style="color:#64748b;">Học sinh: <b>{state['st_name'].upper()}</b> — Lớp: <b>{state['st_class']}</b></p>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("🔍 Xem lại đáp án chi tiết"):
                for idx, q in enumerate(quiz):
                    chosen = choices.get(idx)
                    correct = q.get("answer_key", "")
                    correct_text = next((o for o in q["options"] if o.startswith(correct + ".")), correct)

                    st.markdown(f"**Câu {idx+1}.** {q['question'].split(':', 1)[-1].strip()}")

                    if not chosen:
                        st.markdown(f"<div class='ans-skip'>⬜ Bỏ qua — Đáp án đúng: <b>{correct_text}</b></div>", unsafe_allow_html=True)
                    elif chosen.startswith(correct + "."):
                        st.markdown(f"<div class='ans-correct'>✅ Bạn chọn: <b>{chosen}</b></div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='ans-wrong'>❌ Bạn chọn: <b>{chosen}</b> — Đáp án đúng: <b>{correct_text}</b></div>", unsafe_allow_html=True)
                    st.markdown("")

        if st.button("🔄 Thi lại / Chọn đề khác", use_container_width=True):
            for k in ["is_testing","show_result","quiz_data","u_choices","last_quiz",
                      "last_choices","last_grade","last_correct","start_time",
                      "total_seconds","confirm_submit","auto_submitted","last_update"]:
                state.pop(k, None)
            st.rerun()


# ============================================================
# TAB QUẢN TRỊ VIÊN
# ============================================================
with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản trị:", type="password", key="admin_pwd")

    if pwd == ADMIN_PASSWORD:
        col1, col2 = st.columns([1, 1.8])

        # ---------- CỘT 1: ĐĂNG ĐỀ & QUẢN LÝ ----------
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
                    with st.spinner("Đang xử lý đề thi..."):
                        d_js = parse_docx_simple(f_word)
                        if d_js:
                            try:
                                supabase.table("exam_questions").upsert({
                                    "ma_de": n_ma, "nội_dung_json": d_js,
                                    "ten_mon": t_mon.strip(), "ten_lop": t_lop.strip(),
                                    "ngay_thi": d_thi.strftime("%d/%m/%Y"),
                                    "thoi_gian_phut": t_gian
                                }).execute()
                                st.success(f"✅ Đã đăng đề **{n_ma}** — {len(d_js)} câu hỏi!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Lỗi khi đăng đề: {str(e)}")
                        else:
                            st.error("❌ Không thể đọc được câu hỏi từ file Word!")
                else:
                    st.error("❌ Vui lòng điền đủ thông tin và tải file Word.")

            st.divider()
            st.subheader("🗑️ QUẢN LÝ DỮ LIỆU")

            try:
                q_res = supabase.table("exam_questions").select("ma_de, ten_mon").execute()
                if q_res.data:
                    opts = [f"{i['ma_de']} ({i.get('ten_mon','')})" for i in q_res.data]
                    ma_x = st.selectbox("Chọn đề để xóa:", ["-- Chọn --"] + opts)
                    if ma_x != "-- Chọn --":
                        real_ma = ma_x.split(" (")[0]
                        if st.button(f"🗑️ Xác nhận xóa đề **{real_ma}**", use_container_width=True):
                            supabase.table("exam_questions").delete().eq("ma_de", real_ma).execute()
                            st.success(f"Đã xóa đề {real_ma}!")
                            time.sleep(1)
                            st.rerun()
            except Exception as e:
                st.error(f"Lỗi tải danh sách đề: {str(e)}")

            st.markdown("")
            with st.expander("⚠️ Xóa toàn bộ kết quả thi"):
                if st.button("🔥 XÁC NHẬN XÓA TẤT CẢ KẾT QUẢ", type="primary", use_container_width=True):
                    try:
                        supabase.table("student_results").delete().neq("id", 0).execute()
                        st.success("Đã xóa toàn bộ kết quả!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Lỗi xóa kết quả: {str(e)}")

        # ---------- CỘT 2: KẾT QUẢ & THỐNG KÊ ----------
        with col2:
            st.subheader("📊 KẾT QUẢ & THỐNG KÊ")

            try:
                r_all = supabase.table("student_results").select("*").execute()
                if not r_all.data:
                    st.info("Chưa có kết quả nào.")
                else:
                    df = pd.DataFrame(r_all.data).sort_values(by="ho_ten")
                    df['created_at_vn'] = df['created_at'].apply(format_vietnam_time)
                    df['diem'] = pd.to_numeric(df['diem'], errors='coerce').fillna(0)

                    # Bộ lọc
                    all_mon = ["Tất cả"] + sorted(df['lop_thi'].dropna().unique().tolist())
                    sel_mon = st.selectbox("Lọc theo môn:", all_mon)
                    df_filtered = df if sel_mon == "Tất cả" else df[df['lop_thi'] == sel_mon]

                    if len(df_filtered) > 0:
                        # Thống kê nhanh
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Tổng bài thi", len(df_filtered))
                        c2.metric("Điểm TB", f"{df_filtered['diem'].mean():.2f}")
                        c3.metric("Điểm cao nhất", df_filtered['diem'].max())
                        c4.metric("Tỉ lệ đậu (≥5)", f"{(df_filtered['diem'] >= 5).mean()*100:.0f}%")

                        # Biểu đồ phân phối điểm
                        try:
                            import plotly.express as px
                            fig = px.histogram(
                                df_filtered, x="diem", nbins=10,
                                title="Phân phối điểm số",
                                labels={"diem": "Điểm", "count": "Số học sinh"},
                                color_discrete_sequence=["#2563eb"]
                            )
                            fig.update_layout(
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                font_family="Be Vietnam Pro, Arial",
                                margin=dict(t=40, b=20, l=10, r=10)
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        except ImportError:
                            st.bar_chart(df_filtered['diem'].value_counts().sort_index())

                        # Bảng kết quả
                        display_cols = ["ho_ten","lop","so_cau_dung","diem","ma_de","created_at_vn"]
                        display_names = {
                            "ho_ten": "Họ tên", "lop": "Lớp", "so_cau_dung": "Câu đúng",
                            "diem": "Điểm", "ma_de": "Mã đề", "created_at_vn": "Thời gian nộp"
                        }
                        
                        st.dataframe(
                            df_filtered[display_cols].rename(columns=display_names),
                            use_container_width=True, 
                            hide_index=True
                        )

                        st.divider()
                        st.subheader("🖨️ XUẤT PHIẾU KẾT QUẢ")
                        s_hs = st.selectbox("Chọn học sinh:", ["-- Chọn --"] + df['ho_ten'].tolist())

                        if s_hs != "-- Chọn --":
                            hs = df[df['ho_ten'] == s_hs].iloc[0]

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
                                    <tr><td><b>Kết quả:</b></td><td><b style='font-size:1.25em;color:#1e3a8a;'>{hs['diem']} điểm ({hs['so_cau_dung']})</b></td></tr>
                                </table>
                                <br><br>
                                <div style='display:flex;justify-content:space-between;text-align:center;color:black;'>
                                    <div style='width:45%;'><b>GIÁO VIÊN BỘ MÔN</b><br><br><br><br>(Ký và ghi rõ họ tên)</div>
                                    <div style='width:45%;'><b>HỌC SINH XÁC NHẬN</b><br><br><br><br>(Ký và ghi rõ họ tên)</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="utf-8">
    <title>Phiếu_{hs['ho_ten']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 50px; }}
        .container {{ border: 2px solid #1e3a8a; padding: 40px; border-radius: 10px; max-width: 800px; margin: auto; }}
        h2 {{ text-align: center; color: #1e3a8a; }}
        hr {{ border: 1px solid #1e3a8a; }}
        table {{ width: 100%; line-height: 3em; font-size: 1.15em; }}
        .footer {{ display: flex; justify-content: space-between; margin-top: 60px; text-align: center; }}
    </style>
</head>
<body onload="window.print()">
    <div class="container">
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
                                data=html_content,
                                file_name=f"Phieu_In_{hs['ho_ten']}.html",
                                mime="text/html",
                                use_container_width=True
                            )
                    else:
                        st.info("Không có dữ liệu cho môn học đã chọn")
            except Exception as e:
                st.error(f"Lỗi tải kết quả: {str(e)}")
                
    elif pwd:
        st.error("❌ Sai mật khẩu!")
