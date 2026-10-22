# UniPhoto Backend (FastAPI, MySQL, EXIF & pHash)

Dự án Backend quản lý, quét và lọc trùng ảnh thông minh được xây dựng bằng **FastAPI**, **SQLAlchemy (MySQL)**, **Pillow (PIL)** và **imagehash**.

---

## 📁 Cấu trúc thư mục dự án

```text
UniPhoto/
├── app/
│   ├── __init__.py
│   ├── main.py                     # Khởi tạo FastAPI app, lifespan tạo DB, CORS, router mapping
│   ├── models.py                   # Re-export các model SQLAlchemy
│   ├── core/                       # Cấu hình cốt lõi & cơ sở dữ liệu
│   │   ├── __init__.py
│   │   ├── config.py               # Quản lý settings từ file .env qua Pydantic BaseSettings
│   │   └── database.py             # Cấu hình MySQL engine với Connection Pool & init_db()
│   ├── api/                        # Tầng xử lý API Routing
│   │   ├── __init__.py
│   │   ├── deps.py                 # Dependency get_db cung cấp Session cho từng request
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── api.py              # Gom toàn bộ routers của v1
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── hello.py        # Endpoint Hello World
│   │           └── scan.py         # Endpoint POST /api/scan quét thư mục & lọc trùng ảnh
│   ├── schemas/                    # Pydantic schemas (Request / Response Data Validation)
│   │   ├── __init__.py
│   │   ├── hello.py                # Schema HelloResponse
│   │   └── scan.py                 # Schema ScanRequest, ScanResponse, PhotoItemSummary
│   ├── models/                     # SQLAlchemy Models
│   │   ├── __init__.py
│   │   └── models.py               # Định nghĩa bảng Photo và Cluster (tối ưu VARCHAR cho MySQL)
│   ├── crud/                       # Tầng thao tác cơ sở dữ liệu (CRUD)
│   │   └── __init__.py
│   └── services/                   # Business logic (Xử lý quét thư mục, đọc EXIF, tính pHash)
│       ├── __init__.py
│       └── scanner.py              # Hàm scan_directory()
├── .env.example                    # Mẫu biến môi trường
├── .env                            # Biến môi trường cục bộ (cấu hình MySQL)
├── .gitignore                      # File cấu hình bỏ qua git chuẩn Python
├── requirements.txt                # Danh sách thư viện phụ thuộc (FastAPI, PyMySQL, Cryptography,...)
├── run.py                          # Script khởi chạy nhanh server
└── README.md                       # Tài liệu hướng dẫn sử dụng dự án
```

---

## 🗄️ Cấu trúc Cơ sở dữ liệu (MySQL)

### Bảng `photos`
| Trường | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `id` | INT AUTO_INCREMENT (PK) | Định danh tự tăng |
| `file_path` | VARCHAR(500) (Unique, Indexed) | Đường dẫn tuyệt đối của file ảnh |
| `file_size` | INT | Dung lượng file tính bằng bytes |
| `timestamp` | DATETIME (Nullable) | Thời gian chụp gốc trích xuất từ thẻ EXIF `DateTimeOriginal` |
| `phash` | VARCHAR(64) (Indexed) | Mã băm cảm nhận (perceptual hash 64-bit) |
| `quality_score`| FLOAT (Nullable) | Điểm đánh giá chất lượng ảnh |
| `cluster_id` | INT (FK `clusters.id`) | Nhóm ảnh tương tự |
| `status` | VARCHAR(50) (Indexed) | Trạng thái: `"keep"`, `"exact_duplicate"`, v.v. |

### Bảng `clusters`
| Trường | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `id` | INT AUTO_INCREMENT (PK) | Định danh nhóm |
| `best_photo_id` | INT (FK `photos.id`)| ID của bức ảnh đẹp/chất lượng nhất trong cụm |

---

## 🚀 Hướng dẫn khởi chạy với MySQL

### 1. Khởi động MySQL Server

Tạo database `uni_photo` trong MySQL:
```sql
CREATE DATABASE IF NOT EXISTS uni_photo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
Sau đó điều chỉnh thông tin tài khoản `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT` trong file `.env`.

### 2. Kích hoạt môi trường ảo & cài đặt thư viện
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Khởi động Backend Server
```bash
python run.py
```
Máy chủ chạy tại: `http://127.0.0.1:8000`

---

## 📡 Chi tiết API Quét ảnh & Lọc trùng (`POST /api/scan`)

Endpoint hỗ trợ quét ảnh định dạng `.jpg`, `.jpeg`, `.png`, đọc EXIF `DateTimeOriginal` và tính `pHash` để xác định trùng lặp 100%.

- **URL:** `POST http://127.0.0.1:8000/api/scan` (hoặc `POST http://127.0.0.1:8000/api/v1/scan`)
- **Request Body (JSON):**
  ```json
  {
    "folder_path": "/Users/hung/Pictures/DuLich"
  }
  ```
- **Response (JSON):**
  ```json
  {
    "message": "Quét thư mục và phân loại hoàn tất.",
    "folder_path": "/Users/hung/Pictures/DuLich",
    "total_found": 150,
    "new_added": 120,
    "exact_duplicates": 30,
    "already_indexed": 0,
    "errors_count": 0,
    "duration_seconds": 1.452,
    "items": [
      {
        "id": 1,
        "file_path": "/Users/hung/Pictures/DuLich/IMG_0001.JPG",
        "file_size": 2489120,
        "timestamp": "2024-05-10T14:32:10",
        "phash": "a3c5f091b2c4e5f6",
        "status": "keep"
      },
      {
        "id": 2,
        "file_path": "/Users/hung/Pictures/DuLich/IMG_0001_copy.JPG",
        "file_size": 2489120,
        "timestamp": "2024-05-10T14:32:10",
        "phash": "a3c5f091b2c4e5f6",
        "status": "exact_duplicate"
      }
    ]
  }
  ```

---

## 🔍 Swagger UI & Tài liệu tương tác

- **Swagger UI:** [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs)
- **ReDoc UI:** [http://127.0.0.1:8000/api/v1/redoc](http://127.0.0.1:8000/api/v1/redoc)
