import streamlit as st
from docx import Document
from groq import Groq
import json

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(page_title="Thi Trắc Nghiệm Địa Lý", page_icon="📝", layout="wide")

# Khởi tạo bộ nhớ tạm (Session State)
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = []
if "score" not in st.session_state:
    st.session_state.score = 0
if "current_question" not in st.session_state:
    st.session_state.current_question = 0
if "quiz_started" not in st.session_state:
    st.session_state.quiz_started = False
if "answered" not in st.session_state:
    st.session_state.answered = False

# Lấy chìa khóa Groq (Nhớ cài trong Settings > Secrets của Streamlit nhé)
try:
    api_key = st.secrets["GROQ_API_KEY"]
except KeyError:
    st.error("⚠️ Chưa có API Key của Groq. Vui lòng cài đặt trong phần Secrets!")
    api_key = None

# --- 2. HÀM XỬ LÝ (TRỢ LÝ AI ĐỌC FILE) ---
def parse_word_doc(file):
    """Đọc chữ từ file Word"""
    doc = Document(file)
    full_text = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
    return "\n".join(full_text)

def generate_quiz_from_text(text):
    """Nhờ AI đọc hiểu văn bản và bóc tách thành dạng bảng câu hỏi chuẩn"""
    client = Groq(api_key=api_key)
    prompt = f"""
    Bạn là một chuyên gia giáo dục. Hãy đọc bộ đề thi sau đây và trích xuất thành định dạng JSON chuẩn.
    BẮT BUỘC trả về một đối tượng JSON có cấu trúc như sau:
    {{
        "questions": [
            {{
                "question": "Nội dung câu hỏi?",
                "options": ["A. Đáp án 1", "B. Đáp án 2", "C. Đáp án 3", "D. Đáp án 4"],
                "answer": "A", 
                "explanation": "Giải thích ngắn gọn tại sao đáp án này đúng."
            }}
        ]
    }}
    
    Nội dung file Word giáo viên tải lên:
    {text}
    """
    
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1, # Hạ nhiệt độ xuống thấp nhất để AI không tự bịa thêm
        response_format={"type": "json_object"} # Bắt buộc xuất ra JSON
    )
    
    result = json.loads(response.choices[0].message.content)
    return result.get("questions", [])

# --- 3. GIAO DIỆN CHÍNH ---
st.title("📝 Hệ Thống Thi Trắc Nghiệm Tương Tác")
st.markdown("*Trường THCS Lê Quý Đôn - Môn Địa Lý*")
st.markdown("---")

# --- KHU VỰC DÀNH CHO GIÁO VIÊN (SIDEBAR) ---
with st.sidebar:
    st.header("👩‍🏫 Khu vực Giáo viên")
    st.info("Cô giáo tải file Word (.docx) chứa bộ câu hỏi lên đây để hệ thống tự động tạo đề thi online.")
    
    uploaded_file = st.file_uploader("Tải file Word lên", type=["docx"])
    
    if uploaded_file and api_key:
        if st.button("🚀 Xây dựng Đề Thi Online", use_container_width=True):
            with st.spinner("AI đang đọc file Word và tạo đề thi..."):
                try:
                    raw_text = parse_word_doc(uploaded_file)
                    questions = generate_quiz_from_text(raw_text)
                    
                    if questions:
                        # Reset lại bài thi mới
                        st.session_state.quiz_data = questions
                        st.session_state.quiz_started = True
                        st.session_state.current_question = 0
                        st.session_state.score = 0
                        st.session_state.answered = False
                        st.success(f"Đã tạo thành công {len(questions)} câu hỏi!")
                    else:
                        st.error("Không tìm thấy câu hỏi nào trong file. Vui lòng kiểm tra lại!")
                except Exception as e:
                    st.error(f"Có lỗi khi xử lý file: {e}")

# --- KHU VỰC DÀNH CHO HỌC SINH (MÀN HÌNH CHÍNH) ---
if st.session_state.quiz_started and st.session_state.quiz_data:
    q_idx = st.session_state.current_question
    total_q = len(st.session_state.quiz_data)
    
    # Thanh tiến trình bài làm
    progress = (q_idx) / total_q
    st.progress(progress)
    st.write(f"**Câu {q_idx + 1} / {total_q}** (Điểm hiện tại: {st.session_state.score})")
    
    # Lấy câu hỏi hiện tại
    current_q = st.session_state.quiz_data[q_idx]
    
    # Hiển thị nội dung câu hỏi
    st.subheader(current_q["question"])
    
    # Form để chọn đáp án (Tránh trang bị load lại liên tục)
    with st.form(key=f"quiz_form_{q_idx}"):
        user_choice = st.radio("Chọn một đáp án:", current_q["options"])
        submit_btn = st.form_submit_button("Nộp câu trả lời")
        
        if submit_btn:
            st.session_state.answered = True
            # Kiểm tra đúng sai (Lấy chữ cái đầu tiên A, B, C, D để so sánh)
            correct_letter = current_q["answer"].strip().upper()[0]
            user_letter = user_choice.strip().upper()[0]
            
            if user_letter == correct_letter:
                st.success("✅ Tuyệt vời! Em đã trả lời chính xác.")
                st.session_state.score += 1
            else:
                st.error(f"❌ Tiếc quá! Đáp án đúng phải là: {current_q['answer']}")
            
            # Hiện phần giải thích của AI
            st.info(f"💡 **Giải thích:** {current_q.get('explanation', 'Không có giải thích thêm.')}")

    # Nút chuyển câu hỏi (Chỉ hiện khi đã nộp câu trả lời)
    if st.session_state.answered:
        if q_idx + 1 < total_q:
            if st.button("Tiếp tục ➡️", type="primary"):
                st.session_state.current_question += 1
                st.session_state.answered = False
                st.rerun()
        else:
            st.markdown("---")
            st.header("🎉 CHÚC MỪNG EM ĐÃ HOÀN THÀNH BÀI THI!")
            st.subheader(f"🏆 Tổng điểm: {st.session_state.score} / {total_q}")
            st.balloons()
            
            if st.button("🔄 Làm lại bài thi"):
                st.session_state.current_question = 0
                st.session_state.score = 0
                st.session_state.answered = False
                st.rerun()

else:
    # Màn hình chờ khi chưa tải đề
    st.info("👈 Cô giáo vui lòng tải bộ đề thi (File Word) ở menu bên trái để bắt đầu!")
