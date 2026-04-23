import streamlit as st
from docx import Document
from groq import Groq
from supabase import create_client
import json
import pandas as pd
from datetime import datetime

# --- KẾT NỐI HỆ THỐNG ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase = create_client(url, key)
    client_groq = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("⚠️ Lỗi cấu hình Secrets. Vui lòng kiểm tra lại URL và Key!")
    st.stop()

st.set_page_config(page_title="Hệ Thống Thi Online - Hà Giang", layout="wide", page_icon="🏔️")

# --- HÀM BỔ TRỢ ---
def parse_word(file):
    doc = Document(file)
    content = []
    for para in doc.paragraphs:
        text_parts = []
        for run in para.runs:
            # Nhận diện chữ đỏ (FF0000)
            if run.font.color and run.font.color.rgb and str(run.font.color.rgb) == "FF0000":
                text_parts.append(f"[DAP_AN]{run.text}[/DAP_AN]")
            else:
                text_parts.append(run.text)
        para_text = "".join(text_parts).strip()
        if para_text: content.append(para_text)
    return "\n".join(content)

def ai_process_quiz(text):
    prompt = f"""
    Bạn là chuyên gia số hóa đề thi. Trích xuất TẤT CẢ câu hỏi trong văn bản.
    Đáp án đúng là phần nằm trong [DAP_AN]...[/DAP_AN]. 
    Trả về duy nhất JSON: {{"questions": [ {{"question": "...", "options": ["A.","B.","C.","D."], "answer": "Chữ cái A/B/C/D"}} ]}}
    Văn bản: {text}
    """
    response = client_groq.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content).get("questions", [])

# --- GIAO DIỆN CHÍNH ---
st.title("🏔️ Hệ Thống Thi Trắc Nghiệm Trực Tuyến")
st.markdown("*Dành cho học sinh các xã vùng cao tỉnh Hà Giang*")

tab_gv, tab_hs = st.tabs(["👩‍🏫 Khu vực của Cô giáo", "👨‍🎓 Khu vực của Học sinh"])

# --- TAB GIÁO VIÊN ---
with tab_gv:
    col_de, col_diem = st.columns([1, 1.2])
    with col_de:
        st.subheader("📤 Tải đề thi lên hệ thống")
        ma_de = st.text_input("Nhập mã đề (Ví dụ: DIA10):")
        file_word = st.file_uploader("Chọn file Word (Đáp án bôi đỏ):", type=["docx"])
        
        if st.button("🚀 Kích hoạt đề thi Online"):
            if ma_de and file_word:
                with st.spinner("AI đang số hóa đề thi..."):
                    try:
                        questions = ai_process_quiz(parse_word(file_word))
                        # Đẩy lên Supabase
                        supabase.table("exam_questions").upsert({"ma_de": ma_de, "nội_dung_json": questions}).execute()
                        st.success(f"✅ Đã kích hoạt đề {ma_de} thành công!")
                    except Exception as e:
                        st.error(f"Lỗi: {e}")
            else:
                st.warning("Vui lòng nhập mã đề và chọn file!")

    with col_diem:
        st.subheader("📊 Bảng điểm học sinh")
        ma_xem = st.text_input("Nhập mã đề để xem kết quả nộp bài:")
        if ma_xem:
            res = supabase.table("student_results").select("*").eq("ma_de", ma_xem).order("created_at").execute()
            if res.data:
                df = pd.DataFrame(res.data)
                # Đổi tên cột cho đẹp
                df_show = df.rename(columns={"ho_ten": "Họ và Tên", "lop": "Lớp", "diem": "Điểm", "created_at": "Thời gian nộp"})
                st.dataframe(df_show[["Họ và Tên", "Lớp", "Điểm", "Thời gian nộp"]])
                
                csv = df_show.to_csv(index=False, encoding='utf-8-sig')
                st.download_button("📥 Tải bảng điểm (Excel/CSV)", csv, f"Diem_{ma_xem}.csv", "text/csv")
            else:
                st.info("Chưa có học sinh nào nộp bài cho mã đề này.")

# --- TAB HỌC SINH ---
with tab_hs:
    ma_thi = st.text_input("👉 Nhập mã đề thi cô giáo cho:")
    if ma_thi:
        # Lấy đề từ Supabase về máy học sinh
        data = supabase.table("exam_questions").select("nội_dung_json").eq("ma_de", ma_thi).execute()
        if data.data:
            quiz = data.data[0]["nội_dung_json"]
            st.success(f"Đã tải xong đề thi! Đề có {len(quiz)} câu hỏi.")
            
            with st.form("form_thi"):
                c1, c2 = st.columns(2)
                ten_hs = c1.text_input("Họ và Tên:")
                lop_hs = c2.text_input("Lớp:")
                st.divider()
                
                user_ans = {}
                for i, item in enumerate(quiz):
                    st.write(f"**Câu {i+1}: {item['question']}**")
                    user_ans[i] = st.radio(f"Chọn đáp án:", item['options'], key=f"q_{i}")
                    st.write("")

                if st.form_submit_button("NỘP BÀI THI"):
                    if ten_hs and lop_hs:
                        # Tính điểm
                        correct = sum(1 for i, item in enumerate(quiz) if user_ans[i].strip().upper().startswith(item['answer'].strip().upper()))
                        final_score = round((correct / len(quiz)) * 10, 2)
                        
                        # Gửi kết quả lên Supabase cho cô giáo
                        supabase.table("student_results").insert({
                            "ma_de": ma_thi, "ho_ten": ten_hs, "lop": lop_hs, "diem": final_score
                        }).execute()
                        
                        st.balloons()
                        st.header(f"Kết quả của {ten_hs}: {final_score} điểm")
                        st.write(f"Số câu đúng: {correct} / {len(quiz)}")
                    else:
                        st.error("Em cần nhập đầy đủ Họ tên và Lớp trước khi nộp bài!")
        else:
            st.error("Mã đề thi này không tồn tại trên hệ thống!")
