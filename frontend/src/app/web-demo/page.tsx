'use client';

/**
 * DEMO trang chủ jamahome.vn bản mới — phong cách luxury editorial (học Masterise):
 * ảnh cinematic + serif thanh mảnh + kicker hoa giãn cách + bảng màu ngà/than/đồng.
 * Trang demo độc lập (không dùng Sidebar/theme ERP), ảnh hotlink từ jamahome.vn.
 * CTA nối thẳng hệ sinh thái có sẵn: /bao-gia (lead vào CRM) + /portal/demo.
 */

import { useEffect, useRef, useState } from 'react';
import { Playfair_Display, Be_Vietnam_Pro } from 'next/font/google';

const serif = Playfair_Display({ subsets: ['vietnamese', 'latin'], weight: ['400', '500'], style: ['normal', 'italic'] });
const sans = Be_Vietnam_Pro({ subsets: ['vietnamese', 'latin'], weight: ['300', '400', '500'] });

const IMG = {
  hero: 'https://jamahome.vn/wp-content/uploads/2026/05/hoan-thien-cai-tao-nha-pho-quan-7-phong-khach.jpg',
  g1: 'https://jamahome.vn/wp-content/uploads/2026/05/cai-tao-nha-pho-binh-chanh-1-tret-2-lau-phong-khach.jpg',
  g2: 'https://jamahome.vn/wp-content/uploads/2026/05/hoan-thien-cai-tao-can-ho-urben-green-khu-vuc-hanh-lang.jpg',
  g3: 'https://jamahome.vn/wp-content/uploads/2026/05/hoan-thien-cai-tao-nha-pho-go-vap-bep.jpg',
  portal: 'https://jamahome.vn/wp-content/uploads/2026/05/hoan-thien-cai-tao-nha-pho-quan-12-phong-khach-1.jpg',
};

const CSS = `
  .wd { --ivory:#F7F4EE; --ivory2:#F1EDE3; --char:#23211C; --char2:#1B1915; --bronze:#A8875A; --bronze-l:#C8AE78; --champ:#E3CD9F; --muted:#7A7361; --hair:#E5DECF; }
  .wd { background: var(--ivory); color: var(--char); min-height: 100vh; }
  .wd .kick { font-size: 11px; letter-spacing: 5px; text-transform: uppercase; color: var(--bronze); }
  .wd .btn-o { display: inline-block; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; padding: 14px 34px; border: 1px solid currentColor; transition: all .35s; cursor: pointer; }
  .wd .btn-o:hover { background: var(--char); color: var(--ivory) !important; border-color: var(--char); }
  .wd .fade { opacity: 0; transform: translateY(26px); transition: opacity .8s ease, transform .8s ease; }
  .wd .fade.in { opacity: 1; transform: none; }

  .wd-nav { position: fixed; top: 0; left: 0; right: 0; z-index: 50; display: flex; align-items: center; justify-content: space-between; padding: 22px 48px; transition: all .4s; }
  .wd-nav.solid { background: rgba(247,244,238,.96); border-bottom: 1px solid var(--hair); padding: 14px 48px; }
  .wd-nav .logo { font-size: 17px; letter-spacing: 4px; color: #FBF8F1; transition: color .4s; }
  .wd-nav.solid .logo { color: var(--char); }
  .wd-nav .menu { display: flex; gap: 30px; font-size: 11px; letter-spacing: 2px; text-transform: uppercase; color: rgba(251,248,241,.85); transition: color .4s; }
  .wd-nav.solid .menu { color: var(--muted); }
  .wd-nav .menu a:hover { color: var(--bronze-l); }
  .wd-nav .cta { font-size: 10px; letter-spacing: 2.5px; text-transform: uppercase; padding: 10px 20px; border: 1px solid rgba(251,248,241,.6); color: #FBF8F1; transition: all .4s; }
  .wd-nav.solid .cta { border-color: var(--char); color: var(--char); }
  .wd-nav .cta:hover { background: var(--bronze); border-color: var(--bronze); color: #fff !important; }

  .wd-hero { position: relative; height: 100vh; min-height: 560px; overflow: hidden; }
  .wd-hero img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; animation: kenburns 18s ease-out forwards; }
  @keyframes kenburns { from { transform: scale(1.12); } to { transform: scale(1); } }
  .wd-hero::after { content: ''; position: absolute; inset: 0; background: linear-gradient(rgba(20,18,14,.35), rgba(20,18,14,.55)); }
  .wd-hero .in { position: absolute; inset: 0; z-index: 2; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 0 24px; }
  .wd-hero .kick { color: var(--champ); margin-bottom: 22px; }
  .wd-hero h1 { font-size: clamp(42px, 7vw, 84px); line-height: 1.12; color: #FBF8F1; font-weight: 400; margin: 0 0 14px; }
  .wd-hero h1 em { color: var(--champ); }
  .wd-hero p { font-size: 15px; font-weight: 300; color: rgba(251,248,241,.85); max-width: 560px; line-height: 1.9; margin: 0 0 34px; }
  .wd-hero .btn-o { color: #FBF8F1; border-color: rgba(251,248,241,.65); }
  .wd-hero .scroll { position: absolute; bottom: 26px; left: 50%; transform: translateX(-50%); z-index: 2; color: rgba(251,248,241,.6); font-size: 10px; letter-spacing: 3px; text-transform: uppercase; }

  .wd-sec { padding: 110px 48px; text-align: center; }
  .wd-sec h2 { font-size: clamp(26px, 3.4vw, 40px); line-height: 1.35; font-weight: 400; margin: 18px 0 20px; }
  .wd-sec .body { font-size: 14px; font-weight: 300; color: var(--muted); line-height: 2.05; max-width: 620px; margin: 0 auto; }
  .wd .hairline { width: 44px; height: 1px; background: var(--bronze-l); margin: 30px auto 0; }

  .wd-grid { display: grid; grid-template-columns: 1.45fr 1fr; grid-auto-rows: 300px; gap: 18px; max-width: 1180px; margin: 0 auto; padding: 0 48px; }
  .wd-g { position: relative; overflow: hidden; grid-row: span 1; }
  .wd-g.tall { grid-row: span 2; }
  .wd-g img { width: 100%; height: 100%; object-fit: cover; transition: transform 1.2s ease; }
  .wd-g:hover img { transform: scale(1.05); }
  .wd-g .cap { position: absolute; left: 0; right: 0; bottom: 0; padding: 46px 26px 20px; background: linear-gradient(transparent, rgba(20,18,14,.62)); display: flex; justify-content: space-between; align-items: baseline; }
  .wd-g .cap b { font-size: 19px; color: #FBF8F1; font-weight: 400; }
  .wd-g .cap span { font-size: 10px; letter-spacing: 2.5px; color: var(--champ); text-transform: uppercase; }

  .wd-nums { display: flex; justify-content: center; background: var(--ivory2); padding: 72px 24px; }
  .wd-num { padding: 0 64px; text-align: center; border-right: 1px solid #DFD8C8; }
  .wd-num:last-child { border-right: none; }
  .wd-num b { display: block; font-size: 54px; color: var(--bronze); font-weight: 400; line-height: 1.1; }
  .wd-num span { font-size: 10.5px; letter-spacing: 2.5px; color: var(--muted); text-transform: uppercase; }

  .wd-steps { display: flex; justify-content: space-between; max-width: 900px; margin: 54px auto 0; padding: 0 24px; }
  .wd-step { text-align: center; }
  .wd-step b { display: block; font-size: 30px; color: var(--bronze-l); font-weight: 400; margin-bottom: 10px; }
  .wd-step span { font-size: 10.5px; letter-spacing: 2px; color: var(--char); text-transform: uppercase; }

  .wd-portal { position: relative; background: var(--char2); overflow: hidden; }
  .wd-portal img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; opacity: .18; }
  .wd-portal .in { position: relative; z-index: 2; padding: 120px 48px; text-align: center; }
  .wd-portal h2 { color: #FBF8F1; }
  .wd-portal .body { color: #B0A78F; }
  .wd-portal .btn-o { color: var(--champ); border-color: #6E6146; margin-top: 34px; }
  .wd-portal .btn-o:hover { background: var(--bronze); border-color: var(--bronze); }

  .wd-foot { background: var(--char2); border-top: 1px solid #343026; padding: 44px 48px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 18px; }
  .wd-foot .logo { font-size: 15px; letter-spacing: 4px; color: var(--champ); }
  .wd-foot span { font-size: 11px; color: #7A7361; letter-spacing: 1px; }
  .wd-foot .btn-o { color: var(--champ); border-color: #6E6146; padding: 10px 22px; font-size: 10px; }

  .wd-demo-badge { position: fixed; bottom: 18px; left: 18px; z-index: 60; background: rgba(35,33,28,.92); color: #E3CD9F; font-size: 10px; letter-spacing: 2px; padding: 8px 14px; text-transform: uppercase; }

  @media (max-width: 860px) {
    .wd-nav { padding: 16px 20px; } .wd-nav .menu { display: none; }
    .wd-sec { padding: 72px 22px; }
    .wd-grid { grid-template-columns: 1fr; grid-auto-rows: 240px; padding: 0 22px; }
    .wd-g.tall { grid-row: span 1; }
    .wd-nums { flex-wrap: wrap; gap: 28px 0; } .wd-num { padding: 0 28px; border-right: none; }
    .wd-steps { flex-wrap: wrap; gap: 26px 18px; justify-content: center; }
    .wd-portal .in { padding: 80px 22px; }
    .wd-foot { justify-content: center; text-align: center; }
  }
`;

export default function WebDemoPage() {
  const [solid, setSolid] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onScroll = () => setSolid(window.scrollY > 60);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    const io = new IntersectionObserver(
      entries => entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('in'); }),
      { threshold: 0.15 }
    );
    rootRef.current?.querySelectorAll('.fade').forEach(el => io.observe(el));
    return () => { window.removeEventListener('scroll', onScroll); io.disconnect(); };
  }, []);

  return (
    <div ref={rootRef} className={`wd ${sans.className}`}>
      <style>{CSS}</style>

      <nav className={`wd-nav ${solid ? 'solid' : ''}`}>
        <div className={`logo ${serif.className}`}>JAMA HOME</div>
        <div className="menu">
          <a href="#congtrinh">Công trình</a>
          <a href="#hanhtrinh">Hành trình</a>
          <a href="#portal">Đặc quyền</a>
          <a href="https://jamahome.vn/cam-nang-noi-that/" target="_blank" rel="noreferrer">Cẩm nang</a>
        </div>
        <a className="cta" href="/bao-gia">Nhận báo giá</a>
      </nav>

      <header className="wd-hero">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={IMG.hero} alt="Công trình cải tạo nhà phố Quận 7 do JAMA HOME hoàn thiện" />
        <div className="in">
          <div className="kick">Một thập kỷ kiến tạo tổ ấm</div>
          <h1 className={serif.className}>Tổ ấm cũ.<br /><em>Cuộc sống mới.</em></h1>
          <p>Cải tạo nhà phố · chung cư · biệt thự trọn gói tại TP. Hồ Chí Minh — theo dõi tiến độ online từng ngày, nghiệm thu minh bạch từng giai đoạn.</p>
          <a className="btn-o" href="/bao-gia">Nhận báo giá — 30 giây</a>
        </div>
        <div className="scroll">Cuộn xuống</div>
      </header>

      <section className="wd-sec">
        <div className="fade">
          <div className="kick">Triết lý</div>
          <h2 className={serif.className}>Chúng tôi không sửa những bức tường.<br />Chúng tôi làm mới cách bạn sống.</h2>
          <p className="body">
            Mười năm đồng hành cùng những gia đình Sài Gòn — biến nhà phố xuống cấp, căn hộ cũ kỹ
            thành không gian đáng sống. Trọn gói. Đúng hẹn. Và minh bạch đến từng viên gạch.
          </p>
          <div className="hairline" />
        </div>
      </section>

      <section id="congtrinh" style={{ paddingBottom: 110 }}>
        <div className="wd-sec fade" style={{ paddingBottom: 34, paddingTop: 0 }}>
          <div className="kick">Công trình tiêu biểu</div>
        </div>
        <div className="wd-grid fade">
          <div className="wd-g tall">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={IMG.g1} alt="Cải tạo nhà phố Bình Chánh — phòng khách" />
            <div className="cap"><b className={serif.className}>Nhà phố Bình Chánh</b><span>Hoàn thiện</span></div>
          </div>
          <div className="wd-g">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={IMG.g2} alt="Cải tạo căn hộ Urban Green" />
            <div className="cap"><b className={serif.className}>Căn hộ Urban Green</b><span>Hoàn thiện</span></div>
          </div>
          <div className="wd-g">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={IMG.g3} alt="Cải tạo bếp nhà phố Gò Vấp" />
            <div className="cap"><b className={serif.className}>Nhà phố Gò Vấp</b><span>Hoàn thiện</span></div>
          </div>
        </div>
        <div className="wd-sec fade" style={{ paddingTop: 44, paddingBottom: 0 }}>
          <a className="btn-o" href="https://jamahome.vn" target="_blank" rel="noreferrer" style={{ color: 'var(--char)' }}>Xem tất cả công trình</a>
        </div>
      </section>

      <section className="wd-nums fade">
        <div className="wd-num"><b className={serif.className}>10</b><span>năm kiến tạo</span></div>
        <div className="wd-num"><b className={serif.className}>100+</b><span>công trình 2025</span></div>
        <div className="wd-num"><b className={serif.className}>12</b><span>tháng bảo hành</span></div>
      </section>

      <section id="hanhtrinh" className="wd-sec">
        <div className="fade">
          <div className="kick">Hành trình của bạn</div>
          <h2 className={serif.className}>Sáu bước. Một lời hứa.</h2>
        </div>
        <div className="wd-steps fade">
          {[['01', 'Trò chuyện'], ['02', 'Báo giá 30s'], ['03', 'Khảo sát'], ['04', 'Thiết kế'], ['05', 'Thi công'], ['06', 'Bàn giao']].map(([n, t]) => (
            <div className="wd-step" key={n}><b className={serif.className}>{n}</b><span>{t}</span></div>
          ))}
        </div>
      </section>

      <section id="portal" className="wd-portal">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={IMG.portal} alt="" aria-hidden="true" />
        <div className="in fade">
          <div className="kick" style={{ color: 'var(--bronze-l)' }}>Đặc quyền khách hàng JAMA</div>
          <h2 className={serif.className}>Tổ ấm của bạn — trong lòng bàn tay</h2>
          <p className="body">
            Một đường link riêng tư. Tiến độ cập nhật mỗi ngày, hình ảnh từ công trường,
            và nghiệm thu từng giai đoạn chỉ bằng một chạm. Không cần cài ứng dụng.
          </p>
          <a className="btn-o" href="/portal/demo" target="_blank" rel="noreferrer">Trải nghiệm portal mẫu</a>
        </div>
      </section>

      <footer className="wd-foot">
        <div className={`logo ${serif.className}`}>JAMA HOME</div>
        <span>Thiết kế cho cuộc sống mới · TP. Hồ Chí Minh · 070.56.23456</span>
        <a className="btn-o" href="https://zalo.me/0705623456" target="_blank" rel="noreferrer">Chat Zalo</a>
      </footer>

      <div className="wd-demo-badge">Bản demo 2 — luxury <a href="/web-demo-1" style={{ color: '#FBF8F1', textDecoration: 'underline', marginLeft: 8 }}>Xem bản 1 →</a></div>
    </div>
  );
}
