# Công cụ biên tập văn bản

Website biên tập văn bản với giao diện tập trung vào trình biên tập. Trang có ví dụ trước/sau, hướng dẫn ngắn, FAQ và trình biên tập hoạt động trên máy tính lẫn điện thoại.

## Chạy trên Windows (PowerShell)

```powershell
cd D:\AI_App\bien-tap-van-ban
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Mở `http://127.0.0.1:8502/`. Cổng mặc định là 8502 để không ảnh hưởng ứng dụng đang chạy ở 8501.

Không có API key, trang vẫn dùng được chế độ **Cơ bản**: chuẩn hóa khoảng trắng, dấu câu, rút gọn cụm từ và chỉnh lại một số cấu trúc câu tiếng Việt/Anh. Đây là bộ quy tắc có giới hạn, không phải mô hình ngôn ngữ. Khi không tìm thấy chỗ sửa, trang báo **Chưa có thay đổi** và không trình bày bản gốc như một kết quả mới.

## Tiện ích trong trình biên tập

- **Nhập tệp:** đọc tệp `.txt` hoặc `.md` ngay trong trình duyệt vào ô bản nháp. Giới hạn 12.000 ký tự; tệp không được tải lên máy chủ như một tệp đính kèm.
- **Sửa bản kết quả:** nhấn **Sửa**, chỉnh văn bản và nhấn **Xong**. Nút sao chép và tải TXT dùng nội dung sau khi bạn sửa.
- **Bản trong phiên:** mở lại tối đa 5 bản vừa tạo hoặc tự sửa. Lịch sử chỉ nằm trong bộ nhớ tab, không dùng `localStorage` và mất khi tải lại trang. Có nút xóa lịch sử ngay trên trang.

## Biên tập sâu bằng AI (tùy chọn)

Sao chép `.env.example` thành `.env` rồi điền `OPENAI_API_KEY` trên máy của bạn, hoặc đặt biến môi trường trước khi chạy. Không đưa key vào mã nguồn hay gửi trong chat. Có thể đổi `OPENAI_MODEL` nếu tài khoản dùng model khác. Sau khi khởi động lại máy chủ, mục **Biên tập AI** được bật trong trình biên tập với ba mức:

- **Nhẹ:** sửa lỗi và chỗ khó hiểu, giữ gần nguyên câu chữ.
- **Vừa:** viết lại câu gượng hoặc dài, giữ thứ tự ý và giọng viết.
- **Mạnh:** diễn đạt lại câu và đoạn nhiều hơn, giữ đủ ý và dữ kiện.

Chế độ này gọi OpenAI Responses API với `store=False`; văn bản được gửi tới API để xử lý. Mỗi lần biên tập AI có thể phát sinh chi phí theo tài khoản API. Máy chủ kiểm tra lại các số liệu, mã, trích dẫn và tên riêng nhiều từ nhận diện được; nếu kết quả làm mất chúng, ứng dụng sẽ báo lỗi thay vì hiển thị bản sửa. Bước kiểm tra này không thể xác minh toàn bộ ý nghĩa, nên bạn vẫn cần đọc lại bản cuối.

Website không ghi bản nháp vào file hoặc cơ sở dữ liệu trên máy chủ. Ứng dụng cũng không đưa ra điểm phát hiện AI hoặc cam kết vượt qua Turnitin/GPTZero. Người dùng cần kiểm tra lại nội dung và tuân thủ quy định nơi sử dụng.

## Kiểm thử

```powershell
python -m pytest -q
```

Giới hạn đầu vào: 12.000 ký tự. Nhấn `Ctrl+Enter` trong ô nhập để biên tập nhanh.
