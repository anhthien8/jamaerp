# 🤖 JAMA HOME — Tài liệu AI Agent Workflow

> **Phiên bản:** 1.0 | **Cập nhật:** 26/06/2026
> **Dành cho:** Tất cả nhân viên JAMA HOME — từ Sale, Leader, Kế toán đến Design
> **Hệ thống:** JAMA HOME CRM (Next.js 16 + FastAPI + SQLite + Telegram Bot)

---

## Mục lục

1. [Tổng quan AI Agent System](#1-tổng-quan-ai-agent-system)
2. [Workflow cho từng Role](#2-workflow-cho-từng-role)
   - 2.1 [Nhân viên Sale (data_entry)](#21-nhân-viên-sale-data_entry)
   - 2.2 [Trưởng phòng Sale (leader)](#22-trưởng-phòng-sale-leader)
   - 2.3 [Giám đốc (admin)](#23-giám-đốc-admin)
   - 2.4 [Kế toán / Nhân sự (accountant)](#24-kế-toán--nhân-sự-accountant)
   - 2.5 [Designer (thiết kế)](#25-designer-thiết-kế)
3. [AI Automation Flows (n8n / Telegram)](#3-ai-automation-flows-n8n--telegram)
4. [Technical Implementation](#4-technical-implementation)
5. [AI Enhancements — Tương lai](#5-ai-enhancements--tương-lai)

---

## 1. Tổng quan AI Agent System

### 1.1 Kiến trúc hoạt động: Rule-based + LLM Hybrid

JAMA HOME sử dụng mô hình **Hybrid AI** — kết hợp giữa quy tắc cứng (rule-based) và mô hình ngôn ngữ lớn (LLM):

```
┌─────────────────────────────────────────────────────────────────────┐
│                    JAMA HOME AI ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  User Action ──► API Request ──► AI Router                          │
│                                      │                              │
│                              ┌───────┴────────┐                     │
│                              ▼                 ▼                     │
│                     ┌──────────────┐  ┌────────────────┐            │
│                     │  RULE-BASED  │  │  LLM (Groq)    │            │
│                     │  Engine      │  │  claude-opus-4.8.3-70B  │            │
│                     │              │  │  + litellm      │            │
│                     │  ✓ Regex     │  │  ✓ NLP parse    │            │
│                     │  ✓ Keywords  │  │  ✓ Context      │            │
│                     │  ✓ Scoring   │  │  ✓ Suggestions  │            │
│                     │  ✓ Always-on │  │  ✓ With retry   │            │
│                     └──────┬───────┘  └───────┬────────┘            │
│                            │                  │                      │
│                            ▼                  ▼                      │
│                     ┌─────────────────────────────────┐              │
│                     │     RESPONSE NORMALIZER          │              │
│                     │  (merge & validate result)       │              │
│                     └──────────────┬──────────────────┘              │
│                                    ▼                                 │
│                              JSON Response                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Nguyên tắc hoạt động:**

| Thành phần | Mô tả | Khi nào dùng |
|---|---|---|
| **Rule-based Engine** | Regex extraction, keyword matching, scoring weights | Luôn chạy — đảm bảo hệ thống không bao giờ crash |
| **LLM Engine** | Groq API (`claude-opus-4.8.3-70B`),通过 `litellm` router | Thử gọi LLM trước — nếu fail → tự động fallback về rule-based |
| **Fallback** | Regex fallback khi LLM không khả dụng | LLM timeout, rate limit, hoặc lỗi network |

### 1.2 Ba AI Capabilities hiện tại

```
┌──────────────────────────────────────────────────────────────┐
│                  3 AI AGENTS ĐANG HOẠT ĐỘNG                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌────────────────┐  ┌──────────────────┐ │
│  │  🤖 LEAD     │  │  🤖 SALES      │  │  🤖 LEAD         │ │
│  │  INTAKE      │  │  CO-PILOT      │  │  SCORING         │ │
│  │              │  │                │  │                  │ │
│  │  Paste text  │  │  Click lead →  │  │  Auto-score      │ │
│  │  from Zalo/  │  │  Get action    │  │  0-100 based     │ │
│  │  Facebook →  │  │  suggestions   │  │  on budget,      │ │
│  │  Auto-fill   │  │  + message     │  │  source, type,   │ │
│  │  lead form   │  │  templates     │  │  recency         │ │
│  └──────┬───────┘  └───────┬────────┘  └────────┬─────────┘ │
│         │                  │                     │            │
│         ▼                  ▼                     ▼            │
│  POST /ai/parse-lead   POST /ai/          POST /ai/          │
│                        suggest-action     score-lead          │
│                                                              │
│  Backend: backend/app/api/ai.py                              │
│  Agents:  backend/app/agents/lead_intake.py                  │
│           backend/app/agents/sales_copilot.py                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 LLM Provider & Configuration

```python
# backend/app/config.py
LLM_PROVIDER: str = "groq"           # groq / nhà cung cấp dịch vụ AI / openrouter
LLM_MODEL: str = "groq/claude-opus-4.8-3.3-70b-versatile"  # Model ID
LLM_API_KEY: str = ""                # Groq API key (từ .env)
LLM_FALLBACK_RULES: bool = True     # Luôn bật rule-based fallback
```

**Quy trình fallback:**

```
LLM Call ──► Success? ──Yes──► Parse JSON ──► Return
    │
    No (timeout/error)
    │
    ▼
Rule-based Fallback ──► Regex Parse ──► Return
```

---

## 2. Workflow cho từng Role

---

### 2.1 Nhân viên Sale (`data_entry`)

#### Daily Workflow — Một ngày điển hình

```
╔══════════════════════════════════════════════════════════════╗
║         NGÀY LÀM VIỆC CỦA NHÂN VIÊN SALE                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  08:00  ┌─────────────────────────────────┐                  ║
║         │ 🔔 LOGIN → Dashboard            │                  ║
║         │ • Xem leads quá hạn (AI flag)   │                  ║
║         │ • Xem leads mới chưa xử lý      │                  ║
║         │ • AI gợi ý ưu tiên hôm nay      │                  ║
║         └──────────────┬──────────────────┘                  ║
║                        ▼                                     ║
║  08:30  ┌─────────────────────────────────┐                  ║
║         │ 📱 NHẬN LEAD TỪ ZALO/FB        │                  ║
║         │ • Copy text từ Zalo              │                  ║
║         │ • Paste vào AI Lead Intake       │                  ║
║         │ • AI auto-fill form lead         │                  ║
║         │ • Review & Confirm               │                  ║
║         └──────────────┬──────────────────┘                  ║
║                        ▼                                     ║
║  09:00  ┌─────────────────────────────────┐                  ║
║         │ 📞 GỌI LEAD — AI CO-PILOT       │                  ║
║         │ • Click vào lead                 │                  ║
║         │ • AI suggest hành động tiếp theo │                  ║
║         │ • Copy mẫu tin nhắn từ AI       │                  ║
║         │ • Gọi điện / gửi Zalo           │                  ║
║         └──────────────┬──────────────────┘                  ║
║                        ▼                                     ║
║  10:00  ┌─────────────────────────────────┐                  ║
║         │ 📝 GHI CHÚ SAU CUỘC GỌI       │                  ║
║         │ • Thêm activity log             │                  ║
║         │ • AI gợi ý bước tiếp theo       │                  ║
║         │ • Tự động update lead stage     │                  ║
║         └──────────────┬──────────────────┘                  ║
║                        ▼                                     ║
║  14:00  ┌─────────────────────────────────┐                  ║
║         │ 🔄 LÀM VIỆC VỚI LEADS HIỆN CÓ  │                  ║
║         │ • Lead "potential" → Gửi báo giá│                  ║
║         │ • Lead "interested" → Hẹn lịch   │                  ║
║         │ • AI score cao → Ưu tiên trước   │                  ║
║         └──────────────┬──────────────────┘                  ║
║                        ▼                                     ║
║  17:00  ┌─────────────────────────────────┐                  ║
║         │ 📊 END OF DAY — AI REVIEW       │                  ║
║         │ • Pipeline overview              │                  ║
║         │ • Leads cần follow-up ngày mai  │                  ║
║         │ • Gợi ý ưu tiên cho ngày mai    │                  ║
║         └─────────────────────────────────┘                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

#### AI Features cho Sale

##### 🤖 Feature 1: Lead Intake — Paste text → Auto-fill

**Cách dùng:** Mở trang Leads → Nhấn nút "AI Parse" → Paste text tin nhắn Zalo/Facebook → AI tự động trích xuất thông tin.

**Quy trình kỹ thuật:**

```
                    ┌──────────────────┐
                    │  User paste text  │
                    │  từ Zalo/Facebook │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  POST /ai/parse  │
                    │  -lead            │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                              ▼
     ┌─────────────────┐           ┌─────────────────┐
     │  LLM CALL        │           │  REGEX FALLBACK  │
     │  (Groq API)      │           │  (rule-based)    │
     │                  │           │                  │
     │  • NLP extract   │           │  • PHONE_PATTERN │
     │  • JSON parse    │           │  • BUDGET_PATTERN│
     │  • Smart context │           │  • AREA_PATTERN  │
     └────────┬─────────┘           │  • Keywords      │
              │                     └────────┬─────────┘
              ▼                              ▼
     ┌────────────────────────────────────────────┐
     │           LeadParseResponse                 │
     │  {                                          │
     │    name: "Chị Mai",                         │
     │    phone: "0912345678",                     │
     │    source: "zalo",                          │
     │    property_type: "townhouse",              │
     │    area_sqm: 180,                           │
     │    estimated_budget: 500000000,             │
     │    confidence: 0.85                         │
     │  }                                          │
     └────────────────────────────────────────────┘
```

**Ví dụ thực tế:**

```
╔══════════════════════════════════════════════════════════════╗
║  INPUT (Text từ Zalo):                                       ║
╠══════════════════════════════════════════════════════════════╣
║  "Chị Mai, nhà phố Q7, 180m2, ngân sách 500tr,            ║
║   cần thiết kế hiện đại. Sđt: 0912345678"                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  AI OUTPUT (auto-filled form):                               ║
║  ┌──────────────────────────────────────────┐                ║
║  │ Tên khách hàng:  Chị Mai          ✓      │                ║
║  │ Số điện thoại:   0912345678        ✓      │                ║
║  │ Nguồn:          Zalo              ✓      │                ║
║  │ Loại BĐS:       Nhà phố           ✓      │                ║
║  │ Diện tích:       180 m²            ✓      │                ║
║  │ Ngân sách:       500 triệu        ✓      │                ║
║  │ Nhu cầu:        Thiết kế hiện đại ✓      │                ║
║  │ District:        Q7                ✓      │                ║
║  └──────────────────────────────────────────┘                ║
║  Confidence: 85% ────────────────────░░░░░░                  ║
║                                                              ║
║  RULE-BASED DETECTION:                                       ║
║  • Phone:  regex \d{10} match                → 0912345678    ║
║  • Budget: "500tr" → 500 × 1,000,000        → 500,000,000   ║
║  • Area:   "180m2" → 180                     → 180.0         ║
║  • Source: keyword "Zalo" match              → zalo          ║
║  • Type:   keyword "nhà phố" match           → townhouse     ║
╚══════════════════════════════════════════════════════════════╝
```

##### 🤖 Feature 2: Sales Co-Pilot — Hành động tiếp theo

**Cách dùng:** Mở chi tiết lead → Nhấn nút "AI Gợi ý" → Nhận hành động + mẫu tin nhắn.

**Quy trình:**

```
  Click Lead ──► GET /ai/suggest-action?lead_id=xxx
                        │
                        ▼
              ┌───────────────────┐
              │  Gather Context   │
              │                   │
              │  • Lead info      │
              │  • Stage hiện tại │
              │  • Last activity  │
              │  • Budget, source │
              │  • Activity count │
              └────────┬──────────┘
                       │
                       ▼
              ┌───────────────────┐
              │  LLM CALL          │
              │  System prompt:    │
              │  "Bạn là Sales     │
              │   Co-Pilot AI..."  │
              │                   │
              │  context: lead     │
              │  details           │
              └────────┬──────────┘
                       │
                       ▼
              ┌───────────────────┐
              │  SUGGESTION       │
              │  {                 │
              │    action: "Gọi    │
              │     điện tư vấn"   │
              │    reason: "Lead   │
              │     mới, cần gọi  │
              │     trong ngày"   │
              │    priority: high  │
              │    message: "Xin  │
              │     chào Anh..."  │
              │  }                 │
              └───────────────────┘
```

**Hành động gợi ý theo Pipeline Stage:**

```
  Stage: new ──────────► "Gọi điện giới thiệu dịch vụ"
     │                    Message: "Xin chào {name}, em là [tên] từ
     │                    JAMA HOME. Em được biết anh/chị đang quan
     │                    tâm đến thiết kế nội thất..."
     │
     ▼
  Stage: interested ───► "Hẹn lịch khảo sát thực tế"
     │                    Message: "{name}, JAMA HOME xin hẹn khảo
     │                    sát thực tế nhà anh/chị vào [ngày].
     │                    Thời gian khoảng 30-45 phút ạ."
     │
     ▼
  Stage: survey_ ─────► "Xác nhận lịch & chuẩn bị hồ sơ"
     scheduled            (Priority: medium — đã có lịch)
     │
     ▼
  Stage: potential ────► "Gửi phương án thiết kế + báo giá"
     │                    (Priority: high — push ký hợp đồng)
     │
     ▼
  Stage: signed_design ► "Theo dõi tiến độ dự án"
                          (Priority: low — đã ký)
```

##### 🤖 Feature 3: Lead Scoring — Chấm điểm 0-100

**Cách dùng:** Điểm số tự động cập nhật khi lead thay đổi. Xem trên dashboard cột "AI Score".

**Thuật toán scoring:**

```
┌───────────────────────────────────────────────────────────────────┐
│                    LEAD SCORING ALGORITHM                         │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  BASE SCORE                              = 30 points              │
│                                                                   │
│  ┌─ BUDGET WEIGHT ────────────────────────────────────────┐       │
│  │  ≥ 2 tỷ          +30 pts  ████████████████████████████  │       │
│  │  ≥ 1 tỷ          +25 pts  █████████████████████         │       │
│  │  ≥ 500 triệu     +20 pts  ██████████████                │       │
│  │  ≥ 200 triệu     +10 pts  ███████                       │       │
│  │  < 200 triệu      +0 pts                                │       │
│  └────────────────────────────────────────────────────────┘       │
│                                                                   │
│  ┌─ SOURCE WEIGHT ────────────────────────────────────────┐       │
│  │  Referral         +20 pts  ████████████████████████████  │       │
│  │  Website          +15 pts  ██████████████████            │       │
│  │  Zalo             +12 pts  ██████████████                │       │
│  │  Facebook         +10 pts  ████████████                  │       │
│  │  TikTok            +8 pts  █████████                     │       │
│  └────────────────────────────────────────────────────────┘       │
│                                                                   │
│  ┌─ PROPERTY TYPE ────────────────────────────────────────┐       │
│  │  Villa / Shophouse +10 pts                               │       │
│  │  Townhouse          +8 pts                               │       │
│  │  Other              +0 pts                               │       │
│  └────────────────────────────────────────────────────────┘       │
│                                                                   │
│  ┌─ RECENCY ──────────────────────────────────────────────┐       │
│  │  Liên hệ ≤1 ngày  +10 pts                               │       │
│  │  Liên hệ ≤3 ngày   +5 pts                               │       │
│  │  Liên hệ >3 ngày    +0 pts                              │       │
│  └────────────────────────────────────────────────────────┘       │
│                                                                   │
│  MAX = 100 pts, MIN = 0 pts                                      │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

**Ví dụ tính toán:**

```
╔══════════════════════════════════════════════════════════════╗
║  LEAD: Chị Mai — Nhà phố Q7                                 ║
╠══════════════════════════════════════════════════════════════╣
║  Base Score                           30 pts                ║
║  Budget: 500 triệu (≥500tr)           +20 pts                ║
║  Source: Zalo                          +12 pts                ║
║  Type: Townhouse                       +8 pts                 ║
║  Recency: Hôm nay                     +10 pts                ║
║  ─────────────────────────────────────────────               ║
║  TOTAL AI SCORE:                       72 / 100              ║
║                                                              ║
║  Rating: ★★★★☆ — Lead tiềm năng, cần ưu tiên              ║
╚══════════════════════════════════════════════════════════════╝
```

---

### 2.2 Trưởng phòng Sale (`leader`)

#### Daily Workflow

```
╔══════════════════════════════════════════════════════════════╗
║        NGÀY LÀM VIỆC CỦA TRƯỞNG PHÒNG SALE                 ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  08:00  ┌─────────────────────────────────────┐              ║
║         │ 📊 TEAM DASHBOARD                    │              ║
║         │ • Leads today: 5 mới               │              ║
║         │ • Leads overdue: 3 (cần xử lý)     │              ║
║         │ • Pipeline: 5.43 tỷ                 │              ║
║         │ • SLA compliance: 85%               │              ║
║         └──────────────┬──────────────────────┘              ║
║                        ▼                                     ║
║  08:30  ┌─────────────────────────────────────┐              ║
║         │ 🔍 REVIEW OVERDUE LEADS             │              ║
║         │ • AI alert: "Lê Văn A: 5 ngày chưa │              ║
║         │   follow-up lead潜在 2.5 tỷ"        │              ║
║         │ • AI suggest: "Gọi ngay, risk mất" │              ║
║         └──────────────┬──────────────────────┘              ║
║                        ▼                                     ║
║  09:00  ┌─────────────────────────────────────┐              ║
║         │ 👥 PHÂN CÔNG LEADS CHƯA ASSIGN      │              ║
║         │ • AI gợi ý: Leadvilla 3 tỷ →       │              ║
║         │   Trần Sales (best converter)       │              ║
║         │ • AI gợi ý: Lead apartment 500tr → │              ║
║         │   Lê Sales (available)              │              ║
║         └──────────────┬──────────────────────┘              ║
║                        ▼                                     ║
║  10:00  ┌─────────────────────────────────────┐              ║
║         │ 📈 PERFORMANCE ANALYSIS             │              ║
║         │ • Trần Sales: 85% conversion       │              ║
║         │ • Lê Sales: 60% conversion         │              ║
║         │ • Phạm Sales: 45% conversion       │              ║
║         │ • Action: Coaching session 1-on-1   │              ║
║         └──────────────┬──────────────────────┘              ║
║                        ▼                                     ║
║  14:00  ┌─────────────────────────────────────┐              ║
║         │ 💰 COMMISSION & PIPELINE REVIEW     │              ║
║         │ • Deals dự kiến ký tháng này: 3    │              ║
║         │ • Tổng dự kiến: 3.5 tỷ             │              ║
║         │ • Hoa hồng pending: 145 triệu       │              ║
║         └─────────────────────────────────────┘              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

#### AI Features cho Leader

##### 🤖 Team Performance Analytics

```
┌────────────────────────────────────────────────────────────────┐
│  TEAM PERFORMANCE DASHBOARD                                    │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Sales        │ Leads │ Conv% │ Pipeline │ Score │ Trend       │
│  ─────────────┼───────┼───────┼──────────┼───────┼───────────  │
│  Trần Thị     │  12   │ 85%   │  2.8 tỷ  │  78   │ ↑ +5%     │
│  Lê Văn       │   8   │ 60%   │  1.2 tỷ  │  65   │ → same    │
│  Phạm Đức     │  10   │ 45%   │  1.43 tỷ │  52   │ ↓ -3%     │
│  ─────────────┼───────┼───────┼──────────┼───────┼───────────  │
│  TEAM AVG     │  10   │ 63%   │  5.43 tỷ │  65   │            │
│                                                                │
│  AI INSIGHTS:                                                  │
│  • Trần Thị đang best performer — nên assign leads lớn       │
│  • Phạm Đức cần coaching: low conversion + nhiều leads       │
│  • Lê Văn ổn định, cần push thêm pipeline                    │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

##### 🤖 Lead Assignment — AI gợi ý phân công

```
  Lead chưa phân công ──► AI phân tích:
                             │
                    ┌────────┴────────┐
                    │  Match Factors   │
                    │                  │
                    │  • Workload/     │
                    │    người         │
                    │  • Specialty     │
                    │    (villa vs     │
                    │    apartment)    │
                    │  • Conversion    │
                    │    rate          │
                    │  • Availability  │
                    │  • Budget level  │
                    │    experience    │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │  AI RECOMMEND    │
                    │                  │
                    │  "Lead villa 3tỷ │
                    │   → Trần Thị     │
                    │   (best rate,    │
                    │   low workload)" │
                    └──────────────────┘
```

##### 🤖 Pipeline Forecasting

```
┌──────────────────────────────────────────────────────────────┐
│  PIPELINE FORECAST — Tháng 06/2026                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Pipeline Stages:                                            │
│                                                              │
│  new (2 leads)           ██░░░░░░░░░░░░░░  → ~10% convert  │
│  interested (3)          ████░░░░░░░░░░░░  → ~30% convert  │
│  survey_scheduled (2)    ██████████░░░░░░  → ~50% convert  │
│  potential (3)           ████████████████  → ~70% convert  │
│  signed_design (2)       ████████████████  → 100% (done)   │
│                                                              │
│  FORECAST:                                                   │
│  • Deals dự kiến ký:     3 deals                            │
│  • Tổng giá trị:         3.5 tỷ                             │
│  • Revenue month:        1.49 tỷ (actual) + 3.5 tỷ (pipe)  │
│  • Commission estimate:  145 triệu (pending)                │
│                                                              │
│  RISK ALERTS:                                                │
│  ⚠ Anh Tuấn (2.5 tỷ) ở "potential" 7 ngày → cần push      │
│  ⚠ Chị Linh (800tr) chưa liên hệ 5 ngày → risk dormant    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

##### 🤖 Commission Calculator

```
┌──────────────────────────────────────────────────────────────┐
│  COMMISSION RULES — JAMA HOME                                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─ Design Contract ────────────────────────────────────┐    │
│  │  Sales:      3%  giá trị hợp đồng thiết kế         │    │
│  │  Leader:     0.5% override                           │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ Construction ───────────────────────────────────────┐    │
│  │  Sales:      2%  giá trị hợp đồng thi công          │    │
│  │  Leader:     0.5% override                           │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ Payment Milestones ─────────────────────────────────┐    │
│  │  Ký hợp đồng:          50% (hoá đơn 1)              │    │
│  │  Hoàn thành thô:       30% (hoá đơn 2)              │    │
│  │  Bàn giao:             20% (hoá đơn cuối)           │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  VÍ DỤ: Hợp đồng thiết kế 150 triệu                       │
│  • Sales commission:  150 × 3% = 4.5 triệu                 │
│  • Leader override:   150 × 0.5% = 0.75 triệu              │
│  • Tổng hoa hồng:     5.25 triệu                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

### 2.3 Giám đốc (`admin`)

#### Daily Workflow

```
╔══════════════════════════════════════════════════════════════╗
║         NGÀY LÀM VIỆC CỦA GIÁM ĐỐC                        ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  07:30  ┌──────────────────────────────────────────┐         ║
║         │ 📱 TELEGRAM BRIEFING (Auto @ 8:00 AM)   │         ║
║         │                                          │         ║
║         │  📊 JAMA HOME Daily Briefing              │         ║
║         │  ── 26/06/2026 ──                         │         ║
║         │  • Leads mới: 2 (Anh Phong, Chị Thảo)   │         ║
║         │  • Leads quá hạn: 3 (cần xử lý)         │         ║
║         │  • Pipeline value: 5.43 tỷ               │         ║
║         │  • Dự án sắp bàn giao:                   │         ║
║         │    Căn hộ Sunrise (Chị Hương) — 90%     │         ║
║         │  • Doanh thu tháng:                      │         ║
║         │    Revenue: 1.49 tỷ | Chi: 783 tr        │         ║
║         │    Lợi nhuận: 707 triệu                  │         ║
║         └──────────────┬───────────────────────────┘         ║
║                        ▼                                     ║
║  09:00  ┌──────────────────────────────────────────┐         ║
║         │ 📊 EXECUTIVE DASHBOARD                    │         ║
║         │                                          │         ║
║         │ KPI Summary:                              │         ║
║         │ • Total leads: 47                        │         ║
║         │ • Conversion rate: 23%                   │         ║
║         │ • Avg deal size: 1.2 tỷ                 │         ║
║         │ • Revenue MTD: 1.49 tỷ                  │         ║
║         │ • Target: 3 tỷ (50% achieved)           │         ║
║         └──────────────┬───────────────────────────┘         ║
║                        ▼                                     ║
║  10:00  ┌──────────────────────────────────────────┐         ║
║         │ 💰 FINANCIAL REVIEW                       │         ║
║         │ • P&L real-time                          │         ║
║         │ • Commission approval queue: 3 requests  │         ║
║         │ • Cash flow forecast                     │         ║
║         └──────────────┬───────────────────────────┘         ║
║                        ▼                                     ║
║  14:00  ┌──────────────────────────────────────────┐         ║
║         │ 🎯 STRATEGIC DECISIONS (AI-assisted)     │         ║
║         │ • Market analysis                        │         ║
║         │ • Resource allocation                    │         ║
║         │ • Growth opportunities                   │         ║
║         └──────────────────────────────────────────┘         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

#### AI Features cho Giám đốc

##### 🤖 Daily Telegram Briefing (Auto)

```
┌──────────────────────────────────────────────────────────────┐
│  TELEGRAM BRIEFING — Gửi tự động lúc 8:00 AM hàng ngày     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  📊 JAMA HOME Daily Briefing — 26/06/2026                   │
│  ═══════════════════════════════════════                    │
│                                                              │
│  📌 LEADS                                                    │
│  • Mới hôm nay: 2 (Anh Phong, Chị Thảo)                   │
│  • Quá hạn (>3 ngày): 3                                     │
│  • Tổng đang active: 34                                     │
│                                                              │
│  💼 PIPELINE                                                 │
│  • Total value: 5.43 tỷ                                     │
│  • Deals dự kiến ký: 3 trong tháng này                     │
│                                                              │
│  📋 DỰ ÁN                                                    │
│  • Sắp bàn giao: Căn hộ Sunrise (Chị Hương) — 90%          │
│  • Đang thi công: Biệt thự Thảo Điền (Anh B) — 60%        │
│                                                              │
│  💰 TÀI CHÍNH                                                │
│  • Doanh thu tháng: 1.49 tỷ                                 │
│  • Chi phí: 783 triệu                                       │
│  • Lợi nhuận: 707 triệu                                    │
│                                                              │
│  ⚠️  ALERTS                                                   │
│  • Lead Anh Tuấn (2.5 tỷ) risk mất — 7 ngày không liên hệ │
│  • Hoa hồng pending: 145 triệu — chờ duyệt                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

##### 🤖 Risk Detection

```
  ┌──────────────────────────────────────────────────────────┐
  │  AI RISK SCANNER — Chạy mỗi ngày                         │
  ├──────────────────────────────────────────────────────────┤
  │                                                          │
  │  Rule 1: Stale Leads                                     │
  │  ─────────────────────                                   │
  │  IF lead.last_contacted > 5 days                         │
  │  AND lead.stage NOT IN [signed_design, lost]             │
  │  THEN → ALERT "Risk dormant"                             │
  │                                                          │
  │  Rule 2: High-Value Leads Stalling                       │
  │  ─────────────────────────────────                       │
  │  IF lead.estimated_budget > 1 tỷ                        │
  │  AND days_in_stage > 7                                   │
  │  THEN → ALERT "Risk lost high-value"                     │
  │                                                          │
  │  Rule 3: Project Overdue                                 │
  │  ─────────────────────────                               │
  │  IF project.deadline - today < 7 days                    │
  │  AND project.completion < 80%                            │
  │  THEN → ALERT "Overdue risk"                             │
  │                                                          │
  │  Rule 4: Budget Overrun                                  │
  │  ───────────────────────                                 │
  │  IF actual_cost > estimated_budget × 1.1                 │
  │  THEN → ALERT "Budget overrun"                           │
  │                                                          │
  └──────────────────────────────────────────────────────────┘
```

##### 🤖 Executive Dashboard

```
┌──────────────────────────────────────────────────────────────┐
│  EXECUTIVE DASHBOARD — JAMA HOME                             │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ╔═══════════╗  ╔═══════════╗  ╔═══════════╗  ╔═══════════╗│
│  ║  REVENUE   ║  ║   LEADS    ║  ║  PROJECTS  ║  ║   TEAM    ║│
│  ║  1.49 tỷ  ║  ║  47 total  ║  ║  8 active  ║  ║  5 staff  ║│
│  ║  ▲ +12%   ║  ║  ▲ +5      ║  ║  2 ending  ║  ║  100%     ║│
│  ╚═══════════╝  ╚═══════════╝  ╚═══════════╝  ╚═══════════╝│
│                                                              │
│  CONVERSION FUNNEL:                                          │
│                                                              │
│  ████████████████████████████████████████   47 Total Leads   │
│  ██████████████████████████████             34 Contacted     │
│  ████████████████████                       20 Surveyed      │
│  ██████████████                             14 Potential     │
│  ████████                                    8 Signed        │
│  █████                                       5 Completed    │
│                                                              │
│  Revenue:    1.49 tỷ / 3 tỷ target  ████████████░░░░░  50%  │
│  Profit:     707 tr                  ████████████████░░  88%  │
│  Target hit: On track                                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

### 2.4 Kế toán / Nhân sự (`accountant`)

#### AI Features

##### 🤖 Transaction Categorizer

```
┌──────────────────────────────────────────────────────────────┐
│  AUTO-CATEGORIZE TRANSACTIONS                                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Input: Raw transaction description                          │
│                                                              │
│  "Thanh toán vật tư Greenwood"  ──► Category: "Vật tư"      │
│  "Lương tháng 6 - Trần Thị"   ──► Category: "Lương"        │
│  "Thu khách hàng Anh B"         ──► Category: "Thu.design"  │
│  "Phí vận chuyển nội thất"     ──► Category: "Vận chuyển"  │
│  "Tiền thuê văn phòng Q1"      ──► Category: "Thuê văn pḥ" │
│  "Hoa hồng sales tháng 5"      ──► Category: "Hoa hồng"     │
│                                                              │
│  Unclear transactions → AI suggest options:                  │
│  "Chi Anh Tuấn 5tr" → Suggested:                           │
│    [1] Advances (Tạm ứng)                                   │
│    [2] Commission (Hoa hồng)                                 │
│    [3] Reimbursement (Bồi hoàn)                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

##### 🤖 Commission Calculator — Auto Month-End

```
  End of Month ──► AI Auto-Calculate
                     │
                     ▼
  ┌──────────────────────────────────────────────────────┐
  │  COMMISSION REPORT — Tháng 06/2026                   │
  ├──────────────────────────────────────────────────────┤
  │                                                      │
  │  Trần Thị Sales:                                     │
  │  • Design contracts: 2 deals × 150tr avg × 3%       │
  │    = 9 triệu                                        │
  │  • Construction: 1 deal × 300tr × 2%                │
  │    = 6 triệu                                        │
  │  • Leader override: 0.5% × 450tr = 2.25 triệu      │
  │  ─────────────────────────────────────              │
  │  TOTAL: 17.25 triệu                                 │
  │                                                      │
  │  Lê Văn Sales:                                       │
  │  • Design: 1 deal × 200tr × 3% = 6 triệu           │
  │  • Construction: 0                                  │
  │  ─────────────────────────────────────              │
  │  TOTAL: 6 triệu                                     │
  │                                                      │
  │  ── TOTAL TEAM ─────────────────────                │
  │  Total commission: 23.25 triệu                      │
  │  Status: ⏳ Pending approval                        │
  │                                                      │
  └──────────────────────────────────────────────────────┘
```

##### 🤖 Anomaly Detection

```
┌──────────────────────────────────────────────────────────────┐
│  ANOMALY DETECTION — AI scanning...                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ⚠ Alert 1: Budget Overrun                                   │
│  ──────────────────────────                                  │
│  Dự án: Biệt thự Thảo Điền                                  │
│  Estimated: 2.5 tỷ | Actual: 2.85 tỷ (+14%)                │
│  → Vượt ngân sách dự kiến 14%                               │
│                                                              │
│  ⚠ Alert 2: Duplicate Transaction                            │
│  ───────────────────────────────                             │
│  Ngày 25/06: "Chi vật tư Greenwood" × 2                    │
│  Amount: 15,000,000 VND × 2 = 30,000,000 VND              │
│  → Kiểm tra có phải nhập nhầm không?                        │
│                                                              │
│  ⚠ Alert 3: Unusual Cash Outflow                            │
│  ─────────────────────────────────                           │
│  Total chi tháng này: 783 triệu (bình thường: ~600 triệu)  │
│  → Chi phí cao hơn 30% so với trung bình 3 tháng           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

##### Workflow Kế toán hàng tháng

```
  ┌───────────────────────────────────────────────────┐
  │  MONTHLY ACCOUNTING WORKFLOW                       │
  ├───────────────────────────────────────────────────┤
  │                                                   │
  │  Day 1-25:                                        │
  │  ┌─────────────────────────────────────┐          │
  │  │ • AI auto-categorize transactions    │          │
  │  │ • Flag unclear items for review      │          │
  │  │ • Track project costs vs budget      │          │
  │  └─────────────────────────────────────┘          │
  │                                                   │
  │  Day 26-28:                                       │
  │  ┌─────────────────────────────────────┐          │
  │  │ • AI calculate commissions           │          │
  │  │ • Generate payroll draft             │          │
  │  │ • Generate tax report               │          │
  │  │ • Send for approval                  │          │
  │  └─────────────────────────────────────┘          │
  │                                                   │
  │  Day 29-30:                                       │
  │  ┌─────────────────────────────────────┐          │
  │  │ • Final review & approve             │          │
  │  │ • Pay commissions                    │          │
  │  │ • Update financial dashboard         │          │
  │  └─────────────────────────────────────┘          │
  │                                                   │
  └───────────────────────────────────────────────────┘
```

---

### 2.5 Designer (thiết kế)

#### AI Features

##### 🤖 Design Brief Generator

```
┌──────────────────────────────────────────────────────────────┐
│  DESIGN BRIEF GENERATOR                                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Input: Lead data + Notes từ cuộc khảo sát                   │
│                                                              │
│  Lead: Chị Mai — Nhà phố Q7, 180m²                         │
│  Notes: "Thích phong cách hiện đại, màu trắng + gỗ tự nhiên│
│          Cần 3 phòng ngủ, phòng làm việc, phòng trẻ em.     │
│          Ngân sách 500tr cho thiết kế + thi công."          │
│                                                              │
│  AI OUTPUT (Design Brief):                                   │
│  ┌──────────────────────────────────────────────────┐        │
│  │ PROJECT: Nhà phố Q7 — Chị Mai                   │        │
│  │ STYLE: Modern Minimalist                          │        │
│  │ PALETTE: White (#FFFFFF) + Natural Wood (#C19A6B)│        │
│  │                                                   │        │
│  │ ROOMS:                                           │        │
│  │ • Living Room + Kitchen (open plan)              │        │
│  │ • Master Bedroom + Ensuite                       │        │
│  │ • Bedroom 2 (Guest)                              │        │
│  │ • Bedroom 3 (Children)                           │        │
│  │ • Home Office                                    │        │
│  │ • 2 Bathrooms                                    │        │
│  │                                                   │        │
│  │ SPECIAL REQUESTS:                                 │        │
│  │ • Smart home integration                         │        │
│  │ • Child-safe materials                           │        │
│  │ • Energy-efficient lighting                      │        │
│  │                                                   │        │
│  │ BUDGET ALLOCATION (suggested):                   │        │
│  │ • Design fee: 50tr (10%)                         │        │
│  │ • Materials: 300tr (60%)                         │        │
│  │ • Labor: 120tr (24%)                             │        │
│  │ • Contingency: 30tr (6%)                         │        │
│  └──────────────────────────────────────────────────┘        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

##### 🤖 Material Calculator

```
  Room: Living Room 40m²
  ──────────────────────────────────────────────
  Material          │ Qty     │ Unit    │ Est. Cost
  ──────────────────┼─────────┼─────────┼──────────
  Sàn gỗ tự nhiên   │ 42 m²   │ m²      │ 21 tr
  Sơn nội thất      │ 120 m²  │ m²      │ 12 tr
  Trần thạch cao    │ 40 m²   │ m²      │ 8 tr
  Đèn LED           │ 12      │ cái     │ 3.6 tr
  Tủ kệ tivi        │ 1       │ bộ      │ 15 tr
  Sofa              │ 1       │ bộ      │ 25 tr
  ──────────────────┴─────────┴─────────┴──────────
  TOTAL (Living Room): 84.6 triệu
```

##### 🤖 Project Timeline Predictor

```
┌──────────────────────────────────────────────────────────────┐
│  PROJECT TIMELINE — Nhà phố Q7 (Chị Mai)                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Phase          │ Start     │ End       │ Status             │
│  ───────────────┼───────────┼───────────┼──────────────────  │
│  Khảo sát       │ 01/07     │ 02/07     │ ░░ Scheduled       │
│  Thiết kế SK   │ 03/07     │ 20/07     │ ░░ Scheduled       │
│  Presentation   │ 21/07     │ 21/07     │ ░░ Scheduled       │
│  Thi công thô   │ 25/07     │ 15/08     │ ░░ Scheduled       │
│  Hoàn thiện     │ 16/08     │ 10/09     │ ░░ Scheduled       │
│  Nghiệm thu     │ 11/09     │ 12/09     │ ░░ Scheduled       │
│  Bàn giao       │ 13/09     │ 13/09     │ ░░ Scheduled       │
│                                                              │
│  AI FORECAST: 42 ngày từ khảo sát đến bàn giao              │
│  Risk factors: Mùa mưa (+5 ngày potential)                   │
│                                                              │
│  ┌─甘特チャート──────────────────────────────────────┐        │
│  │ Jul:  ████████░░░░░░░░░░░░ DESIGN                 │        │
│  │ Aug:  ░░░░░░░░████████████ CONSTRUCTION           │        │
│  │ Sep:  ░░░░░░░░░░░░░░░░████ FINISH                │        │
│  └──────────────────────────────────────────────────┘        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. AI Automation Flows (n8n / Telegram)

### Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AI AUTOMATION OVERVIEW                              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐         │
│  │   Triggers    │ ──► │   n8n/       │ ──► │   Actions     │         │
│  │              │     │   Workflows   │     │              │         │
│  │ • New Lead   │     │              │     │ • Telegram   │         │
│  │ • Overdue    │     │ • Route      │     │ • Email      │         │
│  │ • Stage chg  │     │ • Transform  │     │ • DB update  │         │
│  │ • Contract   │     │ • Enrich     │     │ • AI calc    │         │
│  │ •验收        │     │ • Schedule   │     │ • Notify     │         │
│  └──────────────┘     └──────────────┘     └──────────────┘         │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Flow 1: New Lead → Telegram → Auto-assign

```
  ┌──────────────────────────────────────────────────────────────┐
  │  FLOW 1: NEW LEAD INTAKE                                     │
  ├──────────────────────────────────────────────────────────────┤
  │                                                              │
  │  Zalo/FB ──► User pastes text ──► AI Parse                   │
  │                                          │                    │
  │                                          ▼                    │
  │                              ┌──────────────────────┐        │
  │                              │  POST /leads (create)│        │
  │                              │  + AI score          │        │
  │                              └──────────┬───────────┘        │
  │                                         │                     │
  │                    ┌────────────────────┴──────────┐         │
  │                    ▼                                ▼         │
  │           ┌─────────────────┐             ┌──────────────┐  │
  │           │ TELEGRAM NOTIFY │             │ AUTO-ASSIGN  │  │
  │           │                 │             │              │  │
  │           │ 🔔 Lead mới từ │             │ AI suggest   │  │
  │           │ Zalo: Chị Mai  │             │ best sales   │  │
  │           │ Score: 72/100  │             │ for this     │  │
  │           │ Link: /leads/xx│             │ lead type    │  │
  │           └─────────────────┘             └──────────────┘  │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘
```

### Flow 2: Lead Overdue → Reminder → Escalate

```
  ┌──────────────────────────────────────────────────────────────┐
  │  FLOW 2: OVERDUE LEAD MANAGEMENT                             │
  ├──────────────────────────────────────────────────────────────┤
  │                                                              │
  │  Cron: Daily @ 9:00 AM                                       │
  │                                                              │
  │  ┌────────────────────────────────────────┐                  │
  │  │ SCAN: leads where                      │                  │
  │  │   last_contacted > 3 days              │                  │
  │  │   AND stage NOT IN [signed, lost]      │                  │
  │  └──────────────────┬─────────────────────┘                  │
  │                     │                                        │
  │                     ▼                                        │
  │           ┌──────────────────┐                               │
  │           │  DAY 3: Reminder  │                               │
  │           │  → Telegram to    │                               │
  │           │    assigned sales │                               │
  │           └────────┬─────────┘                               │
  │                    │                                         │
  │              Still overdue?                                  │
  │              ┌─────┴──────┐                                  │
  │              Yes          No ──► STOP                        │
  │              │                                                  │
  │              ▼                                                  │
  │  ┌──────────────────────┐                                     │
  │  │  DAY 5: Escalate     │                                     │
  │  │  → Telegram to Leader │                                     │
  │  │  → "Trần có 3 leads  │                                     │
  │  │     quá hạn 5+ ngày" │                                     │
  │  └──────────┬───────────┘                                     │
  │             │                                                  │
  │        Still overdue?                                         │
  │        ┌─────┴──────┐                                         │
  │        Yes          No ──► STOP                               │
  │        │                                                      │
  │        ▼                                                      │
  │  ┌──────────────────────┐                                     │
  │  │  DAY 7: Admin Alert  │                                     │
  │  │  → Telegram to Admin  │                                     │
  │  │  → "Lead risk dormant │                                     │
  │  │     cần quyết định"   │                                     │
  │  └──────────────────────┘                                     │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘
```

### Flow 3: Ký hợp đồng → Auto-create Project

```
  ┌──────────────────────────────────────────────────────────────┐
  │  FLOW 3: CONTRACT SIGNED → PROJECT CREATION                  │
  ├──────────────────────────────────────────────────────────────┤
  │                                                              │
  │  Lead stage ──► signed_design                                │
  │                     │                                        │
  │                     ▼                                        │
  │  ┌──────────────────────────────────────────┐                │
  │  │  AUTO-ACTIONS:                            │                │
  │  │                                           │                │
  │  │  1. Create Project record                 │                │
  │  │     → project.name = lead.name + address  │                │
  │  │     → project.budget = contract value     │                │
  │  │     → project.start_date = today + 7      │                │
  │  │                                           │                │
  │  │  2. Calculate payment milestones          │                │
  │  │     → Milestone 1: 50% (signing)          │                │
  │  │     → Milestone 2: 30% (rough complete)   │                │
  │  │     → Milestone 3: 20% (handover)         │                │
  │  │                                           │                │
  │  │  3. Create design timeline                │                │
  │  │     → Based on property type & area       │                │
  │  │                                           │                │
  │  │  4. Notify designer team                  │                │
  │  │     → Telegram: "New project assigned"    │                │
  │  │     → Include: client info, brief, scope  │                │
  │  │                                           │                │
  │  │  5. Notify accountant                     │                │
  │  │     → "Contract signed, commission ready" │                │
  │  │                                           │                │
  │  └──────────────────────────────────────────┘                │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘
```

### Flow 4: Nghiệm thu → Commission → Notify

```
  ┌──────────────────────────────────────────────────────────────┐
  │  FLOW 4: HANDOVER → COMMISSION CALCULATION                   │
  ├──────────────────────────────────────────────────────────────┤
  │                                                              │
  │  Project stage ──► "completed"                               │
  │                         │                                    │
  │                         ▼                                    │
  │  ┌──────────────────────────────────────────┐                │
  │  │  AUTO-ACTIONS:                            │                │
  │  │                                           │                │
  │  │  1. AI calculates final commission        │                │
  │  │     → Design: 3% × design_contract_value  │                │
  │  │     → Construction: 2% × construction_val │                │
  │  │     → Leader override: 0.5%               │                │
  │  │                                           │                │
  │  │  2. Create commission record              │                │
  │  │     → status = "pending_approval"         │                │
  │  │                                           │                │
  │  │  3. Notify accountant                     │                │
  │  │     → Telegram: "New commission pending"  │                │
  │  │     → Amount + sales name + deal details  │                │
  │  │                                           │                │
  │  │  4. Notify sales                          │                │
  │  │     → "Chúc mừng! Bạn đã nhận hoa hồng   │                │
  │  │        X triệu từ dự án Y"                │                │
  │  │                                           │                │
  │  │  5. Update dashboard                      │                │
  │  │     → Revenue += final payment            │                │
  │  │     → Mark project as completed           │                │
  │  │                                           │                │
  │  └──────────────────────────────────────────┘                │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘
```

### Flow 5: Daily Briefing → Telegram

```
  ┌──────────────────────────────────────────────────────────────┐
  │  FLOW 5: DAILY BRIEFING                                      │
  ├──────────────────────────────────────────────────────────────┤
  │                                                              │
  │  Cron: Daily @ 08:00 AM (Asia/Ho_Chi_Minh)                   │
  │                                                              │
  │  ┌──────────────────────────────────────┐                    │
  │  │  COLLECT DATA                         │                    │
  │  │                                       │                    │
  │  │  • New leads today                    │                    │
  │  │  • Overdue leads count                │                    │
  │  │  • Pipeline total value               │                    │
  │  │  • Active projects status             │                    │
  │  │  • Revenue vs target                  │                    │
  │  │  • Commission pending                 │                    │
  │  │  • Risk alerts                        │                    │
  │  └──────────────┬───────────────────────┘                    │
  │                 │                                             │
  │                 ▼                                             │
  │  ┌──────────────────────────────────────┐                    │
  │  │  FORMAT MESSAGE (AI)                  │                    │
  │  │                                       │                    │
  │  │  📊 JAMA HOME Daily Briefing          │                    │
  │  │  ── {date} ──                         │                    │
  │  │  • Summary of all metrics             │                    │
  │  │  • Highlight risks                    │                    │
  │  │  • Suggest priorities                 │                    │
  │  └──────────────┬───────────────────────┘                    │
  │                 │                                             │
  │                 ▼                                             │
  │  ┌──────────────────────────────────────┐                    │
  │  │  SEND VIA TELEGRAM BOT                │                    │
  │  │                                       │                    │
  │  │  • Admin group: Full briefing         │                    │
  │  │  • Leader group: Team-specific data   │                    │
  │  │  • Sales individual: Personal KPIs    │                    │
  │  └──────────────────────────────────────┘                    │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘
```

---

## 4. Technical Implementation

### 4.1 Thêm AI Agent mới

```
┌──────────────────────────────────────────────────────────────────────┐
│  HOW TO ADD A NEW AI AGENT                                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Step 1: Create agent file                                           │
│  ─────────────────────────                                           │
│                                                                      │
│  backend/app/agents/new_agent.py                                     │
│                                                                      │
│  Step 2: Create API endpoint                                         │
│  ──────────────────────────                                          │
│                                                                      │
│  backend/app/api/new_agent.py                                        │
│                                                                      │
│  Step 3: Register router in main.py                                  │
│  ──────────────────────────────────                                  │
│                                                                      │
│  Step 4: Add frontend UI                                             │
│  ───────────────────────                                             │
│                                                                      │
│  frontend/src/app/.../page.tsx                                        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Template cho AI Agent mới:**

```python
# backend/app/agents/my_new_agent.py
"""My New AI Agent — Description of what it does."""

import json
from litellm import acompletion
from app.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = """Bạn là AI agent của JAMA HOME.
Nhiệm vụ: [Mô tả cụ thể]

Trả về JSON với các trường: [...]
"""

async def run_agent(input_data: str) -> dict:
    """Run AI agent with input data."""
    try:
        response = await acompletion(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": input_data},
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception:
        # Fallback to rule-based
        return _rule_based_fallback(input_data)


def _rule_based_fallback(input_data: str) -> dict:
    """Rule-based fallback when LLM is unavailable."""
    # Implement regex/keyword-based logic here
    return {"result": "fallback result"}
```

**API endpoint template:**

```python
# backend/app/api/my_new_agent.py
"""API for my new AI agent."""

from fastapi import APIRouter, Depends, Query
from app.middleware.auth import get_current_user
from app.models.user import User
from app.agents.my_new_agent import run_agent

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/my-new-agent")
async def my_new_agent_endpoint(
    data: dict,
    current_user: User = Depends(get_current_user),
):
    """Endpoint for my new AI agent."""
    result = await run_agent(data.get("input", ""))
    return result
```

### 4.2 Kết nối n8n Workflows

```yaml
# n8n Webhook Integration

# Workflow: New Lead Notification
Webhook (POST /webhook/new-lead)
  └─► Transform Data
  └─► Telegram Bot: Send Message
        chat_id: -100xxxxxxxxxx
        text: "🔔 New lead: {{name}} (Score: {{score}})"

# Workflow: Overdue Check (Scheduled)
Cron (Daily 9:00 AM)
  └─► HTTP Request: GET /api/leads/overdue
  └─► Loop: For each overdue lead
      └─► Telegram Bot: Send Reminder
            chat_id: {{assigned_sales.telegram_id}}
            text: "⚠️ Lead {{name}} overdue {{days}} days"

# Workflow: Daily Briefing
Cron (Daily 8:00 AM)
  └─► HTTP Request: GET /api/dashboard/summary
  └─► AI Transform (GPT): Format briefing
  └─► Telegram Bot: Send to Admin Group
```

### 4.3 Expose Tools to MCP / AI Agents

```json
// MCP Server Configuration
// File: backend/app/mcp/server.py

{
  "tools": [
    {
      "name": "parse_lead",
      "description": "Parse raw text into structured lead data",
      "endpoint": "POST /ai/parse-lead",
      "input_schema": {
        "text": "string — raw text from Zalo/Facebook"
      }
    },
    {
      "name": "suggest_action",
      "description": "Get AI suggestion for next action on a lead",
      "endpoint": "POST /ai/suggest-action",
      "input_schema": {
        "lead_id": "string — UUID of the lead"
      }
    },
    {
      "name": "score_lead",
      "description": "Score a lead 0-100",
      "endpoint": "POST /ai/score-lead",
      "input_schema": {
        "lead_id": "string — UUID of the lead"
      }
    }
  ]
}
```

### 4.4 Environment Variables

```bash
# .env — JAMA HOME CRM Configuration

# ─── LLM Configuration ─────────────────────────────
LLM_PROVIDER=groq
LLM_MODEL=groq/llama-3.3-70b-versatile
LLM_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_FALLBACK_RULES=true
LLM_TIMEOUT=30
LLM_MAX_RETRIES=3

# ─── App ────────────────────────────────────────────
APP_NAME="JAMA HOME CRM"
APP_ENV=development
DEBUG=true
DATABASE_URL=sqlite+aiosqlite:///./jama.db

# ─── Telegram Bot ───────────────────────────────────
TELEGRAM_BOT_TOKEN=7000000000:XXXXXXXXXXXXXXXXXXXXX
TELEGRAM_ADMIN_CHAT_ID=-1001234567890
TELEGRAM_LEADER_CHAT_ID=-1001234567891
TELEGRAM_SALES_CHAT_ID=-1001234567892

# ─── n8n ────────────────────────────────────────────
N8N_WEBHOOK_URL=http://localhost:5678/webhook
N8N_API_KEY=n8n_xxxxxxxxxxxxxxxx

# ─── Auth ───────────────────────────────────────────
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

### 4.5 File Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── ai.py                    ← AI endpoints (rule-based)
│   │   ├── leads.py                 ← Lead CRUD
│   │   ├── dashboard.py             ← Dashboard API
│   │   ├── accounting.py            ← Financial endpoints
│   │   └── ...
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── lead_intake.py           ← LLM-based lead parsing
│   │   ├── sales_copilot.py         ← LLM-based action suggestion
│   │   └── [new_agent].py           ← ← Add new agents here
│   ├── models/
│   │   ├── lead.py                  ← Lead + Activity models
│   │   ├── project.py               ← Project model
│   │   ├── contract.py              ← Contract model
│   │   └── ...
│   ├── config.py                    ← Settings (LLM_MODEL, etc.)
│   ├── database.py                  ← SQLite connection
│   └── main.py                      ← FastAPI app
│
├── .env                             ← Environment variables
└── jama.db                          ← SQLite database
```

---

## 5. AI Enhancements — Tương lai

### Roadmap

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AI ROADMAP — JAMA HOME                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  PHASE 1 — Đang hoạt động ✅                                        │
│  ────────────────────────────                                        │
│  ✅ Lead Intake Agent (parse Zalo → structured data)                 │
│  ✅ Sales Co-Pilot Agent (suggest next actions)                      │
│  ✅ Lead Scoring (0-100 rule-based)                                  │
│  ✅ Rule-based fallback (always available)                           │
│  ✅ Telegram notifications (daily briefing)                          │
│                                                                      │
│  PHASE 2 — Q3/2026 🔨                                               │
│  ────────────────────                                                │
│  🔨 Sentiment Analysis on customer messages                          │
│     → Detect: positive/negative/neutral sentiment                    │
│     → Alert: if negative sentiment → escalate to leader              │
│     → Track: sentiment trend over time                               │
│                                                                      │
│  🔨 Auto-response Templates for common inquiries                     │
│     → "Bao nhiêu tiền?" → Auto reply with pricing guide              │
│     → "Có mẫu nào không?" → Auto share portfolio images              │
│     → "Schedule survey" → Auto propose 3 time slots                  │
│                                                                      │
│  🔨 Smart Lead Assignment (ML-based)                                 │
│     → Predict best sales match based on:                             │
│       • Lead property type + sales specialty                         │
│       • Lead budget + sales average deal size                        │
│       • Lead source + sales conversion rate by source                │
│                                                                      │
│  PHASE 3 — Q4/2026 📋                                               │
│  ────────────────────                                                │
│  📋 Predictive Analytics for Lead Conversion                         │
│     → ML model trained on historical pipeline data                   │
│     → Predict: probability of conversion × expected revenue          │
│     → Optimize: which leads to focus on                              │
│                                                                      │
│  📋 Computer Vision for Interior Design                               │
│     → Moodboard analysis: extract style, colors, materials           │
│     → Auto-generate design brief from inspiration images             │
│     → Style matching: "Find similar projects in portfolio"           │
│                                                                      │
│  📋 Voice AI for Phone Calls                                         │
│     → Real-time transcription of sales calls                         │
│     → Auto-generate call summary + action items                      │
│     → Sentiment analysis on customer voice                           │
│                                                                      │
│  PHASE 4 — 2027 🚀                                                   │
│  ──────────────────                                                  │
│  🚀 Full Autonomous AI Agent                                         │
│     → Handle initial lead conversations                              │
│     → Schedule meetings automatically                                │
│     → Generate preliminary quotations                                │
│     → Human-in-the-loop for final decisions                          │
│                                                                      │
│  🚀 Multi-modal AI                                                   │
│     → Analyze floor plans from photos                                │
│     → Suggest furniture placement                                    │
│     → Estimate material quantities from images                       │
│                                                                      │
│  🚀 Natural Language Database Queries                                │
│     → "Show me all leads with budget > 1 tỷ"                        │
│     → "How many deals did Trần close this month?"                   │
│     → "What's the average deal size by source?"                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Sentiment Analysis — Preview

```python
# Future: backend/app/agents/sentiment_analyzer.py

"""
Input: Customer message text
Output: Sentiment + confidence + suggested action

Example:
  "Tôi không hài lòng với thiết kế này" 
  → sentiment: negative (0.92)
  → action: "Escalate to leader immediately"
  
  "Cảm ơn bạn, thiết kế rất đẹp"
  → sentiment: positive (0.88)
  → action: "Send thank you + request testimonial"
"""
```

### Auto-Response Templates — Preview

```
┌──────────────────────────────────────────────────────────────┐
│  AUTO-RESPONSE CATEGORIES                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Category: Pricing Inquiry                                   │
│  ─────────────────────────                                   │
│  "Bao nhiêu tiền?" / "Giá cả thế nào?"                     │
│  → Auto-reply: Pricing guide PDF + link to portfolio         │
│  → Follow-up: "Để em tư vấn chi tiết, anh/chị cho em      │
│    biết diện tích nhà và phong cách yêu thích nhé?"         │
│                                                              │
│  Category: Portfolio Request                                 │
│  ──────────────────────────                                  │
│  "Có mẫu nào không?" / "Xem hình ảnh"                      │
│  → Auto-reply: Top 5 relevant projects (by property type)    │
│  → Follow-up: "Anh/chị thích phong cách nào nhất?"         │
│                                                              │
│  Category: Schedule Request                                  │
│  ──────────────────────────                                  │
│  "Hẹn lịch khảo sát" / "Khi nào qua được?"                 │
│  → Auto-reply: 3 available time slots (next 7 days)          │
│  → Follow-up: "Anh/chị chọn slot nào phù hợp nhất ạ?"     │
│                                                              │
│  Category: Complaint                                         │
│  ─────────────────                                           │
│  "Không hài lòng" / "Sai sót" / "Khiếu nại"               │
│  → Flag: sentiment = negative                                │
│  → Escalate: Notify leader immediately                       │
│  → Auto-reply: "Em rất xin lỗi, em sẽ báo lại quản lý     │
│    để xử lý sớm nhất ạ."                                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Appendix: Quick Reference

### AI Endpoints

| Endpoint | Method | Mô tả | File |
|---|---|---|---|
| `/api/ai/parse-lead` | POST | Parse text → Lead data | `api/ai.py` |
| `/api/ai/suggest-action` | POST | Gợi ý hành động tiếp theo | `api/ai.py` |
| `/api/ai/score-lead` | POST | Chấm điểm lead 0-100 | `api/ai.py` |

### Pipeline Stages

| Stage | Vietnamese | AI Action |
|---|---|---|
| `new` | Mới tiếp nhận | → Gọi điện tư vấn |
| `interested` | Có nhu cầu | → Hẹn khảo sát |
| `survey_scheduled` | Đã hẹn khảo sát | → Chuẩn bị hồ sơ |
| `potential` | KH tiềm năng | → Gửi báo giá |
| `signed_design` | Đã ký thiết kế | → Theo dõi dự án |
| `lost` | Mất lead | → Archive |
| `dormant` | Tạm ngừng | → Re-activate check |

### Commission Rules

| Type | Sales | Leader Override |
|---|---|---|
| Design contract | 3% | 0.5% |
| Construction | 2% | 0.5% |

### Payment Milestones

| Milestone | Percentage |
|---|---|
| Ký hợp đồng | 50% |
| Hoàn thành thô | 30% |
| Bàn giao | 20% |

### Key Contacts

| Role | Access Level | AI Features |
|---|---|---|
| `data_entry` | CRUD leads, view projects | Lead Intake, Co-Pilot, Scoring |
| `leader` | Team management, all leads | Team Analytics, Forecasting, Commission |
| `admin` | Full access | Executive Dashboard, Telegram Briefing, Risk |
| `accountant` | Financial data | Transaction Categorizer, Commission Calc |
| `designer` | Projects assigned | Timeline, Material Calculator, Brief Gen |

---

> **JAMA HOME CRM** — AI-Powered Interior Design Management System
> Built with ❤️ using Next.js + FastAPI + Groq AI + Telegram Bot
