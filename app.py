import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re

# --- KẾT NỐI SUPABASE ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Hệ Thống Thi Hà Giang V3", layout="wide")

# --- HÀM XỬ LÝ WORD THÔNG MINH (TÁCH ĐÁP ÁN NGANG & DỌC) ---
def parse_docx_pro(file):
    doc = Document(file)
    questions = []
    full_text_runs = []
    
    # Gom tất cả các cụm chữ và giữ thông tin màu sắc
    for para in doc.paragraphs:
        for run in para.runs:
            color = str(run.font.color.rgb) if run.font.color and run.font.color.rgb else "000000"
            full_text_runs.append({"text": run.text, "color": color})
        full_text_runs.append({"text": "\n", "color": "000000"})

    combined_text = ""
    red_content = []
    for item in full_text_runs:
        if item["color"] == "FF0000":
            # Đánh dấu nội dung đỏ bằng thẻ tạm
            combined_text += f"[[RED]]{item['text']}[[ENDRED]]"
        else:
            combined_text += item["text"]

    # Tách câu hỏi dựa trên chữ "Câu 1:", "Câu 2:"...
    raw_questions = re.split(r'(?i)(Câu\s+\d+[:.])', combined_text)
    
    for i in range(1, len(raw_questions), 2):
        q_header = raw_questions[i]
        q_body = raw_questions[i+1]
        
        # Tách đáp án A, B, C, D kể cả khi nằm cùng dòng
        options = re.split(r'(?i)([A-D]\s*[:.])', q_body)
        
        q_text = options[0].replace("[[RED]]", "").replace("[[ENDRED]]", "").strip()
        current_options = []
        correct_answer = ""
        
        for j in range(1, len(options), 2):
            opt_label = options[j].strip().upper()[0] # Lấy A, B, C hoặc D
            opt_text = options[j+1].strip()
            
            # Kiểm tra xem trong cụm đáp án này có chứa thẻ đỏ không
            if "[[RED]]" in opt_text:
                correct_answer = opt_label
            
            # Làm sạch thẻ đỏ trước khi lưu
            clean_opt = opt_text.replace("[[RED]]", "").replace("[[ENDRED]]", "").strip()
            current_options.append(f"{opt_label}. {clean_opt}")
            
        if q_header and current_options:
            questions.append({
                "question": f"{q_header} {q_text}",
                "options": current_options,
                "answer": correct_answer
            })
    return questions

# --- GIAO DIỆN ---
st.title("🏔️ Hệ Thống Quản Lý Thi Đa Mã Đề")

tab_gv, tab_hs = st.tabs(["👩‍🏫 Quản lý của Giáo viên", "👨‍🎓 Phòng thi Học sinh"])

with tab_gv:
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("📤 Tải lên nhiều mã đề")
        ma_de_input = st.text_input("Nhập mã đề (ví dụ: 101, 102...):")
        file = st.file_uploader("Chọn file Word:", type=["docx"])
        if st.button("Kích hoạt mã đề này"):
            if ma_de_input and file:
                data = parse_docx_pro(file)
                supabase.table("exam_questions").upsert({"ma_de": ma_de_input, "nội_dung_json": data}).execute()
                st.success(f"Đã kích hoạt mã đề {ma_de_input}!")

    with c2:
        st.subheader("📊 Kết quả tổng hợp")
        # Lấy tất cả kết quả từ Supabase
        all_res = supabase.table("student_results").select("*").execute()
        if all_res.data:
            df = pd.DataFrame(all_res.data)
            # Bộ lọc mã đề
            list_ma = ["Tất cả"] + sorted(df['ma_de'].unique().tolist())
            loc_ma = st.selectbox("Lọc kết quả theo mã đề:", list_ma)
            
            df_filter = df if loc_ma == "Tất cả" else df[df['ma_de'] == loc_ma]
            st.dataframe(df_filter[["ma_de", "ho_ten", "lop", "diem", "created_at"]], use_container_width=True)
            
            st.download_button("📥 Tải bảng điểm này", df_filter.to_csv(index=False, encoding='utf-8-sig'), "ket_qua.csv")

with tab_hs:
    st.subheader("📝 Học sinh làm bài")
    ma_thi = st.text_input("Nhập mã đề thi được giao:")
    if ma_thi:
        res_de = supabase.table("exam_questions").select("nội_dung_json").eq("ma_de", ma_thi).execute()
        if res_de.data:
            quiz = res_de.data[0]["nội_dung_json"]
            with st.form("thi_form"):
                col_a, col_b = st.columns(2)
                ten = col_a.text_input("Họ và tên:"); lp = col_b.text_input("Lớp:")
                st.write("---")
                ans = {}
                for idx, item in enumerate(quiz):
                    st.write(f"**{item['question']}**")
                    # Hiển thị đáp án (đã sạch màu đỏ)
                    ans[idx] = st.radio(f"Chọn câu trả lời cho câu {idx+1}:", item['options'], key=f"q_{idx}", label_visibility="collapsed")
                    st.write("")
                
                if st.form_submit_button("NỘP BÀI"):
                    if ten and lp:
                        dung = sum(1 for i, q in enumerate(quiz) if ans[i].startswith(q['answer']))
                        diem = round((dung/len(quiz))*10, 2)
                        supabase.table("student_results").insert({"ma_de": ma_thi, "ho_ten": ten, "lop": lp, "diem": diem}).execute()
                        st.balloons(); st.success(f"Kết quả của {ten}: {diem} điểm.")
                    else: st.error("Điền tên và lớp nhé!")
        else: st.error("Mã đề không tồn tại!")
