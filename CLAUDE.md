# CLAUDE.md — JAMA HOME CRM

Hướng dẫn cho AI (Claude Code và các agent viết code) khi làm việc trong repo này.
Bốn nguyên tắc ở phần 1 lấy từ [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) (MIT),
bản đầy đủ ở `.claude/skills/karpathy-guidelines/SKILL.md`. Phần 2 là quy ước riêng của JAMA — khi hai phần vênh nhau, phần 2 thắng.

**Đánh đổi:** các nguyên tắc này ưu tiên cẩn thận hơn nhanh. Việc vặt (sửa chữ, đổi màu) thì dùng phán đoán.

## 1. Bốn nguyên tắc

### 1.1 Nghĩ trước khi code
- Nói rõ giả định. Không chắc thì hỏi, đừng tự đoán rồi chạy luôn.
- Yêu cầu hiểu được nhiều cách (vd. "sửa quyền" — quyền của role nào, ở API hay giao diện?) thì đưa ra các cách hiểu, đừng âm thầm chọn một.
- Có cách đơn giản hơn thì nói. Thấy yêu cầu có vấn đề thì phản biện.
- Chỗ nào chưa rõ thì dừng, gọi tên chỗ đó, hỏi.

### 1.2 Đơn giản trước tiên
- Chỉ code đúng thứ được yêu cầu. Không thêm tính năng "tiện thể".
- Không trừu tượng hoá cho code chỉ dùng một chỗ; không thêm cấu hình không ai xin.
- Không bắt lỗi cho tình huống không thể xảy ra.
- Viết 200 dòng mà 50 dòng là đủ thì viết lại.

### 1.3 Sửa đúng chỗ
- Chỉ đụng vào thứ cần đụng. Không "tiện tay" sửa code, comment, định dạng bên cạnh.
- Giữ đúng phong cách sẵn có (tên hàm tiếng Việt không dấu như `_lay_lead_xem_duoc`, comment tiếng Việt giải thích *vì sao*).
- Thấy code chết không liên quan thì báo, đừng xoá. Chỉ dọn import/biến mà chính thay đổi của mình làm thừa.
- Phép thử: mỗi dòng trong diff phải truy được về yêu cầu.

### 1.4 Làm theo mục tiêu kiểm chứng được
- Biến việc thành tiêu chí kiểm được: "sửa lỗi" → viết test tái hiện lỗi rồi làm nó qua; "thêm kiểm tra" → test cho đầu vào sai.
- Việc nhiều bước thì ghi kế hoạch ngắn: `bước → kiểm bằng: ...`.
- Chưa chạy kiểm chứng thì chưa báo "xong".

## 2. Quy ước của JAMA

**Cấu trúc**: `backend/` FastAPI + SQLAlchemy async (`app/api`, `app/models`, `app/services`, `app/agents`), `frontend/` Next.js + Tailwind, `telegram-bot/`, `zalo-listener/`. Kiến trúc: `docs/00-System-Architecture.md`; quyền: `docs/02-Role-Permission-Matrix.md`.

**Kiểm chứng trước khi commit**
- Backend: `cd backend && python -m pytest -q tests/<file liên quan>` (cả bộ chạy lâu, >5 phút — chạy file liên quan trước, cả bộ khi đụng phần dùng chung). Sửa lỗi thì thêm test `tests/test_<ten_khong_dau>.py`.
- Frontend: `cd frontend && npm run lint && npm run build`.
- Đổi model → thêm migration trong `backend/alembic/versions/` và nhớ chạy được trên cả SQLite lẫn Postgres (đã từng vỡ vì timezone, xem `test(migration)` 13/10).

**Phân quyền**: mọi endpoint mới phải kiểm quyền theo ma trận V3; không tin dữ liệu form gửi lên để quyết định quyền.

**AI agent trong sản phẩm** (`app/agents/`): luôn có luật dự phòng khi LLM lỗi/hết quota; ghi kết quả qua `services/ai_memory.py`; không gửi SĐT/tên khách thật lên LLM khi không cần.

**Commit**: Conventional Commits, mô tả tiếng Việt theo góc nhìn người dùng — `feat(hr): ...`, `fix(leads): ...`. Một commit một ý.

**Giao diện**: chữ tiếng Việt có dấu, dùng icon nét (không emoji) theo đợt sửa 24/10.
