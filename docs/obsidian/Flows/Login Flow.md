# Flow: Authentication (Quy trình Đăng nhập)

## Web Login Flow

```mermaid
sequenceDiagram
    autonumber
    participant U as User (Browser)
    participant FE as Frontend (Next.js)
    participant BE as Backend (FastAPI)
    participant DB as Database

    U->>FE: Truy cập /login
    FE->>FE: Hiển thị form đăng nhập

    U->>FE: Nhập email + password
    FE->>BE: POST /auth/login<br/>{email, password}

    BE->>BE: Rate limit check<br/>(5 attempts/60s per IP)
    alt Rate limited
        BE-->>FE: 429 Too Many Requests
        FE-->>U: Thông báo thử lại sau
    end

    BE->>DB: SELECT user WHERE email = ?
    DB-->>BE: User record

    alt User không tồn tại
        BE-->>FE: 401 "Email hoặc mật khẩu không đúng"
    end

    BE->>BE: verify_password(plain, hash)
    alt Password sai
        BE-->>FE: 401 "Email hoặc mật khẩu không đúng"
    end

    alt User bị vô hiệu hóa
        BE-->>FE: 403 "Tài khoản đã bị vô hiệu hóa"
    end

    BE->>BE: create_access_token(user_id, role, department)
    Note over BE: JWT payload:<br/>{sub: user_id,<br/>role: role,<br/>dept: department,<br/>exp: expiry}

    BE-->>FE: 200 {access_token, user}
    FE->>FE: Lưu token vào cookie/localStorage
    FE->>FE: Redirect to dashboard
    FE-->>U: Hiển thị trang chính
```

## Telegram Bot Auth Flow

```mermaid
sequenceDiagram
    autonumber
    participant TG as Telegram User
    participant Bot as Telegram Bot
    participant BE as Backend (FastAPI)
    participant DB as Database

    TG->>Bot: Gửi lệnh /start
    Bot->>Bot: Lấy telegram_user_id

    Bot->>BE: POST /auth/telegram<br/>{telegram_user_id, telegram_username}
    Note over Bot,BE: Header: X-Telegram-Bot-Secret<br/>(HMAC shared secret)

    BE->>BE: Verify HMAC secret
    alt Secret không khớp
        BE-->>Bot: 401 Unauthorized
    end

    BE->>BE: Rate limit check<br/>(10 attempts/60s per TG ID)

    BE->>DB: SELECT user WHERE telegram_user_id = ?
    DB-->>BE: User record

    alt Telegram chưa liên kết
        BE-->>Bot: 404 "Telegram chưa liên kết với CRM"
        Bot-->>TG: "Liên hệ Admin để liên kết tài khoản"
    end

    alt User bị vô hiệu hóa
        BE-->>Bot: 403 "Tài khoản đã bị vô hiệu hóa"
    end

    BE->>BE: Update telegram_username (nếu thay đổi)
    BE->>BE: create_access_token(user_id, role, department)

    BE-->>Bot: 200 {access_token, user}
    Bot-->>TG: Chào mừng! Đăng nhập thành công.
```

## JWT Token Structure

```mermaid
graph LR
    subgraph JWT["JWT Access Token"]
        Payload["Payload"]
        Payload --> Sub["sub: user_id (UUID)"]
        Payload --> Role["role: admin|leader|..."]
        Payload --> Dept["dept: EXEC|SALES|..."]
        Payload --> Exp["exp: expiry timestamp"]
    end
```

## Rate Limiting

```mermaid
flowchart TD
    A["Request đến"] --> B{"Tính bucket key"}

    B -->|"Web login"| C["login:{client_ip}"]
    B -->|"Telegram auth"| D["tg:{telegram_user_id}"]

    C --> E{"Count trong<br/>60s window"}
    D --> E

    E -->|"< 5 (web) / < 10 (TG)"| F["CHO PHÉP"]
    E -->|">= limit"| G["429 Too Many Requests"]

    F --> H["Thêm timestamp vào bucket"]
    G --> I["Chờ window reset"]
```

## Middleware Chain

```mermaid
flowchart LR
    A["HTTP Request"] --> B["CORS Middleware"]
    B --> C["Rate Limiter (login only)"]
    C --> D["JWT Auth Middleware"]
    D --> E["Role Check"]
    E --> F["Route Handler"]
```

## Security Features

| Feature | Implementation |
|---------|---------------|
| Password hashing | bcrypt |
| Token format | JWT with role + department claims |
| Rate limiting | In-memory, per-IP (web), per-TG-ID (bot) |
| Telegram auth | HMAC shared secret verification |
| Timing attack prevention | `hmac.compare_digest()` for secret comparison |
| Account deactivation | `is_active` check before token issuance |
| Error messages | Generic "email hoặc mật khẩu không đúng" (no enumeration) |

## Frontend Auth State

```mermaid
stateDiagram-v2
    [*] --> loading: Page load

    loading --> authenticated: Token valid
    loading --> login: No token / expired

    login --> authenticated: Login success
    authenticated --> login: Token expired / logout

    authenticated --> dashboard: role = admin/executive
    authenticated --> leads: role = data_entry/leader
    authenticated --> projects: role = pm
    authenticated --> finance: role = accountant
    authenticated --> inventory: role = purchasing
    authenticated --> tasks: role = designer
```

## Tags

#flow #auth #login #security #jwt #telegram #jama-home
