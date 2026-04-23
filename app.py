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

ADMIN_PASSWORD = "codieutuanhgia" 

# --- BỘ MÁY QUÉT ĐỀ THI CHUẨN XÁC V5 ---
def parse_docx_smart(file):
    doc = Document(file)
    questions = []
    full_text_with_marks = ""
    
    for para in doc.paragraphs:
        para_text = ""
        for run in para.runs:
            if run.font.color and run.font.color.rgb and str(run.font.color.rgb) == "FF0000":
                para_text += f" [[DUNG]]{run.text}[[HET]] "
            else:
                para_text += run.text
        full_text_with_marks += para_text + "\n"

    q_blocks = re.split(r'(?i)(Câu\s+\d+[:.])', full_text_with_marks)
    
    for i in range(1, len(q_blocks), 2):
        header = q_blocks[i].strip()
        content = q_blocks[i+1]
        parts = re.split(r'(?i)\b([A-D]\s*[:.])', content)
        
        question_text = parts[0].replace("[[DUNG]]", "").replace("[[HET]]", "").strip()
        options_dict = {} # Dùng dict để tự sắp xếp A, B, C, D
        final_answer = ""
        
        for j in range(1, len(parts), 2):
            label = parts[j].strip().upper()[0]
            text = parts[j+1].strip()
            if "[[DUNG]]" in text:
                final_answer = label
            clean_text = text.replace("[[DUNG]]", "").replace("[[HET]]", "").strip()
            if clean_text:
                options_dict[label] = f"{label}. {clean_text}"
        
        # Sắp xếp lại list options theo thứ tự A, B, C, D
        sorted_options = [options_dict[k] for k in sorted(options_dict.keys())]
        
        if sorted_options:
            questions.append({
                "question": f"{header} {question_text}",
                "options": sorted_options,
                "answer": final_answer
            })
    return questions

# --- GIAO DIỆN ---
st.title("🏫 Hệ Thống Thi Trắc Nghiệm Trực Tuyến")

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN LÝ GIÁO VIÊN"])

with tab_hs:
    ma_de_thi = st.text_input("🔑 Nhập Mã đề thi:")
    if ma_de_thi:
        res = supabase.table("exam_questions").select("nội_dung_json").eq("ma_de", ma_de_thi).execute()
        if res.data:
            quiz = res.data[0]["nội_dung_json"]
            st.info(f"📋 Đề thi gồm {len(quiz)} câu hỏi. Em hãy làm đầy đủ các câu mới có thể nộp bài!")
            
            with st.form("quiz_form"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Họ và Tên học sinh:")
                class_name = c2.text_input("Lớp:")
                st.write("---")
                
                user_selections = {}
                for idx, q in enumerate(quiz):
                    st.write(f"**{q['question']}**")
                    user_selections[idx] = st.radio(
                        "Chọn đáp án:", q['options'], index=None, 
                        key=f"quiz_{idx}", label_visibility="collapsed"
                    )
                    st.write("")
                
                submitted = st.form_submit_button("NỘP BÀI THI", use_container_width=True)
                
                if submitted:
                    # 1. KIỂM TRA XEM ĐÃ LÀM HẾT CHƯA
                    if not name or not class_name:
                        st.error("⚠️ Em cần điền Họ tên và Lớp nhé!")
                    elif any(v is None for v in user_selections.values()):
                        st.error("⚠️ Em chưa hoàn thành hết các câu hỏi. Hãy kiểm tra lại nhé!")
                    else:
                        # 2. TÍNH ĐIỂM
                        correct_num = sum(1 for i, q in enumerate(quiz) if user_selections[i].startswith(q['answer']))
                        grade = round((correct_num / len(quiz)) * 10, 2)
                        
                        # 3. LƯU KẾT QUẢ
                        supabase.table("student_results").insert({
                            "ma_de": ma_de_thi, "ho_ten": name, "lop": class_name, "diem": grade
                        }).execute()
                        
                        # 4. HIỂN THỊ ĐIỂM TO RÕ
                        st.balloons()
                        st.markdown(f"""
                        <div style="background-color:#d4edda; padding:20px; border-radius:10px; text-align:center;">
                            <h1 style="color:#155724;">KẾT QUẢ CỦA {name.upper()}</h1>
                            <h2 style="color:#155724;">Điểm số: {grade} / 10</h2>
                            <p>Số câu đúng: {correct_num} / {len(quiz)}</p>
                            <p style="font-style:italic;">Bài làm đã được gửi thành công đến cô giáo.</p>
                        </div>
                        """, unsafe_allow_width=True, unsafe_allow_html=True)
        else:
            st.warning("Mã đề này không tồn tại!")

with tab_gv:
    pwd = st.text_input("🔐 Nhập mật khẩu quản lý:", type="password")
    if pwd == ADMIN_PASSWORD:
        st.success("Chào cô giáo!")
        col1, col2 = st.columns([1, 1.5])
        with col1:
            new_ma = st.text_input("Mã đề mới:")
            word_file = st.file_uploader("Tải đề Word (Chữ đỏ là đáp án):", type=["docx"])
            if st.button("Kích hoạt đề"):
                if new_ma and word_file:
                    quiz_data = parse_docx_smart(word_file)
                    supabase.table("exam_questions").upsert({"ma_de": new_ma, "nội_dung_json": quiz_data}).execute()
                    st.success(f"Đã lưu xong {len(quiz_data)} câu!")
        with col2:
            all_data = supabase.table("student_results").select("*").execute()
            if all_data.data:
                df = pd.DataFrame(all_data.data)
                sel_ma = st.selectbox("Lọc theo mã đề:", ["Tất cả"] + sorted(df['ma_de'].unique().tolist()))
                final_df = df if sel_ma == "Tất cả" else df[df['ma_de'] == sel_ma]
                st.dataframe(final_df[["ma_de", "ho_ten", "lop", "diem", "created_at"]], use_container_width=True)
                st.download_button("📥 Tải bảng điểm", final_df.to_csv(index=False, encoding='utf-8-sig'), "Bang_diem.csv")
