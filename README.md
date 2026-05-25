# disable_expired_ruleset

Tự động phát hiện và vô hiệu hóa các Cloudflare WAF Custom Rules đã hết hạn dựa trên quy ước đặt tên, kèm khả năng rollback về trạng thái ban đầu.

---

## Vấn đề giải quyết

Khi tạo rule WAF tạm thời trên Cloudflare (ví dụ: cho một domain dev/test đang trong quá trình phát triển, một đợt khuyến mãi, một IP cần chặn tạm thời...), người quản trị thường phải cấu hình disable các rule này khi hết hạn, hệ thống Cloudflare không có tính năng khai báo Schedule cho việc hết hạn của một Custom rules. Tool này tự động quét toàn bộ zone, tìm ra những rule đã quá hạn, và vô hiệu hóa chúng — đồng thời lưu log để có thể rollback nếu cần.

---

## Quy ước đặt tên rule

Rule được coi là "có ngày hết hạn" khi tên (description) chứa pattern:

```
_expire-YYYY-MM-DD
```

**Ví dụ:**
```
Block_VN_Voucher_expire-2024-03-15
Allow_Internal_Test_expire-2025-01-01
```

Rule sẽ bị vô hiệu hóa khi: rule đang **enabled** VÀ ngày hết hạn đã **trước ngày hôm nay**.

---

## Luồng hoạt động (Logical Flow)

```
┌─────────────────────────────────────────────────────────────┐
│                        handler/main.py                       │
│                       (Entry Point)                          │
└────────────────────────────┬────────────────────────────────┘
                             │
                    1. Load .env (CF_API_TOKEN, CF_EMAIL)
                             │
                    2. Fetch all Zones  ◄──── adapter/api/cloudflare_api.py
                       (paginated)             get_all_zones()
                             │
                    3. Fetch Rules per Zone
                       (concurrent threads)  ◄ fetch_rules() × N zones
                             │
                    4. Display by Domain ◄─── modules/display.py
                       + per-type summary     domain_header()
                                              print_domain_summary()
                             │
                    5. Build Rule Index ◄──── modules/rule_index.py
                       (name, rule_id,        build_rule_index()
                        zone_name, toggle_info)
                             │
                    6. Find Expired Rules ◄── modules/expiry_checker.py
                       (regex _expire-DATE)   find_expired()
                             │
                    7. Show expired list
                       + confirm Y/N
                             │
                    8. Disable Rules ──────── adapter/api/cloudflare_api.py
                       (PATCH API call)       disable_rule()
                             │
                    9. Save Disable Log ◄──── modules/action_log.py
                       (JSON, timestamped)    save_disable_log()
                             │
                           DONE
```

---

## Luồng Rollback

```
┌─────────────────────────────────────────────────────────────┐
│                      handler/rollback.py                     │
└────────────────────────────┬────────────────────────────────┘
                             │
                    1. List all log files ◄── modules/action_log.py
                       in variables/logs/     list_logs()
                             │
                    2. User chọn session
                       (hiện rule count)
                             │
                    3. Load log file ─────── load_log()
                             │
                    4. Re-enable Rules ────── adapter/api/cloudflare_api.py
                       (PATCH API call)       enable_rule()
                             │
                    5. Hiển thị kết quả
                       (success / error count)
```

---

## Kiến trúc thư mục

```
disable_expired_ruleset/
│
├── handler/                  # Entry points
│   ├── main.py               # Chạy chính: quét và disable rule hết hạn
│   └── rollback.py           # Rollback: re-enable rule từ log cũ
│
├── adapter/                  # I/O layer (API + Utilities)
│   ├── api/
│   │   └── cloudflare_api.py # HTTP calls đến Cloudflare API v4
│   │                         # (GET zones, GET rules, PATCH enable/disable)
│   └── utils/
│       ├── console.py        # ANSI color helpers, formatted output
│       └── env_loader.py     # Parse file .env thủ công (không cần python-dotenv)
│
├── modules/                  # Business logic
│   ├── rule_types.py         # Định nghĩa loại rule (WAF Custom Rules...)
│   ├── rule_utils.py         # Helpers: đọc tên rule, kiểm tra trạng thái
│   ├── rule_index.py         # Build index toàn bộ rule từ API response
│   ├── expiry_checker.py     # Regex parse ngày hết hạn, lọc rule expired
│   ├── display.py            # In kết quả ra terminal (domain, summary)
│   └── action_log.py         # Đọc/ghi log JSON cho disable/rollback
│
└── variables/
    ├── .env.example          # Template cấu hình
    └── logs/                 # Auto-generated: log JSON mỗi lần disable
```

---

## Cài đặt

**Yêu cầu:** Python 3.8+ — không cần cài thêm package nào (chỉ dùng standard library).

**1. Clone repo**
```bash
git clone https://github.com/longtk-dev/disable_expired_ruleset.git
cd disable_expired_ruleset
```

**2. Tạo file `.env`**
```bash
cp variables/.env.example variables/.env
```

Chỉnh sửa `variables/.env`:
```env
CF_API_TOKEN=your_cloudflare_api_token_here
CF_EMAIL=your_cloudflare_email_here
```

> API Token cần quyền: `Zone.Zone:Read` và `Zone.Firewall Services:Edit`

---

## Sử dụng

### Quét và disable rule hết hạn
```bash
python -m handler.main
```

Chương trình sẽ:
1. Hiển thị toàn bộ rule WAF theo từng domain
2. Liệt kê các rule có `_expire-DATE` đã quá hạn
3. Hỏi xác nhận trước khi disable
4. Lưu log vào `variables/logs/disable_YYYYMMDD_HHMMSS.json`

### Rollback — re-enable lại rule đã tắt
```bash
python -m handler.rollback
```

Chương trình sẽ:
1. Liệt kê các session disable đã lưu (kèm số lượng rule)
2. Cho chọn session cần rollback
3. Re-enable toàn bộ rule trong session đó

---

## Ví dụ output

```
╔══════════════════════════════════════╗
║       Cloudflare WAF Rule Scanner    ║
╚══════════════════════════════════════╝

[1] example.com  (zone: abc123)
  Custom Rules (WAF)
  ├─ enabled  : ████████░░  8
  └─ disabled : ░░░░░░░░██  2

Expired rules found (2):
  • Block_VN_Promo_expire-2024-12-01  →  expired 145 days ago
  • Allow_Test_IP_expire-2025-01-15   →  expired 10 days ago

Disable these 2 rules? [y/N]: y

  ✓ Block_VN_Promo_expire-2024-12-01 — disabled
  ✓ Allow_Test_IP_expire-2025-01-15  — disabled

Log saved: variables/logs/disable_20250524_153000.json
```

---

## Cơ chế retry & rate limit

`cloudflare_api.py` tự động xử lý lỗi `429 Too Many Requests` với **exponential backoff**:
- Lần 1: chờ 2 giây
- Lần 2: chờ 4 giây
- Lần 3: chờ 8 giây
- Sau 3 lần thất bại: raise exception

---

## Mở rộng thêm loại rule

Chỉnh sửa `modules/rule_types.py` để thêm loại rule mới:

```python
RULE_TYPES = [
    {
        "name": "Custom Rules (WAF)",
        "endpoint": "/rulesets/phases/http_request_firewall_custom/entrypoint",
        "name_key": "description",
        "phase_endpoint": True,
    },
    # Thêm loại rule mới ở đây
    {
        "name": "Rate Limiting Rules",
        "endpoint": "/rulesets/phases/http_ratelimit/entrypoint",
        "name_key": "description",
        "phase_endpoint": True,
    },
]
```
