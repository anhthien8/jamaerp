/**
 * Nén ảnh phía trình duyệt trước khi tải lên Kho ảnh công trình (23/10/2026):
 * cạnh dài ≤1600px, JPG, tô nền trắng cho PNG trong suốt. Ảnh điện thoại 4–8 MB
 * còn ~300 KB → tải nhanh trên 4G công trình. Backend vẫn chuẩn hoá lại lần nữa.
 */
export async function nenAnh(file: Blob, maxDim = 1600, quality = 0.82): Promise<Blob | null> {
  const bitmap = await createImageBitmap(file).catch(() => null);
  if (!bitmap) return null;
  const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close?.();
  return new Promise(resolve => canvas.toBlob(b => resolve(b), 'image/jpeg', quality));
}

/** Blob → data-URL để xem trước trong hàng chờ. */
export function blobThanhDataUrl(b: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onloadend = () => resolve(r.result as string);
    r.onerror = () => reject(r.error);
    r.readAsDataURL(b);
  });
}
