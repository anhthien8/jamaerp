/**
 * JAMA HOME -- Zalo Listener Ingest Service (spec 09, hoan thien 23/10/2026)
 * =========================================================================
 * LISTEN-ONLY. Chay TACH khoi backend ERP (lib Zalo hay vo -> khong keo sap he thong).
 *
 * Vong doi:
 *  1. Khoi dong: hoi backend phien da luu (ma hoa) -> zalo.login(creds), khoi quet QR.
 *  2. Khong co phien / phien het han: cho admin bam "Dang nhap" tren web
 *     (poll GET /zalo/ingest/pending-login, kiem luon heartbeat) -> loginQR,
 *     day QR ve web; quet xong -> luu phien ve backend.
 *  3. Dang nhap xong: dong bo danh sach nhom (ten + so thanh vien) -> backend;
 *     lang nghe tin nhom -> POST /zalo/ingest/message (chi text + metadata).
 *  4. Admin bam "Dang xuat" tren web -> backend status logged_out -> ngat listener.
 *  5. Bi Zalo day ra (dang nhap noi khac, 3000/3003) -> bao loi + xoa phien.
 *
 * KHONG BAO GIO gui tin vao Zalo. Dung tai khoan Zalo phu chuyen dung
 * (thu vien khong chinh thuc -> tai khoan co nguy co bi khoa).
 */

import { Zalo, ThreadType, LoginQRCallbackEventType } from "zca-js";
import { config } from "./config.js";
import { logger } from "./logger.js";
import {
  reportSession,
  pushMessage,
  pollPendingLogin,
  getSavedCredentials,
  saveCredentials,
  clearCredentials,
  syncGroups,
} from "./backend-client.js";

// -------------------------------------------------------------------
// State
// -------------------------------------------------------------------

let zaloApi = null;          // API instance sau khi dang nhap
let loggedIn = false;
let loginInProgress = false;

/** zalo_group_id -> ten nhom */
const groupNameCache = new Map();

const QR_MAX_RETRY = 3;      // QR het han tu lam moi toi da 3 lan (~3 phut)
const GROUP_SYNC_MS = 6 * 60 * 60 * 1000; // dong bo lai ten nhom moi 6 gio

// -------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------

function toDataUri(base64) {
  if (!base64) return null;
  if (base64.startsWith("data:")) return base64;
  return `data:image/png;base64,${base64}`;
}

/** content co the la chuoi (tin chu) hoac object dinh kem {title, href, ...}. */
function extractText(content) {
  if (typeof content === "string") return content;
  if (content && typeof content === "object") {
    const parts = [content.title, content.description].filter((x) => typeof x === "string" && x);
    return parts.join(" — ");
  }
  return "";
}

function extractMediaRef(content) {
  if (content && typeof content === "object" && typeof content.href === "string") {
    return content.href.slice(0, 500);
  }
  return null;
}

function resolveGroupName(zaloGroupId) {
  return groupNameCache.get(zaloGroupId) || `Nhom ${zaloGroupId.slice(0, 8)}`;
}

// -------------------------------------------------------------------
// Sau dang nhap: ten tai khoan + dong bo nhom
// -------------------------------------------------------------------

async function accountName(api) {
  try {
    const info = await api.fetchAccountInfo();
    const p = info?.profile || {};
    return p.displayName || p.zaloName || p.username || "Tài khoản Zalo";
  } catch (err) {
    logger.warn("fetchAccountInfo failed", { error: err.message });
    return "Tài khoản Zalo";
  }
}

async function syncAllGroups() {
  if (!zaloApi) return;
  try {
    const all = await zaloApi.getAllGroups();
    const ids = Object.keys(all?.gridVerMap || {});
    const groups = [];
    for (let i = 0; i < ids.length; i += 50) {
      const batch = ids.slice(i, i + 50);
      try {
        const info = await zaloApi.getGroupInfo(batch);
        for (const [id, g] of Object.entries(info?.gridInfoMap || {})) {
          const name = String(g?.name || "").slice(0, 200) || `Nhom ${id.slice(0, 8)}`;
          groupNameCache.set(id, name);
          groups.push({
            zalo_group_id: id,
            name,
            member_count: Number.isFinite(g?.totalMember) ? g.totalMember : null,
          });
        }
      } catch (err) {
        logger.warn("getGroupInfo batch failed", { error: err.message });
      }
    }
    if (groups.length) {
      const res = await syncGroups(groups);
      logger.info("Groups synced", { total: groups.length, created: res?.created ?? "?" });
    }
  } catch (err) {
    logger.warn("syncAllGroups failed", { error: err.message });
  }
}

async function afterLogin(api) {
  zaloApi = api;
  loggedIn = true;
  const name = await accountName(api);
  await reportSession({ status: "logged_in", account_name: name });
  logger.info("Logged in as %s. Syncing groups + starting listener...", name);
  startListening();
  syncAllGroups(); // khong chan listener
}

function dropSession() {
  try {
    zaloApi?.listener?.stop();
  } catch {
    /* ignore */
  }
  zaloApi = null;
  loggedIn = false;
}

// -------------------------------------------------------------------
// Dang nhap
// -------------------------------------------------------------------

/** Dung phien da luu (cookie + imei) -> khong can quet QR sau moi lan Railway restart. */
async function loginWithSaved() {
  const creds = await getSavedCredentials();
  if (!creds) return false;
  loginInProgress = true;
  try {
    const zalo = new Zalo({ selfListen: false });
    const api = await zalo.login(creds);
    await afterLogin(api);
    return true;
  } catch (err) {
    logger.warn("Saved session rejected -- need new QR", { error: err.message });
    await clearCredentials();
    await reportSession({
      status: "error",
      error_msg: "Phiên Zalo đã hết hạn — bấm «Đăng nhập Zalo» để quét QR lại",
    });
    return false;
  } finally {
    loginInProgress = false;
  }
}

async function loginWithQR() {
  if (loginInProgress) return;
  loginInProgress = true;
  logger.info("Starting Zalo QR login flow...");
  await reportSession({ status: "awaiting_qr" });

  let retries = 0;
  try {
    const zalo = new Zalo({ selfListen: false });
    const api = await zalo.loginQR({ userAgent: "" }, async (event) => {
      try {
        switch (event.type) {
          case LoginQRCallbackEventType.QRCodeGenerated:
            await reportSession({ status: "qr_ready", qr_image: toDataUri(event.data?.image) });
            logger.info("QR code pushed to backend.");
            break;
          case LoginQRCallbackEventType.QRCodeExpired:
            if (retries < QR_MAX_RETRY) {
              retries += 1;
              logger.info("QR expired, refreshing (%d/%d)", retries, QR_MAX_RETRY);
              event.actions?.retry?.();
            } else {
              await reportSession({
                status: "error",
                error_msg: "Mã QR hết hạn — bấm «Đăng nhập Zalo» để lấy mã mới",
              });
              event.actions?.abort?.();
            }
            break;
          case LoginQRCallbackEventType.QRCodeScanned:
            logger.info("QR scanned by %s", event.data?.display_name || "unknown");
            await reportSession({ status: "qr_ready", qr_image: null });
            break;
          case LoginQRCallbackEventType.QRCodeDeclined:
            await reportSession({ status: "error", error_msg: "Đã từ chối đăng nhập trên điện thoại" });
            break;
          case LoginQRCallbackEventType.GotLoginInfo:
            // Luu phien (backend ma hoa) de lan sau khoi quet QR
            await saveCredentials({
              cookie: event.data?.cookie,
              imei: event.data?.imei,
              user_agent: event.data?.userAgent,
            });
            logger.info("Login session saved to backend.");
            break;
          default:
            break;
        }
      } catch (e) {
        logger.warn("Error in loginQR callback", { error: e.message });
      }
    });

    if (!api) throw new Error("loginQR returned null (aborted or timed out)");
    await afterLogin(api);
  } catch (err) {
    logger.error("QR login failed", { error: err.message });
    await reportSession({ status: "error", error_msg: String(err.message).slice(0, 500) });
    dropSession();
  } finally {
    loginInProgress = false;
  }
}

// -------------------------------------------------------------------
// Lang nghe tin nhom (READ-ONLY)
// -------------------------------------------------------------------

function startListening() {
  if (!zaloApi) return;
  const { listener } = zaloApi;

  listener.on("message", async (msg) => {
    try {
      if (msg.type !== ThreadType.Group || msg.isSelf) return;
      const zaloGroupId = msg.threadId;
      if (!zaloGroupId) return;

      const content = msg.data?.content;
      const text = extractText(content);
      const mediaRef = extractMediaRef(content);
      if (!text && !mediaRef) return;

      const ts = Number(msg.data?.ts);
      const result = await pushMessage({
        zalo_group_id: zaloGroupId,
        group_name: resolveGroupName(zaloGroupId),
        sender_zalo_id: String(msg.data?.uidFrom || ""),
        sender_name: String(msg.data?.dName || "").slice(0, 150),
        text: text.slice(0, 4000),
        media_ref: mediaRef,
        ts: Number.isFinite(ts) ? ts : null,
      });
      if (result?.stored) {
        logger.debug("Message ingested", { group: zaloGroupId, signals: result.signals_created || 0 });
      }
    } catch (err) {
      logger.warn("Error processing message", { error: err.message });
    }
  });

  listener.on("connected", () => logger.info("Zalo websocket connected."));
  listener.on("disconnected", (code, reason) => logger.warn("Zalo websocket disconnected", { code, reason }));
  listener.on("error", (err) => logger.warn("Zalo listener error", { error: String(err?.message || err) }));
  listener.on("closed", async (code, reason) => {
    logger.warn("Zalo listener closed", { code, reason });
    if (code === 3000 || code === 3003) {
      // Tai khoan vua dang nhap Zalo Web/PC o noi khac -> phien nay bi day ra
      dropSession();
      await clearCredentials();
      await reportSession({
        status: "error",
        error_msg: "Zalo bị đăng nhập ở nơi khác (Zalo Web/PC) nên phiên nghe đã ngắt — quét QR lại",
      });
    } else if (code !== 1000 && loggedIn) {
      // Mat ket noi bat thuong ma khong tu noi lai -> thu dang nhap lai bang phien da luu
      dropSession();
      await loginWithSaved();
    }
  });

  listener.start({ retryOnClose: true });
  logger.info("Message listener started.");
}

// -------------------------------------------------------------------
// Vong poll: heartbeat + yeu cau dang nhap/dang xuat tu web
// -------------------------------------------------------------------

async function pollLoop() {
  const result = await pollPendingLogin();
  if (!result) return; // backend khong toi duoc -- da log

  if (loggedIn && result.current_status === "logged_out") {
    logger.info("Admin logged out from web -- stopping listener.");
    dropSession();
    return;
  }
  if (result.login_requested && !loggedIn && !loginInProgress) {
    logger.info("Backend requested login. Initiating QR flow...");
    await loginWithQR();
  }
}

// -------------------------------------------------------------------
// Startup
// -------------------------------------------------------------------

logger.info("Starting JAMA Zalo Listener", { backend: config.backendUrl, pollMs: config.pollMs });

(async () => {
  await loginWithSaved();
  await pollLoop();
  setInterval(() => pollLoop().catch((e) => logger.warn("pollLoop error", { error: e.message })), config.pollMs);
  setInterval(() => loggedIn && syncAllGroups(), GROUP_SYNC_MS);
})();

function shutdown(signal) {
  logger.info("Received %s -- shutting down.", signal);
  dropSession();
  process.exit(0);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("uncaughtException", (err) => {
  logger.error("Uncaught exception", { error: err.message, stack: err.stack });
});
process.on("unhandledRejection", (reason) => {
  logger.error("Unhandled rejection", { reason: String(reason) });
});
