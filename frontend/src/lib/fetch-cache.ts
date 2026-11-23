/**
 * Cache nhỏ cho các request GET dùng chung nhiều nơi.
 *
 * Vì sao có file này: khung app (Sidebar/NotificationCenter) nằm trong layout
 * nên mỗi lần mở một trang bất kỳ nó lại gọi lại cùng một danh sách. Thêm nữa
 * React StrictMode (bật sẵn ở `next dev`) chạy effect HAI lần nên mỗi lần mở
 * trang là hai request y hệt nhau. Gói lời gọi qua `cachedFetch` thì mọi nơi
 * dùng cùng `key` chia nhau MỘT promise trong khoảng `ttlMs`.
 *
 * Chỉ dùng cho dữ liệu đọc, chịu được cũ vài chục giây (danh sách sinh badge,
 * danh mục tra cứu). KHÔNG dùng cho số liệu phải đúng tức thì sau khi ghi.
 */

type Entry = { at: number; promise: Promise<unknown> };

const store = new Map<string, Entry>();

export function cachedFetch<T>(key: string, ttlMs: number, fn: () => Promise<T>): Promise<T> {
  const hit = store.get(key);
  if (hit && Date.now() - hit.at < ttlMs) return hit.promise as Promise<T>;

  const promise = fn();
  store.set(key, { at: Date.now(), promise });
  // Lỗi thì bỏ khỏi cache ngay, không giữ promise reject suốt TTL.
  promise.catch(() => {
    if (store.get(key)?.promise === promise) store.delete(key);
  });
  return promise;
}
