import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime
import pytz
import io
import plotly.express as px

# --- KẾT NỐI HỆ THỐNG ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)
st.set_page_config(page_title="Quản Lý Giáo Dục Lê Quý Đôn", layout="wide", page_icon="🏫")
ADMIN_PASSWORD = "141983" 

# --- HÀM HỖ TRỢ ---
def format_vietnam_time(utc_time_str):
    try:
        utc_dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        return utc_dt.astimezone(vn_tz).strftime("%H:%M:%S %d/%m/%Y")
    except: return utc_time_str

def parse_docx_smart(file):
    doc = Document(file)
    questions = []
    full_text_with_marks = ""
    for para in doc.paragraphs:
        para_text = "".join([f" [[DUNG]]{r.text}[[HET]] " if r.font.color and str(r.font.color.rgb) == "FF0000" else r.text for r in para.runs])
        full_text_with_marks += para_text + "\n"
    q_blocks = re.split(r'(?i)(Câu\s+\d+[:.])', full_text_with_marks)
    for i in range(1, len(q_blocks), 2):
        header = q_blocks[i].strip()
        parts = re.split(r'(?i)\b([A-D]\s*[:.])', q_blocks[i+1])
        question_text = parts[0].replace("[[DUNG]]", "").replace("[[HET]]", "").strip()
        options_dict = {}
        final_answer = ""
        for j in range(1, len(parts), 2):
            label = parts[j].strip().upper()[0]
            if "[[DUNG]]" in parts[j+1]: final_answer = label
            options_dict[label] = f"{label}. {parts[j+1].replace('[[DUNG]]', '').replace('[[HET]]', '').strip()}"
        sorted_options = [options_dict[k] for k in sorted(options_dict.keys())]
        if sorted_options:
            questions.append({"question": f"{header} {question_text}", "options": sorted_options, "answer": final_answer})
    return questions

# --- GIAO DIỆN ---
st.title("🏫 Hệ Thống Báo Cáo Giáo Dục Trực Tuyến")

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 KHU VỰC QUẢN LÝ GIÁO VIÊN"])

with tab_hs:
    ma_de_thi = st.text_input("🔑 Nhập Mã đề thi cô giáo giao:")
    if ma_de_thi:
        res = supabase.table("exam_questions").select("*").eq("ma_de", ma_de_thi).execute()
        if res.data:
            exam_info = res.data[0]
            quiz = exam_info["nội_dung_json"]
            st.info(f"📋 **Lớp:** {exam_info.get('ten_lop')} | **Ngày kiểm tra:** {exam_info.get('ngay_thi')}")
            
            with st.form("quiz_form"):
                name = st.text_input("Họ và Tên học sinh:")
                actual_class = st.text_input("Lớp (của em):")
                user_selections = {idx: st.radio(f"**{q['question']}**", q['options'], index=None, key=f"q_{idx}") for idx, q in enumerate(quiz)}
                
                if st.form_submit_button("NỘP BÀI THI", use_container_width=True):
                    if name and actual_class:
                        correct_num = sum(1 for i, q in enumerate(quiz) if user_selections[i] and user_selections[i].startswith(q['answer']))
                        grade = round((correct_num / len(quiz)) * 10, 2)
                        supabase.table("student_results").insert({
                            "ma_de": ma_de_thi, "ho_ten": name, "lop": actual_class, 
                            "diem": grade, "so_cau_dung": f"{correct_num}/{len(quiz)}",
                            "lop_thi": exam_info.get('ten_lop'), "ngay_thi": exam_info.get('ngay_thi')
                        }).execute()
                        st.balloons(); st.success(f"Chúc mừng {name.upper()}! Em đã nộp bài thành công.")
                    else: st.error("⚠️ Em cần điền tên và lớp nhé!")
        else: st.warning("Mã đề không tồn tại!")

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản lý:", type="password")
    if pwd == ADMIN_PASSWORD:
        col1, col2 = st.columns([1, 2.5])
        with col1:
            st.subheader("📤 Đăng đề mới")
            new_ma = st.text_input("Mã đề:")
            ten_lop = st.text_input("Lớp:")
            ngay_thi = st.date_input("Ngày kiểm tra:", value=datetime.now())
            word_file = st.file_uploader("Tải đề Word:", type=["docx"])
            if st.button("🚀 Kích hoạt đề"):
                if new_ma and word_file:
                    data = parse_docx_smart(word_file)
                    supabase.table("exam_questions").upsert({
                        "ma_de": new_ma, "nội_dung_json": data, 
                        "ten_lop": ten_lop, "ngay_thi": ngay_thi.strftime("%d/%m/%Y")
                    }).execute()
                    st.success("Kích hoạt thành công!")
            
            st.divider()
            if st.button("🔥 Xóa tất cả kết quả thi"):
                supabase.table("student_results").delete().neq("id", 0).execute()
                st.toast("Đã dọn dẹp kết quả!"); st.rerun()

        with col2:
            st.subheader("📊 Báo cáo & Bảng điểm theo Lớp")
            all_res = supabase.table("student_results").select("*").execute()
            if all_res.data:
                df = pd.DataFrame(all_res.data)
                df['created_at'] = df['created_at'].apply(format_vietnam_time)
                
                # 1. BỘ LỌC CHỌN LỚP
                list_lop = sorted(df['lop_thi'].dropna().unique().tolist())
                sel_lop = st.selectbox("📌 1. Chọn Lớp cần báo cáo:", list_lop)
                
                # 2. BỘ LỌC CHỌN NGÀY
                df_lop = df[df['lop_thi'] == sel_lop]
                list_ngay = sorted(df_lop['ngay_thi'].dropna().unique().tolist(), reverse=True)
                sel_ngay = st.selectbox("📅 2. Chọn Ngày kiểm tra của lớp này:", list_ngay)
                
                # LẤY DỮ LIỆU CUỐI CÙNG
                final_df = df_lop[df_lop['ngay_thi'] == sel_ngay].sort_values(by="ho_ten")
                
                st.markdown(f"### Báo cáo Lớp {sel_lop} - Ngày {sel_ngay}")
                st.write(f"📈 **Sĩ số nộp bài:** {len(final_df)} em | **Điểm trung bình:** {round(final_df['diem'].mean(), 2)}")
                
                # Biểu đồ phân bổ điểm
                fig = px.histogram(final_df, x="diem", nbins=10, 
                                   title=f"Phân phối điểm lớp {sel_lop} ({sel_ngay})",
                                   labels={'diem':'Điểm số', 'count':'Số học sinh'},
                                   color_discrete_sequence=['#17a2b8'])
                st.plotly_chart(fig, use_container_width=True)

                # --- PHẦN XUẤT EXCEL TIẾNG VIỆT "HẾT NƯỚC CHẤM" ---
                # Định nghĩa tên cột Tiếng Việt để hiển thị và xuất file
                mapping_cols = {
                    "ho_ten": "Họ và Tên",
                    "lop": "Lớp học",
                    "so_cau_dung": "Số câu đúng/Tổng",
                    "diem": "Điểm số",
                    "created_at": "Thời gian nộp bài",
                    "ma_de": "Mã đề thi"
                }

                # Hiển thị bảng trên web (đã đổi tên cột)
                st.dataframe(final_df[list(mapping_cols.keys())].rename(columns=mapping_cols), use_container_width=True)

                # Tạo file Excel Tiếng Việt
                export_df = final_df[list(mapping_cols.keys())].rename(columns=mapping_cols)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    export_df.to_excel(writer, index=False, sheet_name='Báo cáo chi tiết')
                    workbook = writer.book
                    worksheet = writer.sheets['Báo cáo chi tiết']
                    
                    # Trang trí tiêu đề (Màu xanh, chữ đậm, căn giữa)
                    header_format = workbook.add_format({
                        'bold': True, 'text_wrap': True, 'valign': 'vcenter',
                        'align': 'center', 'bg_color': '#D7E4BC', 'border': 1
                    })
                    
                    for col_num, value in enumerate(export_df.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                    
                    # Chỉnh độ rộng cột cho đẹp
                    worksheet.set_column('A:A', 25) # Cột Tên rộng ra
                    worksheet.set_column('B:F', 18) # Các cột khác vừa đủ
                
                # Nút tải file Excel xịn
                st.download_button(
                    label="📥 Tải Báo Cáo Excel Tiếng Việt (XLSX)", 
                    data=output.getvalue(), 
                    file_name=f"Bao_cao_{sel_lop}_{sel_ngay.replace('/','-')}.xlsx", 
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("Hiện chưa có dữ liệu nộp bài nào để báo cáo.")
