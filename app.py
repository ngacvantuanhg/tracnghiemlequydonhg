import streamlit as st
from docx import Document
from groq import Groq
import json

# --- CẤU HÌNH ---
st.set_page_config(page_title="Hệ Thống Thi Trắc Nghiệm Lê Quý Đôn", page_icon="📝", layout="wide")

if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = []
if "quiz_started" not in st.session_state:
    st.session_state.quiz_started = False
if "ma_de_chuan" not in st.session_state:
    st.session_state.ma_de_chuan = ""

api_key = st.secrets["GROQ_API_KEY"]

# --- HÀM ĐỌC FILE WORD (NHẬN DIỆN CHỮ ĐỎ) ---
def parse_word_with_colors(file):
    doc = Document(file)
    content = []
    for para in doc.paragraphs:
        text_parts = []
        for run in para.runs:
            # Kiểm tra nếu chữ có màu đỏ (Color hex: FF0000)
            if run.font.color and run.font.color.rgb and str(run.font.color.rgb) == "FF0000":
                text_parts.append(f"[DAP_AN_DUNG]{run.text}[/DAP_AN_DUNG]")
            else:
                text_parts.append(run.text)
        
        full_para_text = "".join(text_parts).strip()
        if full_para_text:
            content.append(full_para_text)
    return "\n".join(content)

# --- NHỜ AI BÓC TÁCH DỮ LIỆU ---
def generate_quiz_ai(text):
    client = Groq(api_key=api_key)
    prompt = f"""
    Bạn là trợ lý số hóa đề thi. Hãy trích xuất câu hỏi từ văn bản dưới đây.
    QUY TẮC QUAN TRỌNG: 
    1. Đáp án đúng là cụm từ nằm trong thẻ [DAP_AN_DUNG]...[/DAP_AN_DUNG]. Hãy lấy đó làm đáp án chuẩn, KHÔNG TỰ GIẢI.
    2. Phải trích xuất ĐẦY ĐỦ TẤT CẢ câu hỏi có trong văn bản, không được bỏ sót bất kỳ câu nào.
    
    Xuất ra định dạng JSON mảng 'questions':
    [
      {{"question": "...", "options": ["A.","B.","C.","D."], "answer": "Chữ cái A hoặc B hoặc C hoặc D", "explanation": "Giải thích dựa trên đáp án đỏ"}}
    ]
    
    Nội dung:
    {text}
    """
    
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0, # Chính xác tuyệt đối
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content).get("questions", [])

# --- GIAO DIỆN ---
st.title("📝 Hệ Thống Thi Trắc Nghiệm Địa Lý")

# TAB GIÁO VIÊN & HỌC SINH
tab_gv, tab_hs = st.tabs(["👩‍🏫 Dành cho Giáo viên", "👨‍🎓 Dành cho Học sinh"])

with tab_gv:
    st.subheader("Thiết lập đề thi")
    ma_de_input = st.text_input("1. Đặt mã đề thi (Ví dụ: DIA101, DE01...):")
    file_word = st.file_uploader("2. Tải file Word (Đáp án đúng bôi đỏ chữ):", type=["docx"])
    
    if st.button("Xây dựng đề thi online"):
        if ma_de_input and file_word:
            with st.spinner("Đang quét đáp án đỏ và tạo đề..."):
                raw_text = parse_word_with_colors(file_word)
                st.session_state.quiz_data = generate_quiz_ai(raw_text)
                st.session_state.ma_de_chuan = ma_de_input
                st.success(f"Đã tạo xong đề {ma_de_input} với {len(st.session_state.quiz_data)} câu hỏi!")
        else:
            st.warning("Vui lòng nhập mã đề và tải file!")

with tab_hs:
    if not st.session_state.quiz_data:
        st.info("Hiện chưa có đề thi nào được kích hoạt.")
    else:
        ma_nhap = st.text_input("Nhập mã đề thi để bắt đầu làm bài:")
        if ma_nhap == st.session_state.ma_de_chuan:
            st.success("Mã đề chính xác! Mời em làm bài.")
            
            # Hiển thị danh sách câu hỏi làm bài tập tập trung
            score = 0
            with st.form("quiz_form"):
                user_answers = {}
                for idx, q in enumerate(st.session_state.quiz_data):
                    st.write(f"**Câu {idx+1}: {q['question']}**")
                    user_answers[idx] = st.radio(f"Chọn đáp án câu {idx+1}:", q['options'], key=f"radio_{idx}")
                    st.markdown("---")
                
                if st.form_submit_button("Nộp bài và xem điểm"):
                    st.balloons()
                    for idx, q in enumerate(st.session_state.quiz_data):
                        correct_letter = q['answer'].strip().upper()[0]
                        if user_answers[idx].startswith(correct_letter):
                            score += 1
                    
                    st.header(f"Kết quả: {score} / {len(st.session_state.quiz_data)}")
                    st.write("Cô giáo dặn: Các em xem lại các câu sai để nhớ bài nhé!")
        elif ma_nhap != "":
            st.error("Mã đề không đúng, vui lòng hỏi lại cô giáo!")
