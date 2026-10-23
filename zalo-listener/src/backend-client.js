/**
 * JAMA Zalo Listener -- Backend HTTP Client
 *
 * Encapsulates all communication with the JAMA backend ingest endpoints.
 * Every request includes the X-Zalo-Secret header for authentication.
 * All failures are logged and swallowed (never crashes the caller).
 */

import { request } from "undici";
import { config } from "./config.js";
import { logger } from "./logger.js";

const BASE = `${config.backendUrl}/api/v1`;
const HEADERS = Object.freeze({
  "Content-Type": "application/json",
  "X-Zalo-Secret": config.secret,
});

// -------------------------------------------------------------------
// Low-level helpers
// -------------------------------------------------------------------

async function apiGet(path) {
  const url = `${BASE}${path}`;
  try {
    const res = await request(url, { method: "GET", headers: HEADERS, bodyTimeout: 10_000 });
    if (res.statusCode === 200) {
      return await res.body.json();
    }
    logger.warn("apiGet non-200", { path, status: res.statusCode });
    return null;
  } catch (err) {
    logger.warn("apiGet failed", { path, error: err.message });
    return null;
  }
}

async function apiPost(path, body) {
  const url = `${BASE}${path}`;
  try {
    const res = await request(url, {
      method: "POST",
      headers: HEADERS,
      body: JSON.stringify(body),
      bodyTimeout: 15_000,
    });
    if (res.statusCode < 300) {
      // Backend may return empty body on 204; consume safely.
      const text = await res.body.text();
      return text ? JSON.parse(text) : {};
    }
    logger.warn("apiPost non-2xx", { path, status: res.statusCode });
    return null;
  } catch (err) {
    logger.warn("apiPost failed", { path, error: err.message });
    return null;
  }
}

// -------------------------------------------------------------------
// Public API  (all functions are fire-and-forget safe)
// -------------------------------------------------------------------

/**
 * Report session status / QR image to the backend.
 * @param {object} payload - { status, qr_image?, account_name?, error_msg? }
 */
export async function reportSession(payload) {
  await apiPost("/zalo/ingest/session", payload);
}

/**
 * Push a single group message to the backend.
 * @param {object} msg - { zalo_group_id, group_name, sender_zalo_id, sender_name, text, media_ref }
 */
export async function pushMessage(msg) {
  return await apiPost("/zalo/ingest/message", msg);
}

/**
 * Poll backend for pending login requests (also serves as heartbeat).
 * @returns {{ login_requested: boolean, current_status: string } | null}
 */
export async function pollPendingLogin() {
  return await apiGet("/zalo/ingest/pending-login");
}

/** Phien Zalo da luu (backend giai ma) hoac null. */
export async function getSavedCredentials() {
  const res = await apiGet("/zalo/ingest/credentials");
  return res?.credentials || null;
}

/** Luu phien sau khi quet QR: { cookie, imei, user_agent }. */
export async function saveCredentials(creds) {
  return await apiPost("/zalo/ingest/credentials", creds);
}

export async function clearCredentials() {
  try {
    await request(`${BASE}/zalo/ingest/credentials`, { method: "DELETE", headers: HEADERS, bodyTimeout: 10_000 });
  } catch (err) {
    logger.warn("clearCredentials failed", { error: err.message });
  }
}

/** Dong bo danh sach nhom: [{ zalo_group_id, name, member_count }]. */
export async function syncGroups(groups) {
  return await apiPost("/zalo/ingest/groups", { groups });
}
