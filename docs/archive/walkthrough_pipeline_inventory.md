# Walkthrough: Project Pipeline & Inventory Access Control

We have successfully implemented and verified the **Project Pipeline** and **Inventory Access Control** features, resolving the requests to manage complex operations with Kanban view, notes/media attachments, and restricted visibility for inventory.

---

## 1. Project Operational Pipeline 📊

### 1.1 Kanban Pipeline View
- **What was added:** A pipeline view to track projects across 6 stages (`design`, `quotation`, `procurement`, `construction`, `acceptance`, `completed`).
- **Toggle Mode:** Easily switch between **📊 Pipeline Kanban** and **📋 Danh sách** at the top of the Projects page.
- **Stage Progression:** Admin/Purchasing and relevant roles can change a project's stage directly via a dropdown in the Project Details modal.

---

### 1.2 Stage-Grouped Tasks
- **What was added:** In the Project Details modal, all 19 standard tasks are grouped by their operational stages (**Thiết kế**, **Báo giá**, **Thu mua**, **Thi công**, **Nghiệm thu**), making progress tracking incredibly organized instead of a giant unorganized list.

---

### 1.3 Task updates & Notes Timeline (Chronological Notes + Media)
- **What was added:** Clicking on any task opens a **Task Detail Modal** equipped with:
  - **Status Selector:** Transition tasks among ` todo` (Chờ), `in_progress` (Đang làm), and `done` (Hoàn thành).
  - **Ghi chú & Media Form:** Add text updates and attach media (either pasting image URLs or uploading files via a file picker which automatically converts the image to a base64 string).
  - **Activity Timeline:** Shows the complete, chronological list of notes + attachments made by team members.
  - **Final Stage File (File kết quả chốt):** A dedicated field to save files like final quote, technical drawings, or final acceptance certificate. This ensures direct audit trails for documents during the project.

---

### 1.4 Auto-Conversion on Design Signed
- **Auto Hook:** When a CRM Lead's status changes to `signed_design` (Đã ký hợp đồng thiết kế), the backend automatically:
  1. Creates a **Customer** from the lead.
  2. Creates a **Project** in the pipeline.
  3. Seeds **19 standard tasks** aligned to the operational blueprint.

---

## 2. Inventory Access Control (Kho vật tư) 🔒

- **Restriction Rule:** Only users with `admin` (Giám đốc) and the new `purchasing` (Nhân viên Thu mua) roles can access the inventory page.
- **Access Check:**
  - **Backend:** Added security dependency `verify_inventory_access` checking roles and departments to block API requests for other roles with HTTP 403 Forbidden.
  - **Frontend:** Modified role definitions mapping (`ROLE_PERMISSIONS.purchasing`). `leader` and `accountant` now have `canViewInventory: false` which automatically hides the "Kho vật tư" link from the sidebar layout.

---

## 3. Verification & Deployment 🚀

- **Type safety:** Run `npm run build` locally in the frontend, resulting in a successful build without any compiler warnings/errors.
- **Deployment:** Successfully pushed to production branch (`main -> origin/main`). Live health check is active and OK.
- **Production URL:** `https://jamacrm-production.up.railway.app/health`

---

## 4. New Seed Accounts
- **Purchasing User:** `purchasing@jamahome.vn` / password: `purchase123` (role: `purchasing`).
