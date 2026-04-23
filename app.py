import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re

# --- KẾT NỐI HỆ THỐNG ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Hệ Thống Thi Online Lê Quý Đôn", layout="wide", page_icon="🏫")

# Mật khẩu quản lý dành cho cô giáo (Bạn có thể đổi mật khẩu này tùy ý)
ADMIN_PASSWORD = "141983" 

# --- BỘ MÁY QUÉT ĐỀ THI CHUẨN XÁC ---
def parse_docx_smart(file):
    doc = Document(file)
    questions = []
    full_text_with_marks = ""
    
    # Quét từng đoạn văn và đánh dấu chữ đỏ
    for para in doc.paragraphs:
        para_text = ""
        for run in para.runs:
            # Nhận diện màu đỏ FF0000
            if run.font.color and run.font.color.rgb and str(run.font.color.rgb) == "FF0000":
                para_text += f" [[DUNG]]{run.text}[[HET]] "
            else:
                para_text += run.text
        full_text_with_marks += para_text + "\n"

    # Tách các câu hỏi (Dựa trên từ khóa Câu 1, Câu 2...)
    q_blocks = re.split(r'(?i)(Câu\s+\d+[:.])', full_text_with_marks)
    
    for i in range(1, len(q_blocks), 2):
        header = q_blocks[i].strip()
        content = q_blocks[i+1]
        
        # Tách 4 phương án A, B, C, D kể cả nằm ngang
        parts = re.split(r'(?i)\b([A-D]\s*[:.])', content)
        
        question_text = parts[0].replace("[[DUNG]]", "").replace("[[HET]]", "").strip()
        options_list = []
        final_answer = ""
        
        # Nhặt các đáp án
        for j in range(1, len(parts), 2):
            label = parts[j].strip().upper()[0] # Lấy chữ A, B, C hoặc D
            text = parts[j+1].strip()
            
            # Nếu trong text có chứa dấu hiệu chữ đỏ
            if "[[DUNG]]" in text:
                final_answer = label
            
            clean_text = text.replace("[[DUNG]]", "").replace("[[HET]]", "").strip()
            if clean_text:
                options_list.append(f"{label}. {clean_text}")
        
        # Chỉ lấy những câu có đủ đáp án
        if options_list:
            questions.append({
                "question": f"{header} {question_text}",
                "options": options_list,
                "answer": final_answer
            })
    return questions

# --- GIAO DIỆN ---
st.title("🏫 Hệ Thống Thi Trắc Nghiệm Trực Tuyến")
st.markdown("*Dành cho học sinh trường Lê Quý Đôn - Hà Giang*")

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN LÝ GIÁO VIÊN"])

# --- TAB HỌC SINH (Mặc định mở tab này để các em vào làm luôn) ---
with tab_hs:
    ma_de_thi = st.text_input("🔑 Nhập Mã đề thi cô giáo giao (Ví dụ: 001, 002...):")
    if ma_de_thi:
        res = supabase.table("exam_questions").select("nội_dung_json").eq("ma_de", ma_de_thi).execute()
        if res.data:
            quiz = res.data[0]["nội_dung_json"]
            with st.form("quiz_form"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Họ và Tên học sinh:")
                class_name = c2.text_input("Lớp:")
                st.write("---")
                
                user_selections = {}
                for idx, q in enumerate(quiz):
                    st.write(f"**{q['question']}**")
                    # Radio không có giá trị mặc định để tránh tự chọn A
                    user_selections[idx] = st.radio(
                        "Chọn đáp án đúng:", 
                        q['options'], 
                        index=None, # Ép không chọn sẵn cái nào cả
                        key=f"quiz_{idx}",
                        label_visibility="collapsed"
                    )
                    st.write("")
                
                if st.form_submit_button("NỘP BÀI THI"):
                    if name and class_name and all(v is not None for v in user_selections.values()):
                        correct_num = sum(1 for i, q in enumerate(quiz) if user_selections[i].startswith(q['answer']))
                        grade = round((correct_num / len(quiz)) * 10, 2)
                        
                        supabase.table("student_results").insert({
                            "ma_de": ma_de_thi, "ho_ten": name, "lop": class_name, "diem": grade
                        }).execute()
                        
                        st.balloons()
                        st.success(f"Chúc mừng {name}! Em đã hoàn thành bài thi với {grade} điểm.")
                    else:
                        st.error("⚠️ Em hãy nhập đủ thông tin và chọn ĐẦY ĐỦ các câu trả lời nhé!")
        else:
            st.warning("Mã đề này chưa có trên hệ thống, em hãy kiểm tra lại!")

# --- TAB GIÁO VIÊN (CẦN MẬT KHẨU) ---
with tab_gv:
    pwd = st.text_input("🔐 Nhập mật khẩu quản lý để tiếp tục:", type="password")
    if pwd == ADMIN_PASSWORD:
        st.success("Xác thực thành công. Chào cô giáo!")
        col1, col2 = st.columns([1, 1.5])
        
        with col1:
            st.subheader("📤 Đăng đề thi mới")
            new_ma = st.text_input("Đặt mã đề mới:")
            word_file = st.file_uploader("Tải đề Word (Chữ đỏ là đáp án):", type=["docx"])
            if st.button("Kích hoạt đề online"):
                if new_ma and word_file:
                    with st.spinner("Đang xử lý dữ liệu..."):
                        quiz_data = parse_docx_smart(word_file)
                        supabase.table("exam_questions").upsert({"ma_de": new_ma, "nội_dung_json": quiz_data}).execute()
                        st.success(f"Đã lưu xong {len(quiz_data)} câu hỏi cho mã đề {new_ma}")
        
        with col2:
            st.subheader("📊 Kết quả và Bảng điểm")
            all_data = supabase.table("student_results").select("*").execute()
            if all_data.data:
                df = pd.DataFrame(all_data.data)
                list_m_de = ["Tất cả"] + sorted(df['ma_de'].unique().tolist())
                sel_ma = st.selectbox("Lọc theo mã đề:", list_m_de)
                
                final_df = df if sel_ma == "Tất cả" else df[df['ma_de'] == sel_ma]
                st.dataframe(final_df[["ma_de", "ho_ten", "lop", "diem", "created_at"]], use_container_width=True)
                
                st.download_button("📥 Tải bảng điểm này", final_df.to_csv(index=False, encoding='utf-8-sig'), "Bang_diem.csv")
                
                if st.button("🔥 Xóa sạch kết quả để thi lại"):
                    supabase.table("student_results").delete().neq("id", 0).execute()
                    st.rerun()
    elif pwd != "":
        st.error("Mật khẩu sai rồi bạn hiền ơi!")
