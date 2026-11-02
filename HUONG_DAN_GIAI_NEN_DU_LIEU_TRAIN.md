# Hướng dẫn giải nén — dữ liệu train và gói bổ sung 2 (10/10/2026)

File này bổ sung cho `HUONG_DAN_KHOI_PHUC.md` (nằm trong gói chính `old-book-ocr-backup-20261010.tar.gz`).
Nó hướng dẫn giải nén ba gói còn lại. Dành cho người dùng mới hoặc một phiên Claude Code mới.

## 1. Ba gói này là gì

| Gói | Dung lượng | Số mục | Giải nén ra |
|---|---|---|---|
| `old-book-ocr-training-data-20261010.tar.gz` | 28,8 GB | 231.743 | `training/data/` (khoảng 29 GB) |
| `old-book-ocr-training-data-lines-20261010.tar.gz` | 28,5 GB | 725.583 | `training/data-lines/` (khoảng 30 GB) |
| `old-book-ocr-backup-20261010-bosung2.tar.gz` | 106 MB | 471 | các file lẻ trong `training/` và `backend/` (khoảng 470 MB) |

Nội dung từng gói:

- **`training-data`**: bộ dữ liệu train chính (crop theo đoạn) đã dựng từ VieBookRead.
  - `books-all/crops/paragraph/`: ảnh crop.
  - `books-all/train.jsonl`, `dev.jsonl`, `test.jsonl`, `gold.jsonl`: các split đã khoá.
  - `books-all/gold_verified.jsonl` và `gold_review/`: 250 trang gold đã được người kiểm. **Không dựng lại được.**
  - `books-all/data_manifest.json`: hash và thống kê của bản dựng.
- **`training-data-lines`**: bộ dữ liệu crop theo dòng (thí nghiệm ablation `exp_lines`, `exp_mix`).
- **`bosung2`**: các file không có trên GitHub mà gói chính bỏ sót.
  - `training/work/<run>/eval/step-*/`: dự đoán thô trên dev theo từng bước của các run. Không tạo lại được vì
    checkpoint trung gian không được sao lưu.
  - `training/work/feedback/`: trạng thái vòng phản hồi (`heldout_pages.json`, `locked_dhash.json`,
    `rehearsal_state.json`).
  - `training/work/merge_exp/`, `training/leaderboard/cache/`: kết quả thử merge và cache leaderboard.
  - `training/data-mixed/books-all/`: bộ dữ liệu trộn đoạn + dòng (5 file `.jsonl`).
  - `backend/data/backups/`: hai bản dump database cũ (25/09 và 28/09) và file env trước khi đổi secret.
    Chỉ có giá trị lịch sử; secret trong file env đó đã bị thu hồi.

## 2. Điều kiện trước khi giải nén

- Đã clone repo và giải nén gói chính theo `HUONG_DAN_KHOI_PHUC.md`.
- Còn trống ít nhất 60 GB cho dữ liệu sau giải nén, chưa kể chỗ để chính các file nén (57 GB).
- **Repo nên nằm ở `/home/huy/master`.** Các file `.jsonl` ghi `crop_path` là đường dẫn tuyệt đối
  `/home/huy/master/training/...`, và `training/configs/data*.yaml` cũng ghi cứng đường dẫn này. Xem mục 5 nếu
  repo nằm ở chỗ khác.

## 3. Kiểm tra gói

Đặt các file `.sha256` cùng thư mục với file nén rồi chạy:

```bash
sha256sum -c old-book-ocr-training-data-20261010.tar.gz.sha256
sha256sum -c old-book-ocr-training-data-lines-20261010.tar.gz.sha256
sha256sum -c old-book-ocr-backup-20261010-bosung2.tar.gz.sha256
```

Mỗi dòng phải kết thúc bằng `OK`. Hai gói lớn mất vài phút mỗi gói.

## 4. Giải nén

Cả ba gói dùng đường dẫn tính từ gốc repo, nên giải nén tại gốc repo. Thứ tự không quan trọng.

```bash
cd /home/huy/master
B=/duong/dan/toi/thu/muc/chua/file/nen

tar -xzf $B/old-book-ocr-training-data-20261010.tar.gz          # -> training/data/
tar -xzf $B/old-book-ocr-training-data-lines-20261010.tar.gz    # -> training/data-lines/
tar -xzf $B/old-book-ocr-backup-20261010-bosung2.tar.gz         # -> training/work/, training/data-mixed/, backend/data/backups/
```

Mỗi gói lớn mất khoảng 10–15 phút. Kiểm tra sau khi giải nén:

```bash
find training/data | wc -l          # 231743
find training/data-lines | wc -l    # 725583
wc -l < training/data/books-all/gold_verified.jsonl   # 250
git -C training status --short      # không được có file nào bị sửa
```

Các thư mục này đều bị git ignore, nên `git status` không liệt kê chúng; lệnh cuối chỉ để chắc rằng không file
đang theo dõi nào bị ghi đè sai.

Muốn đối chiếu hash của các split với bản gốc: `cd mlops && make verify-splits`.

## 5. Nếu repo không nằm ở `/home/huy/master`

Cách đơn giản nhất là tạo liên kết để đường dẫn cũ vẫn đúng:

```bash
sudo mkdir -p /home/huy
sudo ln -s /duong/dan/that/cua/repo /home/huy/master
```

Nếu không tạo liên kết, phải sửa `crop_path` trong mọi file `.jsonl` và các đường dẫn trong
`training/configs/data*.yaml`. Khi đó hash của các split sẽ khác bản gốc, `make verify-splits` sẽ báo lệch, và
các run mới sẽ không còn chung nhóm leaderboard với các run cũ.

## 6. Lưu ý khi dùng

- **Không chạy lại `prepare_data.py --books all` lên các thư mục này.** Lệnh đó luôn ghi vào
  `<out_dir>/books-all` và sẽ ghi đè các split đã khoá. Bản dòng dùng config riêng `configs/data_lines.yaml`.
- Tập test đã khoá. Đánh giá lại trên test là một lần truy cập test mới; xem `mlops/docs/REPRODUCE.md` bước 5.
- Corpus gốc `dataset/VieBookRead` và submodule `eda` **không** có trong các gói này. Chỉ cần chúng khi dựng lại dữ
  liệu từ đầu; huấn luyện, đánh giá và vòng phản hồi chạy được với ba gói này.
- VieBookRead theo giấy phép CC BY-NC 4.0 và sách còn bản quyền: không chia sẻ các gói này công khai.
