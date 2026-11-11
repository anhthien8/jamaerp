<!-- BEGIN:nextjs-agent-rules -->
# Next.js 16 (App Router, Turbopack)

Bản Next này mới hơn dữ liệu huấn luyện của nhiều model. Chỉ khi đụng tới routing, config
(`next.config.*`), middleware/proxy, caching hay data fetching, đọc đúng mục liên quan trong
`node_modules/next/dist/docs/` (cần `npm install` trước). Sửa component/trang thông thường thì
không cần đọc — làm theo code sẵn có trong `src/`.
<!-- END:nextjs-agent-rules -->

## Quy ước giao diện JAMA
- Chữ tiếng Việt có dấu; icon nét qua `LineIcon`, không dùng emoji trên giao diện.
- Nhãn giai đoạn lead lấy từ `STAGE_CONFIG` (`src/lib/utils.ts`), khớp `STAGE_LABELS` ở backend.
- Kiểm tra trước khi xong: `npm run lint` (file đã sửa) và `npm run build`.
