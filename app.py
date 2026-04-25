import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re
from datetime import datetime
import pytz
import io
import time

# --- KẾT NỐI HỆ THỐNG ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.set_page_config(page_title="Hệ Thống Thi Lê Quý Đôn", layout="wide", page_icon="🏫")
ADMIN_PASSWORD = "141983" 

bg_img = "https://raw.githubusercontent.com/ngacvantuanhg/tracnghiemlequydonhg/main/Anhnen.png"

# --- STYLE GIAO DIỆN ---
st.markdown(f"""
    <style>
    .stApp {{ background-image: url("{bg_img}"); background-attachment: fixed; background-size: cover; background-position: center; }}
    .main {{ background-color: rgba(255, 255, 255, 0.85); padding: 2rem; border-radius: 20px; }}
    h1, .sub-title {{ text-align: center !important; color: #1e3a8a !important; }}
    
    div[data-baseweb="input"], div[data-baseweb="select"] {{
        background-color: #ffffff !important; border: 2px solid #cbd5e1 !important; border-radius: 8px !important;
    }}
    
    [data-testid="stForm"] {{
        background-color: rgba(255, 255, 255, 0.95); border: 2px solid #1e3a8a;
        border-radius: 15px; padding: 2rem; max-width: 850px; margin: 0 auto !important;
    }}

    .printable-card {{
        background-color: white !important;
        padding: 30px !important;
        border: 2px solid #1e3a8a !important;
        color: black !important;
        border-radius: 10px;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- HÀM HỖ TRỢ ---
def format_vietnam_time(utc_time_str):
    try:
        utc_dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        return utc_dt.astimezone(vn_tz).strftime("%H:%M:%S %d/%m/%Y")
    except: return utc_time_str

# --- GIAO DIỆN CHÍNH ---
st.markdown("<h1>HỆ THỐNG THI TRỰC TUYẾN</h1>", unsafe_allow_html=True)

tab_hs, tab_gv = st.tabs(["👨‍🎓 PHÒNG THI HỌC SINH", "👩‍🏫 QUẢN TRỊ VIÊN"])

# ... (Tab học sinh giữ nguyên) ...

with tab_gv:
    pwd = st.text_input("🔐 Mật khẩu quản trị:", type="password", key="final_admin_pwd")
    if pwd == ADMIN_PASSWORD:
        c1, c2 = st.columns([1, 2])
        # ... (Cột 1 đăng đề giữ nguyên) ...
        
        with c2:
            st.subheader("📊 KẾT QUẢ VÀ XUẤT PHIẾU")
            r_all = supabase.table("student_results").select("*").execute()
            if r_all.data:
                df = pd.DataFrame(r_all.data).sort_values(by="ho_ten")
                df['created_at_vn'] = df['created_at'].apply(format_vietnam_time)
                st.dataframe(df[["ho_ten", "lop", "so_cau_dung", "diem", "ma_de"]], use_container_width=True)
                
                s_hs = st.selectbox("🖨️ Chọn học sinh dự kiến in:", ["-- Chọn --"] + df['ho_ten'].tolist())
                if s_hs != "-- Chọn --":
                    hs = df[df['ho_ten'] == s_hs].iloc[0]
                    
                    # 1. Hiển thị xem trước trên web
                    st.markdown(f"""
                    <div class='printable-card'>
                        <h3 style='text-align: center; color: #1e3a8a;'>PHIẾU MINH CHỨNG KẾT QUẢ KIỂM TRA</h3>
                        <p style='text-align: center;'>Trường THCS Lê Quý Đôn - Tuyên Quang</p>
                        <hr>
                        <table style='width: 100%; font-size: 1.1em; line-height: 2em;'>
                            <tr><td width='40%'><b>Học sinh:</b></td><td>{hs['ho_ten'].upper()}</td></tr>
                            <tr><td><b>Lớp:</b></td><td>{hs['lop']}</td></tr>
                            <tr><td><b>Môn kiểm tra:</b></td><td>{hs['lop_thi']}</td></tr>
                            <tr><td><b>Ngày nộp:</b></td><td>{hs['created_at_vn']}</td></tr>
                            <tr><td><b>Điểm số:</b></td><td><b style='font-size: 1.2em;'>{hs['diem']} điểm ({hs['so_cau_dung']})</b></td></tr>
                        </table>
                        <br>
                        <div style='display: flex; justify-content: space-between; text-align: center;'>
                            <div><b>GIÁO VIÊN</b><br><br><br>(Ký tên)</div>
                            <div><b>HỌC SINH</b><br><br><br>(Ký tên)</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 2. Tạo nội dung file HTML để tải về và in
                    html_to_download = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <title>Phieu_Minh_Chung_{hs['ho_ten']}</title>
                        <style>
                            body {{ font-family: Arial, sans-serif; padding: 50px; }}
                            .container {{ border: 2px solid #1e3a8a; padding: 40px; border-radius: 10px; max-width: 800px; margin: auto; }}
                            h2 {{ text-align: center; color: #1e3a8a; }}
                            hr {{ border: 1px solid #1e3a8a; }}
                            table {{ width: 100%; line-height: 3em; font-size: 1.2em; }}
                            .footer {{ display: flex; justify-content: space-between; margin-top: 50px; text-align: center; }}
                        </style>
                    </head>
                    <body onload="window.print()">
                        <div class="container">
                            <h2>PHIẾU MINH CHỨNG KẾT QUẢ KIỂM TRA</h2>
                            <p style="text-align: center;">Trường THCS Lê Quý Đôn - Tuyên Quang</p>
                            <hr>
                            <table>
                                <tr><td width="40%"><b>Họ và tên học sinh:</b></td><td>{hs['ho_ten'].upper()}</td></tr>
                                <tr><td><b>Lớp học:</b></td><td>{hs['lop']}</td></tr>
                                <tr><td><b>Môn kiểm tra:</b></td><td>{hs['lop_thi']}</td></tr>
                                <tr><td><b>Ngày nộp bài:</b></td><td>{hs['created_at_vn']}</td></tr>
                                <tr><td><b>Kết quả đạt được:</b></td><td><b>{hs['diem']} điểm ({hs['so_cau_dung']})</b></td></tr>
                            </table>
                            <div class="footer">
                                <div><b>GIÁO VIÊN BỘ MÔN</b><br><br><br><br>(Ký tên)</div>
                                <div><b>HỌC SINH XÁC NHẬN</b><br><br><br><br>(Ký tên)</div>
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                    
                    st.write("---")
                    st.download_button(
                        label=f"🚀 TẢI PHIẾU IN ({hs['ho_ten']})",
                        data=html_to_download,
                        file_name=f"Phieu_In_{hs['ho_ten']}.html",
                        mime="text/html"
                    )
                    st.info("💡 **Hướng dẫn:** Sau khi tải về, bạn hãy mở file đó lên. Trình duyệt sẽ tự động hiện lệnh in cực đẹp và đầy đủ nội dung!")
