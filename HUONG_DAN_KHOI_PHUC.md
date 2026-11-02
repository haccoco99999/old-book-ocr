# Hướng dẫn khôi phục — old-book-ocr (bản sao lưu 10/10/2026)

File này đi kèm `old-book-ocr-backup-20261010.tar.gz`. Nó dành cho người dùng mới hoặc một phiên Claude Code mới
cần dựng lại dự án trên máy khác.

Gói này **chỉ chứa những thứ không có trên GitHub và không tái tạo được**. Mã nguồn lấy từ GitHub, môi trường và
dữ liệu train dựng lại theo mục 5.

> **Cảnh báo bảo mật.** Gói có `backend/.env` chứa secret thật (API token, mật khẩu Postgres, mật khẩu Grafana).
> Không chia sẻ gói ở nơi công khai. Nếu gói đã đến tay người không nên có, hãy đổi cả ba secret đó.

## 1. Gói chứa gì

Mọi đường dẫn trong gói tính từ thư mục gốc của repo ô (`master/`), trừ `claude-memory/` và file hướng dẫn này.

| # | Đường dẫn trong gói | Là gì |
|---|---|---|
| 1 | `backend/data/backups/snapshots/20261010T104954Z/` | Snapshot backend: `db.dump` (Postgres, schema 0016, 42.284 dòng), `storage/` (13.466 ảnh trang, 17,7 GiB), `manifest.json` |
| 2 | `backend/reports/eval/` | Kết quả đánh giá của backend |
| 3 | `training/data-feedback/`, `training/data-feedback-train/`, `training/data-fix/` | Dữ liệu vòng phản hồi và nhãn đã sửa |
| 4 | `training/runs/*/best/` | Adapter LoRA tốt nhất của từng run (chỉ `exp_lr2e4` có trong git) |
| 5 | `training/work/analysis/`, `training/work/study/`, `training/work/watchdog/` | Kết quả phân tích, bộ user study, log watchdog |
| 6 | `training/finals/`, `training/baselines/` | Dự đoán trên tập test và baseline. **Không chạy lại**: chạy lại là truy cập tập test thêm một lần |
| 7 | `models/adapters/` | Adapter soup (`soup-r1r2`, model id 16) và các adapter trung bình (gồm model id 25 `fb-20261008-avg`) |
| 8 | `mlops/mlruns.db`, `mlops/mlartifacts/`, `mlops/work/` | Lịch sử MLflow, hồ sơ promotion và eval (không gồm `mlops/work/repro`, dựng lại được) |
| 9 | `backend/data/backups/usability/` | Sự kiện usability của tài liệu 701 |
| 10 | `backend/.env` | Cấu hình và secret đang dùng |
| 11 | `claude-memory/`, `.claude/skills/` | Bộ nhớ của Claude Code cho dự án và skill `viet-ocr-eval` bản local |

Gói được tạo khi các repo ở những commit sau (đều đã có trên GitHub):

| Repo | Commit |
|---|---|
| umbrella `old-book-ocr` | `5cb8c41` |
| `backend` | `7b0328d` |
| `frontend` | `6834fbc` |
| `mlops` | `3d1b996` |
| `training` | `3f545f0` |

## 2. Kiểm tra gói

```bash
sha256sum -c old-book-ocr-backup-20261010.tar.gz.sha256
tar -tzf old-book-ocr-backup-20261010.tar.gz | head
```

Cần khoảng 25 GB trống cho file nén và thêm khoảng 25 GB sau khi giải nén.

## 3. Giải nén

Clone mã nguồn trước, rồi giải nén **đè lên thư mục gốc của repo**. Một số file trong gói trùng với file git đang
theo dõi (ví dụ adapter `exp_lr2e4`); nội dung giống hệt nếu repo ở đúng commit trong bảng trên.

```bash
git clone --recurse-submodules https://github.com/haccoco99999/old-book-ocr.git master
cd master
tar -xzf /duong/dan/old-book-ocr-backup-20261010.tar.gz
git status                                   # không được có file nào bị sửa trong các submodule
```

Submodule `eda` (khoảng 4,7 GB) chỉ cần khi dựng lại dữ liệu train; có thể bỏ qua bằng cách clone không kèm nó rồi
`git submodule update --init backend frontend mlops training`.

Sau khi giải nén, ở gốc repo sẽ có thêm `HUONG_DAN_KHOI_PHUC.md` và `claude-memory/`; cả hai không thuộc repo.

## 4. Khôi phục backend (database và ảnh trang)

Cần Docker đang chạy. Làm trong `backend/`, khi stack đang tắt:

```bash
cd backend
SNAP=data/backups/snapshots/20261010T104954Z
docker compose up -d --wait postgres
set -a; . ./.env; set +a
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $POSTGRES_DB" -c "CREATE DATABASE $POSTGRES_DB"
docker compose exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error < "$SNAP/db.dump"
rsync -a --delete "$SNAP/storage/" data/storage/
python3 tools/backup.py drill                # diễn tập: so số dòng, revision và ảnh với manifest
```

Lưu ý:

- Postgres tạo volume mới với mật khẩu lấy từ `backend/.env` ở lần chạy đầu, nên phải giải nén `.env` trước khi
  bật container.
- Sau bước này `data/storage/` là bản thứ hai của ảnh trang (thêm 17,7 GiB). Muốn tiết kiệm đĩa, dùng
  `rsync -a --delete --link-dest="$PWD/$SNAP/storage/" "$SNAP/storage/" data/storage/` để hai bản dùng chung file.
- Số liệu đúng sau khi khôi phục: 693 tài liệu, 13.465 trang, 12.487 bản sửa trang, 5 model, model đang active là
  id 3 `paddleocr-vl-1.6-vbr-lr2e4-s3000`. Bảng đầy đủ nằm trong `$SNAP/manifest.json`.
- Quy trình gốc: `backend/README.md`, mục "Backup and restore".

## 5. Những thứ không có trong gói và cách dựng lại

| Thứ | Cách dựng lại |
|---|---|
| `models/PaddleOCR-VL-1.6/` (model gốc, 1,8 GB) | Tải lại từ Hugging Face vào đúng đường dẫn này |
| `.venv-train/` (train + recognizer server) | Python 3.12, cài theo `training/requirements-train.lock.txt`; ghi chú cài đặt ở đầu `training/requirements-train.txt`. ERNIE pin ở commit `30ad986`, PaddleFormers `35a9df2`, paddlefleet `0.0.1.dev20251210` |
| `.venv-layout/` (layout server, paddlex) | Môi trường riêng; không cài chung vào `.venv-train` |
| `third_party/` | ERNIE ở commit đã pin và libgomp cục bộ |
| `frontend/node_modules/` | `npm ci` trong `frontend/` |
| `mlops/.venv/`, `backend/.venv/`, `.venv/` | Cài lại theo file requirements/pyproject của từng repo |
| `training/data/`, `training/data-lines/`, `training/data-mixed/` (dữ liệu train đã dựng, khoảng 60 GB) | `git submodule update --init eda`, rồi chạy `training/prepare_data.py`. Chưa xác minh bản dựng lại khớp từng byte với bản cũ |
| `training/runs/*/checkpoints/` | Không khôi phục được; chỉ cần nếu muốn resume một run cũ |
| `mlops/work/repro/` | Dựng lại bằng `mlops/repro_package.py` (xem `mlops/docs/REPRODUCE.md`) |
| Lịch sử metric Prometheus, trạng thái Grafana | Mất; dashboard được provision lại từ git |
| Đăng nhập `gh`, git, Azure, AWS | Đăng nhập lại trên máy mới |

Bật hệ thống sau khi dựng xong: `./stack.sh up` ở gốc repo (xem `README.md`).

## 6. Dành cho Claude Code

`claude-memory/` là bộ nhớ dự án của Claude Code trên máy cũ. Thư mục đích phụ thuộc đường dẫn repo trên máy mới:
lấy đường dẫn tuyệt đối của gốc repo, thay mọi `/` bằng `-`.

```bash
# ví dụ repo ở /home/<user>/master
mkdir -p ~/.claude/projects/-home-<user>-master
mv claude-memory ~/.claude/projects/-home-<user>-master/memory
```

Khi đọc bộ nhớ, lưu ý:

- `MEMORY.md` là mục lục; mỗi file còn lại là một ghi chú.
- Ghi chú phản ánh trạng thái lúc viết. Đường dẫn `/home/huy/master`, số commit và trạng thái "chưa đẩy" trong các
  ghi chú cũ có thể đã lỗi thời: tính đến 10/10/2026 mọi commit đã có trên GitHub.
- Hướng dẫn làm việc của dự án nằm ở `CLAUDE.md` tại gốc repo (đã có trong git).
- Skill đánh giá `viet-ocr-eval` có trong git ở `skills/`; `.claude/skills/` trong gói là bản cài local của nó.
