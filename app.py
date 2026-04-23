import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
from datetime import datetime

# --- KẾT NỐI HỆ THỐNG ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Thi Online Hà Giang - Bản Chuẩn", layout="wide", page_icon="🏔️")

# --- HÀM TỰ ĐỘNG TÁCH CÂU HỎI TỪ WORD (KHÔNG DÙNG AI) ---
def parse_word_to_quiz(file):
    doc = Document(file)
    questions = []
    current_q = None
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text: continue
        
        # Kiểm tra xem dòng này có phải là Câu hỏi không (thường bắt đầu bằng chữ "Câu")
        if text.upper().startswith("CÂU"):
            if current_q: questions.append(current_q)
            current_q = {"question": text, "options": [], "answer": ""}
        
        # Kiểm tra xem dòng này có phải là Đáp án không (thường bắt đầu bằng A., B., C., D.)
        elif current_q and (text.upper().startswith("A.") or text.upper().startswith("B.") or 
                            text.upper().startswith("C.") or text.upper().startswith("D.")):
            current_q["options"].append(text)
            
            # QUAN TRỌNG: Kiểm tra xem trong dòng này có chữ nào BÔI ĐỎ không
            for run in para.runs:
                if run.font.color and run.font.color.rgb and str(run.font.color.rgb) == "FF0000":
                    # Nếu thấy chữ đỏ, lấy chữ cái đầu tiên (A, B, C hoặc D) làm đáp án đúng
                    current_q["answer"] = text[0].upper()
                    break
                    
    if current_q: questions.append(current_q)
    return questions

# --- GIAO DIỆN CHÍNH ---
st.title("🏔️ Hệ Thống Thi Trắc Nghiệm Hà Giang")
st.markdown("*Phiên bản xử lý dữ liệu trực tiếp - Chính xác 100%*")

tab_gv, tab_hs = st.tabs(["👩‍🏫 Khu vực của Cô giáo", "👨‍🎓 Khu vực của Học sinh"])

with tab_gv:
    col_de, col_diem = st.columns([1, 1.2])
    with col_de:
        st.subheader("📤 Kích hoạt đề thi")
        ma_de = st.text_input("Nhập mã đề:")
        file_word = st.file_uploader("Tải file Word (Đáp án đúng bôi đỏ):", type=["docx"])
        
        if st.button("🚀 Đưa đề lên hệ thống"):
            if ma_de and file_word:
                with st.spinner("Đang trích xuất dữ liệu..."):
                    quiz_data = parse_word_to_quiz(file_word)
                    if quiz_data:
                        supabase.table("exam_questions").upsert({"ma_de": ma_de, "nội_dung_json": quiz_data}).execute()
                        st.success(f"✅ Đã tải xong {len(quiz_data)} câu hỏi cho đề {ma_de}!")
                    else:
                        st.error("Không tìm thấy câu hỏi. Hãy kiểm tra định dạng file!")

    with col_diem:
        st.subheader("📊 Kết quả thi")
        ma_xem = st.text_input("Mã đề cần xem điểm:")
        if ma_xem:
            res = supabase.table("student_results").select("*").eq("ma_de", ma_xem).execute()
            if res.data:
                df = pd.DataFrame(res.data).rename(columns={"ho_ten": "Họ Tên", "lop": "Lớp", "diem": "Điểm"})
                st.dataframe(df[["Họ Tên", "Lớp", "Điểm"]])
                st.download_button("📥 Tải bảng điểm", df.to_csv(index=False, encoding='utf-8-sig'), f"Diem_{ma_xem}.csv")

with tab_hs:
    ma_thi = st.text_input("👉 Nhập mã đề thi:")
    if ma_thi:
        data = supabase.table("exam_questions").select("nội_dung_json").eq("ma_de", ma_thi).execute()
        if data.data:
            quiz = data.data[0]["nội_dung_json"]
            with st.form("form_thi"):
                c1, c2 = st.columns(2); ten = c1.text_input("Họ Tên:"); lop = c2.text_input("Lớp:")
                st.divider()
                ans = {}
                for i, q in enumerate(quiz):
                    st.write(f"**Câu {i+1}: {q['question']}**")
                    ans[i] = st.radio(f"Chọn đáp án:", q['options'], key=f"q_{i}")
                
                if st.form_submit_button("NỘP BÀI"):
                    if ten and lop:
                        correct = sum(1 for i, q in enumerate(quiz) if ans[i].startswith(q['answer']))
                        score = round((correct/len(quiz))*10, 2)
                        supabase.table("student_results").insert({"ma_de": ma_thi, "ho_ten": ten, "lop": lop, "diem": score}).execute()
                        st.balloons()
                        st.success(f"Chúc mừng {ten}! Điểm của em là: {score}")
                    else: st.error("Em hãy nhập đủ tên và lớp!")
        else: st.error("Mã đề không đúng!")
