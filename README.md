# old-book-ocr

Nền tảng OCR cho sách tiếng Việt cũ, phần thực nghiệm của luận văn thạc sĩ:

- **Model**: PaddleOCR-VL-1.6 fine-tune bằng LoRA trên corpus VieBookRead.
- **Backend**: nhận tài liệu, chạy OCR theo trang, lưu bản hiệu đính, xuất file.
- **Frontend**: giao diện web để hiệu đính và xuất file.
- **MLOps**: registry model, đánh giá, tái lập, giám sát. Mỗi con số trong luận văn đều truy được nguồn.

Đây là repo "ô" (umbrella): mỗi phần là một git submodule riêng. Repo ô chỉ giữ những thứ dùng chung: `stack.sh`,
tài liệu, sơ đồ, skill đánh giá và kết quả audit.

Sơ đồ tổng quan: mở [`diagrams/index.html`](diagrams/index.html) (xem mục [Sơ đồ](#sơ-đồ)).

---

## Mục lục

1. [Bắt đầu nhanh](#bắt-đầu-nhanh)
2. [Chế độ hiện tại: chỉ hiệu đính và xuất file](#chế-độ-hiện-tại-chỉ-hiệu-đính-và-xuất-file)
3. [Bật / tắt hệ thống](#bật--tắt-hệ-thống)
4. [Địa chỉ khi đang chạy](#địa-chỉ-khi-đang-chạy)
5. [Cấu trúc repo](#cấu-trúc-repo)
6. [Model hiện tại](#model-hiện-tại)
7. [Sơ đồ](#sơ-đồ)
8. [Tài liệu khác](#tài-liệu-khác)
9. [Làm việc với submodule](#làm-việc-với-submodule)
10. [Khi có sự cố](#khi-có-sự-cố)

---

## Bắt đầu nhanh

Điều kiện: **Docker Desktop đang chạy** bên Windows và đã bật WSL integration cho distro này.

```bash
./stack.sh up
```

Lệnh này chạy từ thư mục gốc của repo, mất khoảng 25 giây. Khi xong, mở http://localhost:8080 trên Windows.

```bash
./stack.sh status
```

```bash
./stack.sh down
```

Máy mới, chưa có dữ liệu: xem [`HUONG_DAN_KHOI_PHUC.md`](HUONG_DAN_KHOI_PHUC.md) để khôi phục database, ảnh trang,
adapter và `backend/.env` từ bản sao lưu. Sau đó làm theo
[`HUONG_DAN_GIAI_NEN_DU_LIEU_TRAIN.md`](HUONG_DAN_GIAI_NEN_DU_LIEU_TRAIN.md) nếu cần dữ liệu train.

---

## Chế độ hiện tại: chỉ hiệu đính và xuất file

Hệ thống đang chạy với `REVIEW_ONLY=true` trong `backend/.env`. Người dùng đọc 693 tài liệu đã nhận dạng, hiệu đính
và xuất file. Không nạp tài liệu mới, không chạy OCR, và bản hiệu đính **không** quay lại huấn luyện.

**Cơ chế.** Chỉ có một cờ, nằm ở backend. API công bố cờ này qua `GET /capabilities`:

```json
{ "review_only": true, "upload": false, "ocr": false, "training_export": false }
```

Frontend đọc câu trả lời này một lần lúc khởi động và không giữ bản sao cờ nào. Nếu không gọi được API, frontend coi
như đang ở chế độ review-only.

| | `REVIEW_ONLY=true` (hiện tại) | `REVIEW_ONLY=false` |
|---|---|---|
| Đọc, hiệu đính, đánh dấu trang | có | có |
| Xuất txt / md / json / pdf / docx / epub | có | có |
| Màn Upload (`POST /documents`) | ẩn, API trả 403 | có |
| Màn Hàng đợi, nút OCR, nút Retry (`POST /jobs`) | ẩn, API trả 403 | có |
| Cột "Huấn luyện" (`PATCH /documents/{id}`) | ẩn, API trả 403 | có |
| `GET /exports/training-candidates` | 403 | có |
| Trang mở đầu (`/`) | Review | Upload |

**Mở lại toàn bộ chức năng:** đặt `REVIEW_ONLY=false` trong `backend/.env`, rồi tạo lại container `api` bằng
`cd backend && docker compose up -d api`. Lệnh `docker compose restart` không đọc lại `.env`, nên không có tác dụng.
Tải lại trang web để frontend hỏi lại `/capabilities`. Không có dữ liệu nào thay đổi khi bật hay tắt cờ. Chi tiết:
`backend/README.md`, mục "Review-only deployments".

**Tên sách.** Mỗi tài liệu có thêm trường `title` (migration `0017`, tối đa 300 ký tự, không bắt buộc). Trường này
được nhập ở màn Upload. Tên sách hiện trong các danh sách tài liệu và làm tiêu đề file docx/epub. Tài liệu chưa có
tên thì hiện tên file bỏ đuôi (`9.pdf` → `9`).

**Hạn chế đã biết:**
- `DELETE /documents/{id}` **không** bị chặn khi bật `REVIEW_ONLY`, nên vẫn xoá được tài liệu qua API.
- Màn Upload không còn ô cho phép dùng bản hiệu đính để huấn luyện: upload luôn gửi `allow_training=false`, kể cả
  khi `REVIEW_ONLY=false`.
- 693 tài liệu đã có đều chưa có tên sách. Khi màn Upload bị ẩn thì chưa có chỗ nào trên giao diện để đặt tên.

---

## Bật / tắt hệ thống

Mặc định hệ thống được **tắt** để tiết kiệm tài nguyên.

| Lệnh | Tác dụng |
|---|---|
| `./stack.sh up` | Bật tất cả, phần nào đang chạy thì bỏ qua |
| `./stack.sh up --no-soup` | Như trên nhưng không bật model soup (:8097) |
| `./stack.sh status` | Trạng thái từng phần, bộ nhớ GPU, cảnh báo Prometheus đang kích hoạt |
| `./stack.sh down` | Tắt tất cả, có tạo backup snapshot trước |
| `./stack.sh down --no-backup` | Tắt tất cả, bỏ qua bước backup |

`up` bật theo thứ tự:

1. **Container** (`backend/docker-compose.yml`, project `ocr`): postgres, valkey, migrate, api, worker, prometheus,
   grafana. Chờ đến khi tất cả healthy.
2. **GPU server** chạy trên host (`backend/recognizer_server/manage.py`): một layout server và 3 recognizer, bật song
   song.
3. **Supervisor** (`manage.py supervise`): tự khởi động lại GPU server bị chết, bị treo hoặc lỗi GPU (CUDA 999).
   Log ở `backend/data/logs/supervisor.log`.
4. **Frontend dev server** (`npm run dev` trong `frontend/`, cổng 8080 hoặc `PORT` trong `frontend/.env.local`).

`down` tắt theo thứ tự ngược lại: supervisor → frontend → **backup snapshot** (`backend/tools/backup.py`, chỉ chép ảnh
mới) → container (worker làm nốt trang đang xử lý) → GPU server.

Dữ liệu được **giữ nguyên** khi tắt: Postgres, ValKey, Prometheus, Grafana và ảnh trang trong `backend/data/storage`.
Muốn giải phóng thêm RAM thì sau `./stack.sh down`, thoát hẳn Docker Desktop.

Cảnh báo của Prometheus chỉ hiện trong `status`. Hệ thống chưa có Alertmanager nên không gửi cảnh báo đi đâu.

---

## Địa chỉ khi đang chạy

| Dịch vụ | Địa chỉ | Ghi chú |
|---|---|---|
| Giao diện web | http://localhost:8080 | Gọi API qua `/api` (proxy sang :8000). Từ Windows phải dùng **localhost**: WSL không chuyển tiếp `127.0.0.1:8080` |
| API (FastAPI) | http://127.0.0.1:8000 | `/docs` là trang OpenAPI. Token: `API_TOKEN` trong `backend/.env` |
| Grafana | http://127.0.0.1:3000 | User `admin`, mật khẩu trong `backend/.env`. Dashboard MLOps nằm trong `mlops/grafana/` |
| Prometheus | http://127.0.0.1:9090 | |
| Postgres / ValKey | 127.0.0.1:5432 / 6379 | Thông tin đăng nhập trong `backend/.env` |
| Layout server (PP-DocLayoutV3) | :8091 | Bắt buộc: mọi trang đều đi qua đây |
| Recognizer `lr2e4-s3000` (model chính, active) | :8090, :8092 | Hai bản cùng một model để tăng thông lượng |
| Recognizer `soup-r1r2` (inactive) | :8097 | Chỉ dùng khi chọn soup lúc upload (sách mờ, xám) |
| MLflow | http://127.0.0.1:5000 | Không nằm trong stack. Bật riêng: `cd mlops && make mlflow-ui` |

Danh sách GPU server trong `stack.sh` (`GPU_SERVERS`) phải khớp với `RECOGNIZER_URL`, `RECOGNIZER_ROUTES` và
`LAYOUT_URL` trong `backend/.env`. Sửa bên này thì phải sửa cả bên kia.

---

## Cấu trúc repo

### Submodule

| Thư mục | Nội dung | Remote (github.com/haccoco99999/…) |
|---|---|---|
| `backend/` | API, worker, migrations, GPU server (`recognizer_server/`), công cụ backup, báo cáo đánh giá (`reports/eval/`) | `master-2-backend` |
| `frontend/` | Giao diện React (Umi + antd): hiệu đính, xuất file, upload và hàng đợi khi ở full mode | `master-2-frontend` |
| `training/` | Dựng dữ liệu, train LoRA, đánh giá, các run, kết quả khoá (`finals/`), phân tích (`analysis/`, `work/analysis/`) | `master-training-2` |
| `mlops/` | Registry, promote / activate model, MLflow, gói tái lập, dashboard Grafana | `master-2-mlops` |
| `eda/` | Phân tích corpus VieBookRead và các quyết định dữ liệu (notebook và báo cáo bằng tiếng Việt) | `master-2-eda` |

`backend`, `frontend`, `mlops` và `eda` có README riêng về cách chạy test, biến môi trường và quy trình làm việc.
`training` chưa có README ở thư mục gốc. Tài liệu của nó nằm rải rác: `splits/README.md`, `work/study/README.md`,
`analysis/a2_lm_only/README.md` và docstring đầu mỗi script.

`eda/` chiếm khoảng 4,5 GB. Chỉ `training/prepare_data.py` cần đến nó, ở bước dựng lại bộ dữ liệu từ corpus gốc.
Nếu thiếu, script sẽ dừng và in lệnh khôi phục. Các phần còn lại (dữ liệu đã dựng, train, đánh giá, backend,
frontend) đều không cần `eda/`.

### Trong repo ô

| Đường dẫn | Nội dung |
|---|---|
| `stack.sh` | Bật / tắt toàn bộ hệ thống |
| `diagrams/` | 15 sơ đồ hệ thống, dữ liệu và huấn luyện (xem [Sơ đồ](#sơ-đồ)) |
| `skills/viet-ocr-eval/` | Giao thức đánh giá đã khoá: CER, WER, DER, TER, bootstrap. Các phân tích mới dùng protocol 1.3 |
| `docs/specs/` | Đề bài và prompt gốc của từng phần, `decision.md` |
| `docs/thesis/`, `docs/SO_LIEU_2026-10-01.md` | Ghi chú chương kết quả và bảng số liệu ngày 01/10 |
| `audit/` | Báo cáo audit ngày 25/09 (`AUDIT.md`) và bằng chứng |
| `HUONG_DAN_KHOI_PHUC.md` | Khôi phục dự án từ bản sao lưu 10/10/2026 |
| `HUONG_DAN_GIAI_NEN_DU_LIEU_TRAIN.md` | Giải nén dữ liệu train và gói bổ sung |

### Chỉ có trên máy, không đưa vào git

| Thư mục | Nội dung |
|---|---|
| `dataset/VieBookRead/` | Corpus gốc |
| `models/PaddleOCR-VL-1.6/` | Model gốc |
| `models/adapters/` | Adapter soup (`soup-r1r2`) và các adapter trung bình của vòng phản hồi |
| `third_party/ERNIE/` | ERNIE (đã pin phiên bản) |
| `.venv-train/` | Môi trường train và recognizer server. **Đóng băng**, không cài thêm gì |
| `.venv-layout/` | Môi trường layout server (paddlex). Không cài vào `.venv-train` |
| `.run/` | PID và log của frontend dev server do `stack.sh` bật |
| `backend/.env` | Cấu hình và secret đang dùng |

Log GPU server: `backend/data/logs/<kind>-<port>.log`. Log frontend: `.run/frontend.log`.

---

## Model hiện tại

- **Active**: `paddleocr-vl-1.6-vbr-lr2e4-s3000` (model version 3). Mọi số liệu của luận văn đều khoá theo model này.
- **Soup** `paddleocr-vl-1.6-vbr-soup-r1r2` (version 16, inactive). Model này hoà với model chính ở round 2 (147/145)
  nên không thay thế model chính. Nó được giữ làm lựa chọn theo từng tài liệu cho sách mờ, xám. Chi tiết:
  `backend/reports/eval/soup/REPORT.md` và `backend/reports/eval/round2/RESULT.md`.
- Đổi model active là thao tác làm bằng tay (`mlops/activate.py`), không bao giờ tự động.

---

## Sơ đồ

Mở [`diagrams/index.html`](diagrams/index.html) trong trình duyệt để xem tất cả. Mỗi sơ đồ có ba file: `.json` là
nguồn, `.svg` là ảnh tĩnh, `.html` là bản tương tác.

| # | Sơ đồ | # | Sơ đồ |
|---|---|---|---|
| 01 | Tổng quan hệ thống | 09 | Trạng thái của một OCR job |
| 02 | Vòng đời một OCR job | 10 | CER theo loại vùng |
| 03 | Xử lý một trang | 11 | Từ VieBookRead tới model cuối |
| 04 | Hiệu đính và xuất file | 12 | Từ một trang scan tới các cặp crop + nhãn |
| 05 | Cấu trúc frontend | 13 | 231.541 vùng đi về đâu |
| 06 | Vòng đời model | 14 | Chia tập theo sách và tập gold |
| 07 | Schema: lõi OCR | 15 | Từ dữ liệu train tới model được chọn |
| 08 | Schema: hiệu đính và nghiên cứu | | |

Sơ đồ 01–09 mô tả hệ thống, 10–15 mô tả dữ liệu và huấn luyện.

---

## Tài liệu khác

| Muốn biết | Xem |
|---|---|
| Chi tiết API, biến môi trường, chế độ review-only | `backend/README.md` |
| Chạy frontend, test, mock mode | `frontend/README.md` |
| Chia tập train / dev / test | `training/splits/README.md` |
| Registry, promote, MLflow, tái lập | `mlops/README.md` |
| Phân tích corpus | `eda/README.md` |
| Thí nghiệm A2 (LoRA chỉ trên LM, chỉ dùng dev) | `training/analysis/a2_lm_only/README.md` |
| Độ nhạy của kết quả test khi bỏ sách 097 | `training/work/analysis/sensitivity_097/SUMMARY.md` |

---

## Làm việc với submodule

Clone lần đầu, kèm cả submodule:

```bash
git clone --recurse-submodules git@github.com:haccoco99999/old-book-ocr.git
```

Sau khi pull repo ô, cập nhật submodule theo con trỏ mới:

```bash
git submodule update --init
```

Khi sửa code: **commit trong submodule trước**, rồi mới ghi lại con trỏ ở repo ô.

```bash
cd backend && git commit ... && git push && cd ..
git add backend && git commit -m "Bump backend"
```

`git submodule update` để submodule ở trạng thái detached HEAD. Trước khi commit trong submodule, hãy chuyển sang một
nhánh (`git checkout main` hoặc nhánh đang làm), nếu không commit sẽ không nằm trên nhánh nào.

---

## Khi có sự cố

- **`./stack.sh status` báo `GPU ERROR`** (thường sau lỗi GPU của WSL, CUDA error 999): context CUDA đã hỏng và
  không tự hồi phục. Chạy `./stack.sh down && ./stack.sh up`. Nếu chỉ một server lỗi, dừng riêng server đó bằng
  `python3 backend/recognizer_server/manage.py stop --port <N>` rồi bật lại.
- **Container không lên**: xem log bằng `cd backend && docker compose logs <service>`. Luôn bật bằng `up -d` (hoặc
  `./stack.sh up`), không dùng `docker compose start`, vì hai lý do. Một là container cũ vẫn giữ mật khẩu cũ sau khi
  đổi secret. Hai là Docker Desktop làm hỏng bind-mount một file (`prometheus.yml`) của container đã stop.
- **Không dừng tiến trình bằng `pkill -f <pattern>`**: pattern sẽ khớp luôn cả shell đang chạy lệnh. Dùng `stack.sh`
  hoặc `manage.py stop`.
- **Màn Upload không có model để chọn** (chỉ ở full mode): server tương ứng chưa chạy hoặc đang lỗi, xem
  `./stack.sh status`. Worker cập nhật danh sách model 30 giây một lần.
- **Không thấy màn Upload hay Hàng đợi**: đây là hành vi đúng khi `REVIEW_ONLY=true`. Có thể kiểm tra bằng
  `curl -s http://127.0.0.1:8000/capabilities`.
- **WSL báo không tìm thấy `docker`**: bật WSL integration cho distro này trong Docker Desktop (Settings → Resources →
  WSL integration).
