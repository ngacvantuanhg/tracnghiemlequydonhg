list_lop = sorted(df['lop_thi'].dropna().unique().tolist())
sel_lop = st.selectbox("📌 1. Chọn Lớp cần báo cáo:", list_lop)

                # 2. BỘ LỌC CHỌN NGÀY (CHỈ HIỆN CÁC NGÀY CỦA LỚP ĐÃ CHỌN)
                # 2. BỘ LỌC CHỌN NGÀY
df_lop = df[df['lop_thi'] == sel_lop]
list_ngay = sorted(df_lop['ngay_thi'].dropna().unique().tolist(), reverse=True)
sel_ngay = st.selectbox("📅 2. Chọn Ngày kiểm tra của lớp này:", list_ngay)
@@ -124,31 +124,54 @@ def parse_docx_smart(file):
st.markdown(f"### Báo cáo Lớp {sel_lop} - Ngày {sel_ngay}")
st.write(f"📈 **Sĩ số nộp bài:** {len(final_df)} em | **Điểm trung bình:** {round(final_df['diem'].mean(), 2)}")

                # Biểu đồ Plotly
                # Biểu đồ phân bổ điểm
fig = px.histogram(final_df, x="diem", nbins=10, 
title=f"Phân phối điểm lớp {sel_lop} ({sel_ngay})",
labels={'diem':'Điểm số', 'count':'Số học sinh'},
color_discrete_sequence=['#17a2b8'])
st.plotly_chart(fig, use_container_width=True)

                # Bảng dữ liệu
                show_cols = ["ho_ten", "lop", "so_cau_dung", "diem", "created_at", "ma_de"]
                st.dataframe(final_df[show_cols].rename(columns={
                    "ho_ten": "Họ và Tên", "lop": "Lớp học", "so_cau_dung": "Đúng/Tổng",
                    "diem": "Điểm", "created_at": "Thời gian nộp", "ma_de": "Mã đề"
                }), use_container_width=True)
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

                # Xuất file Excel chuẩn báo cáo
                # Hiển thị bảng trên web (đã đổi tên cột)
                st.dataframe(final_df[list(mapping_cols.keys())].rename(columns=mapping_cols), use_container_width=True)

                # Tạo file Excel Tiếng Việt
                export_df = final_df[list(mapping_cols.keys())].rename(columns=mapping_cols)
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    final_df[show_cols].to_excel(writer, index=False, sheet_name='Bao_cao_chi_tiet')
                    export_df.to_excel(writer, index=False, sheet_name='Báo cáo chi tiết')
workbook = writer.book
                    worksheet = writer.sheets['Bao_cao_chi_tiet']
                    h_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center'})
                    for c_num, val in enumerate(show_cols): worksheet.write(0, c_num, val, h_format)
                    worksheet.set_column('A:F', 20)
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

                st.download_button("📥 Tải Báo Cáo Excel (XLSX)", data=output.getvalue(), 
                                   file_name=f"Bao_cao_{sel_lop}_{sel_ngay.replace('/','-')}.xlsx")
                # Nút tải file Excel xịn
                st.download_button(
                    label="📥 Tải Báo Cáo Excel Tiếng Việt (XLSX)", 
                    data=output.getvalue(), 
                    file_name=f"Bao_cao_{sel_lop}_{sel_ngay.replace('/','-')}.xlsx", 
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
else:
                st.info("Hiện chưa có dữ liệu nộp bài nào.")
                st.info("Hiện chưa có dữ liệu nộp bài nào để báo cáo.")
