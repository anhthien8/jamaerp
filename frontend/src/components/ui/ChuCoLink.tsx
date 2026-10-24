'use client';

/** Đoạn chữ có link http(s) bấm được (nhật ký đầu việc chứa link tin Telegram).
 *  Link t.me hiện gọn «Mở trong Telegram» cho đỡ dài trên điện thoại. */
const LINK = /(https?:\/\/[^\s<>"']+)/g;

export default function ChuCoLink({ text }: { text: string }) {
  const phan = text.split(LINK);
  return (
    <>
      {phan.map((p, i) =>
        i % 2 === 1 ? (
          <a
            key={i}
            href={p}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--gold-500)] underline underline-offset-2 break-all"
          >
            {p.startsWith('https://t.me/') ? 'Mở trong Telegram' : p}
          </a>
        ) : (
          p
        ),
      )}
    </>
  );
}
