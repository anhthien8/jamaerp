/**
 * JAMA HOME -- Zalo Listener Ingest Service (spec 09)
 * ====================================================
 * LISTEN-ONLY.  Runs TACH khoi backend ERP (lib Zalo hay vo -> khong keo sap he thong).
 *
 * Lifecycle:
 *  1. Poll backend GET /zalo/ingest/pending-login -- admin co bam "Dang nhap" khong?
 *  2. Neu co -> login Zalo qua QR (zca-js). Nhan QR -> day ve backend de admin quet tren web.
 *  3. Dang nhap xong -> lang nghe tin nhom -> POST /zalo/ingest/message (chi metadata + text).
 *  4. Heartbeat dinh ky de web biet service con song.
 *
 * CAUTION: Dung tai khoan Zalo ca nhan qua thu vien khong chinh thuc = vi pham ToS Zalo.
 *    Tai khoan SE co nguy bi khoa. Dung account phu chuyen dung. Khong gui tin (giam rui ro).
 *
 * Cai dat: npm install (can Node 20+). Chay: ZALO_INGEST_SECRET=... BACKEND_URL=... npm start
 *
 * zca-js v2.1.2 API (confirmed from source):
 *   - new Zalo({ selfListen: false })
 *   - zalo.loginQR(options, callback)  -- callback receives LoginQRCallbackEvent
 *   - callback event types: QRCodeGenerated, QRCodeExpired, QRCodeScanned, QRCodeDeclined, GotLoginInfo
 *   - api.listener.on("message", cb)  -- cb receives GroupMessage | UserMessage
 *   - GroupMessage: { type: ThreadType.Group, threadId: string, isSelf: boolean, data: TGroupMessage }
 *   - TGroupMessage.content: string (for text), .uidFrom: sender ID, .dName: sender display name
 *   - QR image from callback: raw base64 (no data URI prefix)
 */

import { Zalo, ThreadType, LoginQRCallbackEventType } from "zca-js";
import { config } from "./config.js";
import { logger } from "./logger.js";
import {
  reportSession,
  pushMessage,
  pollPendingLogin,
} from "./backend-client.js";

// -------------------------------------------------------------------
// State
// -------------------------------------------------------------------

let zaloApi = null;     // Logged-in API instance (null until login succeeds)
let loggedIn = false;    // True between login success and session loss
let loginInProgress = false; // Guard against concurrent login attempts

/** Cache: zalo_group_id -> group_name to avoid repeated lookups. */
const groupNameCache = new Map();

// -------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------

/**
 * Convert raw base64 (from zca-js QRCodeGenerated event) into a data URI
 * that the backend / frontend can render as an <img> src.
 */
function toDataUri(base64) {
  if (!base64) return null;
  if (base64.startsWith("data:")) return base64;
  return `data:image/png;base64,${base64}`;
}

/**
 * Extract text content from a zca-js message data object.
 * content can be a plain string, an attachment object, or an unknown shape.
 */
function extractText(content) {
  if (typeof content === "string") return content;
  if (content && typeof content === "object" && typeof content.title === "string") {
    // Attachment-type content -- return title/description as text reference.
    return content.title;
  }
  return "";
}

/**
 * Extract a link reference for media messages (images, files).
 * zca-js attachment objects have an `href` field.
 */
function extractMediaRef(content) {
  if (content && typeof content === "object" && typeof content.href === "string") {
    return content.href;
  }
  return null;
}

/**
 * Look up or return a cached group name.  zca-js GroupMessage does NOT carry
 * groupName, so we either use the cache or build a placeholder.
 */
function resolveGroupName(zaloGroupId) {
  return groupNameCache.get(zaloGroupId) || `Nhom ${zaloGroupId.slice(0, 8)}`;
}

// -------------------------------------------------------------------
// QR Login Flow
// -------------------------------------------------------------------

async function loginWithQR() {
  if (loginInProgress) {
    logger.info("Login already in progress, skipping.");
    return;
  }
  loginInProgress = true;

  logger.info("Starting Zalo QR login flow...");
  await reportSession({ status: "awaiting_qr" });

  try {
    const zalo = new Zalo({ selfListen: false });

    const api = await zalo.loginQR(
      { userAgent: "" },
      async (event) => {
        try {
          switch (event.type) {
            case LoginQRCallbackEventType.QRCodeGenerated: {
              // event.data: { code, image, options, token }
              // image is raw base64 PNG (no data URI prefix)
              const dataUri = toDataUri(event.data?.image);
              await reportSession({ status: "qr_ready", qr_image: dataUri });
              logger.info("QR code generated and pushed to backend.");
              break;
            }
            case LoginQRCallbackEventType.QRCodeExpired: {
              logger.warn("QR code expired. Waiting for backend to request a new login.");
              await reportSession({ status: "awaiting_qr" });
              break;
            }
            case LoginQRCallbackEventType.QRCodeScanned: {
              // event.data: { avatar, display_name }
              logger.info("QR code scanned by user: %s", event.data?.display_name || "unknown");
              await reportSession({ status: "qr_ready", qr_image: null });
              break;
            }
            case LoginQRCallbackEventType.QRCodeDeclined: {
              logger.warn("QR code login declined by user.");
              await reportSession({ status: "error", error_msg: "QR login declined by user" });
              break;
            }
            case LoginQRCallbackEventType.GotLoginInfo: {
              logger.info("Login session obtained.");
              break;
            }
            default:
              logger.debug("Unhandled loginQR event type: %d", event.type);
          }
        } catch (e) {
          logger.warn("Error in loginQR callback", { error: e.message });
        }
      },
    );

    if (!api) {
      throw new Error("loginQR returned null -- login may have been aborted or timed out");
    }

    // Login succeeded
    zaloApi = api;
    loggedIn = true;

    // Fetch own ID for logging (best-effort; zca-js v2 may not expose getOwnId directly)
    const accountName = "Zalo Listener";
    await reportSession({ status: "logged_in", account_name: accountName });
    logger.info("Login successful. Starting message listener...");

    startListening();
  } catch (err) {
    logger.error("Login failed", { error: err.message, stack: err.stack });
    await reportSession({ status: "error", error_msg: err.message.slice(0, 500) });
    loggedIn = false;
    zaloApi = null;
  } finally {
    loginInProgress = false;
  }
}

// -------------------------------------------------------------------
// Message Listener (READ-ONLY)
// -------------------------------------------------------------------

function startListening() {
  if (!zaloApi) {
    logger.warn("startListening called but zaloApi is null.");
    return;
  }

  const { listener } = zaloApi;

  listener.on("message", async (msg) => {
    try {
      // --- Filter: only group messages, ignore self ---
      if (msg.type !== ThreadType.Group) return;
      if (msg.isSelf) return;

      const zaloGroupId = msg.threadId;
      if (!zaloGroupId) return;

      const content = msg.data?.content;
      const text = extractText(content);
      const mediaRef = extractMediaRef(content);

      // Skip messages that have neither text nor media reference.
      if (!text && !mediaRef) return;

      const payload = {
        zalo_group_id: zaloGroupId,
        group_name: resolveGroupName(zaloGroupId),
        sender_zalo_id: String(msg.data?.uidFrom || ""),
        sender_name: String(msg.data?.dName || ""),
        text: text.slice(0, 4000),
        media_ref: mediaRef,
      };

      const result = await pushMessage(payload);

      // If backend reports a new group was created, we may want to update cache.
      // The backend auto-creates ZaloGroup entries; no name update needed from here.
      if (result?.stored) {
        logger.debug("Message ingested", { group: zaloGroupId, signals: result.signals_created || 0 });
      } else if (result?.stored === false) {
        logger.debug("Message skipped (monitoring off)", { group: zaloGroupId, reason: result.reason });
      }
    } catch (err) {
      logger.warn("Error processing message", { error: err.message });
    }
  });

  listener.start();
  logger.info("Message listener started.");
}

// -------------------------------------------------------------------
// Main Loop: poll for login requests + heartbeat
// -------------------------------------------------------------------

async function pollLoop() {
  try {
    const result = await pollPendingLogin();

    if (!result) {
      // Backend unreachable -- logged inside pollPendingLogin already.
      return;
    }

    // If backend signals a login is requested and we are not logged in, start QR flow.
    if (result.login_requested && !loggedIn && !loginInProgress) {
      logger.info("Backend requested login. Initiating QR flow...");
      await loginWithQR();
    }
  } catch (err) {
    // pollPendingLogin already catches internally, but just in case:
    logger.warn("pollLoop unexpected error", { error: err.message });
  }
}

async function heartbeatLoop() {
  if (!loggedIn) return;
  try {
    await reportSession({ status: "logged_in" });
  } catch (err) {
    logger.warn("heartbeat failed", { error: err.message });
  }
}

// -------------------------------------------------------------------
// Startup
// -------------------------------------------------------------------

logger.info("Starting JAMA Zalo Listener ingest service", {
  backend: config.backendUrl,
  pollMs: config.pollMs,
  heartbeatMs: config.heartbeatMs,
});

// First poll immediately, then on interval.
pollLoop();
setInterval(pollLoop, config.pollMs);
setInterval(heartbeatLoop, config.heartbeatMs);

// Graceful shutdown
function shutdown(signal) {
  logger.info("Received %s -- shutting down gracefully.", signal);
  loggedIn = false;
  zaloApi = null;
  process.exit(0);
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("uncaughtException", (err) => {
  logger.error("Uncaught exception", { error: err.message, stack: err.stack });
  // Do NOT exit -- keep the process alive so the poll loop can recover.
});
process.on("unhandledRejection", (reason) => {
  logger.error("Unhandled rejection", { reason: String(reason) });
});
