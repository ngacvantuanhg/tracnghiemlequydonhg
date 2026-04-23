import streamlit as st
from docx import Document
from groq import Groq
import json
import pandas as pd
from datetime import datetime

# --- 1. CẤU HÌNH ---
st.set_page_config(page_title="Thi Trắc Nghiệm Online - Hà Giang", page_icon="🏔️", layout="wide")

# Khởi tạo bộ nhớ hệ thống
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = []
if "ma_de_chuan" not in st.session_state:
    st.session_state.ma_de_chuan = ""
if "danh_sach_ket_qua" not in st.session_state:
    st.session_state.danh_sach_ket_qua = []

api_key = st.secrets["GROQ_API_KEY"]

# --- 2. HÀM XỬ LÝ FILE WORD (NHẬN DIỆN CHỮ ĐỎ CHUẨN) ---
def parse_word_with_red_text(file):
    doc = Document(file)
    content = []
    for para in doc.paragraphs:
        text_parts = []
        for run in para.runs:
            # Kiểm tra mã màu đỏ FF0000 hoặc các biến thể đỏ
            is_red = False
            if run.font.color and run.font.color.rgb:
                color_str = str(run.font.color.rgb).upper()
                if color_str in ["FF0000", "FF0001", "ED1C24"]: # Các mã màu đỏ phổ biến
                    is_red = True
            
            if is_red:
                text_parts.append(f"[DAP_AN]{run.text}[/DAP_AN]")
            else:
                text_parts.append(run.text)
        
        para_full = "".join(text_parts).strip()
        if para_full: content.append(para_full)
    return "\n".join(content)

def generate_quiz_ai(text):
    client = Groq(api_key=api_key)
    # Prompt yêu cầu AI giữ nguyên số lượng câu hỏi
    prompt = f"""
    Bạn là hệ thống số hóa đề thi chuyên nghiệp. 
    NHIỆM VỤ: Trích xuất TẤT CẢ các câu hỏi có trong văn bản. 
    QUY TẮC ĐÁP ÁN: Đáp án đúng là nội dung nằm trong thẻ [DAP_AN]...[/DAP_AN]. Hãy đối chiếu nội dung đó với các phương án A,B,C,D để xác định chữ cái đáp án đúng.
    
    Yêu cầu trả về JSON định dạng:
    {{"questions": [
      {{"question": "Câu hỏi...", "options": ["A.","B.","C.","D."], "answer": "Chữ cái đáp án", "explanation": "Giải thích"}}
    ]}}
    
    Văn bản nguồn:
    {text}
    """
    
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content).get("questions", [])

# --- 3. GIAO DIỆN ---
st.title("🏔️ Hệ Thống Thi Trắc Nghiệm Trực Tuyến")
st.markdown("*Hỗ trợ học sinh vùng cao Hà Giang học tập*")

tab_gv, tab_hs = st.tabs(["👩‍🏫 Khu vực của Cô giáo", "👨‍🎓 Khu vực của Học sinh"])

# --- TAB GIÁO VIÊN ---
with tab_gv:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Cài đặt đề thi")
        ma_de = st.text_input("Bước 1: Đặt mã đề (Ví dụ: DIA8_KY1):")
        file_word = st.file_uploader("Bước 2: Tải đề Word (Chữ đáp án bôi đỏ):", type=["docx"])
        
        if st.button("Kích hoạt đề thi ngay"):
            if ma_de and file_word:
                with st.spinner("Đang xử lý đề thi..."):
                    raw_text = parse_word_with_red_text(file_word)
                    st.session_state.quiz_data = generate_quiz_ai(raw_text)
                    st.session_state.ma_de_chuan = ma_de
                    st.success(f"✅ Đề {ma_de} đã sẵn sàng với {len(st.session_state.quiz_data)} câu hỏi.")
    
    with col2:
        st.subheader("Kết quả làm bài của học sinh")
        if st.session_state.danh_sach_ket_qua:
            df = pd.DataFrame(st.session_state.danh_sach_ket_qua)
            st.dataframe(df)
            
            # Nút tải file Excel/CSV
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Tải bảng điểm về máy (Excel/CSV)",
                data=csv,
                file_name=f"Ket_qua_{st.session_state.ma_de_chuan}.csv",
                mime="text/csv",
            )
            if st.button("Xóa danh sách cũ để làm đợt mới"):
                st.session_state.danh_sach_ket_qua = []
                st.rerun()
        else:
            st.write("Chưa có học sinh nào nộp bài.")

# --- TAB HỌC SINH ---
with tab_hs:
    if not st.session_state.quiz_data:
        st.info("Hiện tại chưa có đề thi nào được mở. Vui lòng đợi cô giáo!")
    else:
        with st.form("form_lam_bai"):
            st.subheader("Thông tin học sinh")
            c1, c2 = st.columns(2)
            ho_ten = c1.text_input("Họ và Tên học sinh:")
            lop = c2.text_input("Lớp:")
            ma_nhap = st.text_input("Nhập mã đề thi cô giáo cho:")
            
            st.divider()
            
            if ma_nhap == st.session_state.ma_de_chuan:
                st.write("--- PHẦN LÀM BÀI ---")
                answers = {}
                for i, q in enumerate(st.session_state.quiz_data):
                    st.write(f"**Câu {i+1}: {q['question']}**")
                    answers[i] = st.radio(f"Chọn đáp án câu {i+1}:", q['options'], key=f"ans_{i}")
                
                submitted = st.form_submit_button("NỘP BÀI")
                
                if submitted:
                    if not ho_ten or not lop:
                        st.error("Em cần nhập đầy đủ Họ tên và Lớp nhé!")
                    else:
                        # Tính điểm
                        correct_count = 0
                        for i, q in enumerate(st.session_state.quiz_data):
                            if answers[i].startswith(q['answer'].strip().upper()):
                                correct_count += 1
                        
                        # Lưu kết quả vào hệ thống cho cô giáo
                        result = {
                            "Thời gian": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
                            "Họ Tên": ho_ten,
                            "Lớp": lop,
                            "Số câu đúng": f"{correct_count}/{len(st.session_state.quiz_data)}",
                            "Điểm": round((correct_count / len(st.session_state.quiz_data)) * 10, 2)
                        }
                        st.session_state.danh_sach_ket_qua.append(result)
                        
                        st.balloons()
                        st.success(f"Chúc mừng {ho_ten}! Em đã hoàn thành bài thi.")
                        st.write(f"Kết quả của em: **{correct_count} / {len(st.session_state.quiz_data)}** câu đúng.")
            elif ma_nhap != "":
                st.form_submit_button("Kiểm tra mã đề")
                st.error("Mã đề không chính xác rồi em ơi!")
            else:
                st.form_submit_button("Vào làm bài")
