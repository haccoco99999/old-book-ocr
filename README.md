# old-book-ocr

Nền tảng OCR cho sách tiếng Việt cũ: fine-tune PaddleOCR-VL-1.6 (LoRA) trên VieBookRead, backend xử lý tài liệu,
frontend để upload / soát lỗi / export, và MLOps để mọi con số trong luận văn truy được nguồn.
Repo này là repo "ô" (umbrella): mỗi phần là một submodule riêng.

## Bật / tắt toàn bộ hệ thống

Mặc định hệ thống được **tắt** để tiết kiệm tài nguyên. Trước khi làm việc với backend hoặc frontend:

```bash
cd /home/huy/master
./stack.sh up            # bật tất cả (~25 giây)
./stack.sh up --no-soup  # như trên, không bật model soup (:8097)
./stack.sh status        # trạng thái từng phần + bộ nhớ GPU
./stack.sh down          # tắt tất cả
```

Điều kiện: **Docker Desktop phải đang chạy** bên Windows (nếu không, `up` sẽ báo).

`up` bật theo thứ tự, phần nào đang chạy thì bỏ qua:

1. Container (`backend/docker-compose.yml`): postgres, valkey, migrate, api, worker, prometheus, grafana. Chờ đến khi healthy.
2. GPU server trên host (`backend/recognizer_server/manage.py`): layout + 3 recognizer, bật song song.
3. Supervisor (`manage.py supervise`): tự khởi động lại GPU server chết, treo hoặc lỗi GPU (CUDA 999). Log ở
   `backend/data/logs/supervisor.log`.
4. Frontend dev server (`npm run dev` trong `frontend/`).

`down` tắt theo thứ tự: supervisor → frontend → **backup snapshot** (`backend/tools/backup.py`, chỉ chép ảnh mới; bỏ qua
bằng `--no-backup`) → container (worker làm nốt trang đang xử lý) → GPU server. `status` hiển thị thêm các cảnh báo đang
kích hoạt của Prometheus. Không có cảnh báo nào được gửi đi đâu (chưa có Alertmanager).
Dữ liệu (Postgres, ValKey, Prometheus, Grafana, ảnh trang trong `backend/data/storage`) **được giữ nguyên**.

Muốn giải phóng thêm RAM: sau `./stack.sh down`, thoát hẳn Docker Desktop.

## Địa chỉ khi đang chạy

| Dịch vụ | Địa chỉ | Ghi chú |
|---|---|---|
| Giao diện web (frontend) | http://localhost:8080 | gọi API qua `/api` (proxy sang :8000). Từ Windows dùng **localhost**: `127.0.0.1:8080` không được WSL chuyển tiếp |
| API (FastAPI) | http://127.0.0.1:8000 | `/docs` = OpenAPI; token trong `backend/.env` (`API_TOKEN`) |
| Grafana | http://127.0.0.1:3000 | user `admin`, mật khẩu trong `backend/.env`; dashboard MLOps trong thư mục MLOps |
| Prometheus | http://127.0.0.1:9090 | |
| Postgres / ValKey | 127.0.0.1:5432 / 6379 | thông tin đăng nhập trong `backend/.env` |
| Layout server (PP-DocLayoutV3) | :8091 | bắt buộc: mọi trang đều qua đây |
| Recognizer `lr2e4-s3000` (model chính, active) | :8090, :8092 | 2 bản cùng model để tăng thông lượng |
| Recognizer `soup-r1r2` (inactive) | :8097 | chỉ dùng khi chọn soup lúc upload (sách mờ xám) |
| MLflow (không nằm trong stack) | http://127.0.0.1:5000 | bật riêng: `cd mlops && make mlflow-ui` |

Danh sách GPU server trong `stack.sh` phải khớp với `RECOGNIZER_URL`, `RECOGNIZER_ROUTES`, `LAYOUT_URL` trong
`backend/.env`. Đổi bên này thì sửa bên kia.

## Cấu trúc

| Thư mục | Là gì | Remote |
|---|---|---|
| `backend/` | API, worker, migrations, GPU server (`recognizer_server/`), báo cáo đánh giá (`reports/eval/`) | master-2-backend |
| `frontend/` | Giao diện React (Umi/antd): upload, soát lỗi, export | master-2-frontend |
| `training/` | Train LoRA, infer, các run và kết quả khoá (`finals/`) | master-training-2 |
| `mlops/` | Registry, promote/activate, MLflow, gói tái lập, dashboard Grafana | master-2-mlops |
| `eda/` | Phân tích corpus VieBookRead và các quyết định dữ liệu. **Không checkout trên máy này từ 06/10/2026** (xem dưới bảng) | master-2-eda |
| `skills/` | Skill `viet-ocr-eval` (giao thức đo CER/DER/TER, bản 1.2 và 1.1) | (repo này) |
| `docs/specs/` | Đề bài / prompt gốc của từng phần, `decision.md` | (repo này) |
| `audit/` | Báo cáo audit 25/09 và bằng chứng | (repo này) |
| `stack.sh` | Bật / tắt toàn bộ | (repo này) |

**`eda/` đang để trống (06/10/2026, để giải phóng 5,2 GB).** Toàn bộ nội dung đã có trên GitHub (`master-2-eda`,
commit `61fdbf7c`, đúng commit repo này ghi nhận).
- Chỉ `training/prepare_data.py` cần nó: bước dựng lại bộ dữ liệu huấn luyện từ corpus gốc đọc JSON của Azure, thống kê
  corpus và tokenizer từ `eda/reports/`. Thiếu các file này thì script dừng ngay và in lệnh khôi phục.
- Bộ dữ liệu đã dựng (`training/data/`), huấn luyện, đánh giá, vòng phản hồi, backend và frontend không cần `eda/`.
- Khôi phục (tải lại khoảng 4,7 GB): `git submodule update --init eda`

Chỉ có trên máy, không vào git:

| Thư mục | Là gì |
|---|---|
| `dataset/VieBookRead/` | Corpus |
| `models/PaddleOCR-VL-1.6/` | Model gốc |
| `models/adapters/soup-r1r2/` | Adapter soup (R1+R2) |
| `third_party/` | ERNIE (đã pin) và libgomp cục bộ |
| `.venv-train/` | Môi trường train + recognizer server (**đóng băng**, không cài thêm gì) |
| `.venv-layout/` | Môi trường layout server (paddlex); không được cài vào `.venv-train` |
| `.venv/` | Môi trường chung (Jupyter, phân tích) |
| `.run/` | PID và log của frontend dev server do `stack.sh` bật |

Log GPU server: `backend/data/logs/<kind>-<port>.log`. Log frontend: `.run/frontend.log`.

## Làm việc với submodule

```bash
git clone --recurse-submodules https://github.com/haccoco99999/old-book-ocr.git   # clone mới
git submodule update --init                     # sau khi pull repo ô

# commit trong submodule trước, rồi ghi lại con trỏ ở repo ô
cd backend && git commit ... && git push && cd ..
git add backend && git commit -m "Bump backend"
```

Mỗi submodule có README riêng cho chi tiết (test, biến môi trường, quy trình).

## Khi có sự cố

- **GPU server báo `GPU ERROR`** trong `./stack.sh status` (sau lỗi GPU của WSL, CUDA error 999): context CUDA hỏng
  không tự hồi phục. `./stack.sh down && ./stack.sh up`, hoặc chỉ server đó:
  `python3 backend/recognizer_server/manage.py stop --port <N>` rồi bật lại.
- **Container không lên**: xem `cd backend && docker compose logs <service>`. Luôn dùng `up -d` (hoặc `./stack.sh up`),
  không dùng `docker compose start`: container cũ giữ mật khẩu cũ sau khi đổi secret, và Docker Desktop làm hỏng
  bind-mount một file (`prometheus.yml`) của container đã stop.
- **Không dừng tiến trình bằng `pkill -f <pattern>`**: pattern khớp luôn cả shell đang chạy lệnh. Dùng `stack.sh` hoặc
  `manage.py stop`.
- **Worker không thấy model** (màn Upload không có model để chọn): server tương ứng chưa chạy hoặc lỗi; xem
  `./stack.sh status`. Worker báo lại danh sách model mỗi 30 giây.

## Model hiện tại

- **Active**: `paddleocr-vl-1.6-vbr-lr2e4-s3000` (model version 3). Số liệu luận văn khoá theo model này.
- **Soup** `paddleocr-vl-1.6-vbr-soup-r1r2` (version 16, inactive): hoà model chính ở round 2 (147/145) nên không thay;
  giữ làm lựa chọn theo từng tài liệu cho sách mờ xám. Chi tiết: `backend/reports/eval/soup/REPORT.md`,
  `backend/reports/eval/round2/RESULT.md`.
- Đổi model active là thao tác tay (`mlops/activate.py`), không bao giờ tự động.
