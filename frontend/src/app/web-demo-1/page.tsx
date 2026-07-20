'use client';

/**
 * DEMO bản 1 — trang chủ jamahome.vn phong cách corporate premium SÁNG:
 * conversion-first (form báo giá ngay hero), trust bar navy, gallery Trước/Sau,
 * quy trình 6 bước icon, khối Customer Portal. So sánh với /web-demo (bản 2 luxury).
 */

import { useEffect, useRef } from 'react';
import { Be_Vietnam_Pro } from 'next/font/google';
import LineIcon from '@/components/ui/LineIcon';

const sans = Be_Vietnam_Pro({ subsets: ['vietnamese', 'latin'], weight: ['300', '400', '500', '600'] });

const IMG = {
  hero: 'https://jamahome.vn/wp-content/uploads/2026/05/hoan-thien-cai-tao-nha-pho-quan-7-phong-khach.jpg',
  g1: 'https://jamahome.vn/wp-content/uploads/2026/05/cai-tao-nha-pho-binh-chanh-1-tret-2-lau-phong-khach.jpg',
  g2: 'https://jamahome.vn/wp-content/uploads/2026/05/hoan-thien-cai-tao-can-ho-urben-green-khu-vuc-hanh-lang.jpg',
  g3: 'https://jamahome.vn/wp-content/uploads/2026/05/hoan-thien-cai-tao-nha-pho-go-vap-bep.jpg',
  portal: 'https://jamahome.vn/wp-content/uploads/2026/05/hoan-thien-cai-tao-nha-pho-quan-12-phong-khach-1.jpg',
};

const NAVY = '#0F2A47';
const GOLD = '#B8935A';

const CSS = `
  .w1 { background: #FBF9F5; color: #22303F; min-height: 100vh; }
  .w1 a { color: inherit; }
  .w1 .wrap { max-width: 1180px; margin: 0 auto; padding: 0 28px; }
  .w1 .btn { display: inline-flex; align-items: center; gap: 8px; border-radius: 10px; font-size: 14px; font-weight: 500; padding: 13px 24px; cursor: pointer; transition: all .25s; }
  .w1 .btn-gold { background: ${GOLD}; color: #fff; }
  .w1 .btn-gold:hover { background: #A07C46; }
  .w1 .btn-navy { background: ${NAVY}; color: #fff; }
  .w1 .btn-line { border: 1px solid #3C577A; color: #CBD8E8; }

  .w1-nav { position: sticky; top: 0; z-index: 50; background: rgba(255,255,255,.97); border-bottom: 1px solid #EEE9DF; }
  .w1-nav .in { display: flex; align-items: center; justify-content: space-between; padding: 14px 28px; max-width: 1180px; margin: 0 auto; }
  .w1-nav .logo { display: flex; align-items: center; gap: 9px; font-weight: 600; color: ${NAVY}; font-size: 17px; letter-spacing: .5px; }
  .w1-nav .menu { display: flex; gap: 26px; font-size: 13.5px; color: #5A6472; }
  .w1-nav .menu a:hover { color: ${GOLD}; }

  .w1-hero { background: #FBF9F5; }
  .w1-hero .in { display: grid; grid-template-columns: 1.12fr 1fr; gap: 40px; align-items: center; max-width: 1180px; margin: 0 auto; padding: 54px 28px 64px; }
  .w1 .badge { display: inline-flex; align-items: center; gap: 7px; font-size: 12.5px; font-weight: 500; color: #8A6F3F; background: #F3EBDB; border-radius: 999px; padding: 7px 16px; margin-bottom: 18px; }
  .w1-hero h1 { font-size: clamp(30px, 3.6vw, 44px); line-height: 1.22; color: ${NAVY}; font-weight: 600; margin: 0 0 14px; }
  .w1-hero h1 em { color: ${GOLD}; font-style: normal; }
  .w1-hero .sub { font-size: 15px; font-weight: 300; color: #5A6472; line-height: 1.8; margin-bottom: 24px; }
  .w1-quote { background: #fff; border: 1px solid #E8E0D0; border-radius: 16px; padding: 22px; box-shadow: 0 10px 34px rgba(15,42,71,.08); }
  .w1-quote .qt { font-size: 15px; font-weight: 600; color: ${NAVY}; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
  .w1-quote .row { display: flex; gap: 10px; margin-bottom: 10px; }
  .w1-quote input, .w1-quote select { flex: 1; border: 1px solid #E4DCC9; border-radius: 10px; padding: 12px 13px; font-size: 14px; color: #22303F; background: #FDFCF9; outline: none; min-width: 0; }
  .w1-quote input:focus, .w1-quote select:focus { border-color: ${GOLD}; }
  .w1-quote .note { font-size: 11.5px; color: #98A0AC; margin-top: 9px; text-align: center; }
  .w1-himg { position: relative; border-radius: 18px; overflow: hidden; box-shadow: 0 18px 44px rgba(15,42,71,.16); }
  .w1-himg img { width: 100%; height: 430px; object-fit: cover; display: block; }
  .w1-himg .tag { position: absolute; bottom: 14px; left: 14px; background: rgba(15,42,71,.85); color: #fff; font-size: 11.5px; padding: 7px 13px; border-radius: 8px; }

  .w1-trust { background: ${NAVY}; }
  .w1-trust .in { display: flex; justify-content: space-around; flex-wrap: wrap; gap: 18px; max-width: 1180px; margin: 0 auto; padding: 26px 28px; }
  .w1-trust b { display: block; font-size: 26px; color: #D9B87C; font-weight: 600; }
  .w1-trust span { font-size: 11.5px; color: #B9C4D2; }
  .w1-trust > .in > div { text-align: center; }

  .w1-sec { padding: 64px 0; }
  .w1-sec.alt { background: #F4F0E7; }
  .w1 h2 { font-size: 26px; color: ${NAVY}; font-weight: 600; margin: 0 0 6px; }
  .w1 .ss { font-size: 13.5px; color: #8A93A0; margin: 0 0 26px; }

  .w1-gal { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
  .w1-gcard { border-radius: 14px; overflow: hidden; border: 1px solid #EEE8DC; background: #fff; transition: transform .25s, box-shadow .25s; }
  .w1-gcard:hover { transform: translateY(-4px); box-shadow: 0 14px 34px rgba(15,42,71,.1); }
  .w1-gcard img { width: 100%; height: 200px; object-fit: cover; display: block; }
  .w1-gmeta { padding: 13px 16px; display: flex; justify-content: space-between; align-items: center; }
  .w1-gmeta b { font-size: 14.5px; color: ${NAVY}; font-weight: 600; display: block; }
  .w1-gmeta span { font-size: 11.5px; color: #98A0AC; }
  .w1-gmeta .ba { font-size: 10px; letter-spacing: 1px; color: ${GOLD}; font-weight: 600; }

  .w1-steps { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }
  .w1-step { background: #fff; border: 1px solid #EEE8DC; border-radius: 14px; padding: 18px 10px; text-align: center; }
  .w1-step .ic { width: 44px; height: 44px; border-radius: 12px; background: #F3EBDB; display: flex; align-items: center; justify-content: center; margin: 0 auto 10px; }
  .w1-step b { font-size: 12.5px; color: ${NAVY}; font-weight: 600; display: block; }
  .w1-step span { font-size: 10.5px; color: #98A0AC; }

  .w1-portal { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; align-items: center; }
  .w1-portal img { width: 100%; height: 300px; object-fit: cover; border-radius: 16px; display: block; }
  .w1-portal ul { list-style: none; padding: 0; margin: 0 0 20px; }
  .w1-portal li { display: flex; gap: 10px; font-size: 14px; color: #5A6472; margin-bottom: 11px; align-items: flex-start; }
  .w1-portal li .tick { color: #2E9E6B; flex-shrink: 0; margin-top: 2px; }

  .w1-foot { background: ${NAVY}; }
  .w1-foot .in { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 18px; max-width: 1180px; margin: 0 auto; padding: 34px 28px; }
  .w1-foot .fl { color: #fff; font-size: 17px; font-weight: 600; }
  .w1-foot .fl span { display: block; font-size: 12px; color: #9FB0C4; font-weight: 300; margin-top: 4px; }
  .w1-foot .btns { display: flex; gap: 12px; }

  .w1-badge { position: fixed; bottom: 18px; left: 18px; z-index: 60; background: rgba(15,42,71,.94); color: #D9B87C; font-size: 11px; letter-spacing: 1px; padding: 9px 15px; border-radius: 8px; }
  .w1-badge a { color: #fff; text-decoration: underline; margin-left: 8px; }

  .w1 .fade { opacity: 0; transform: translateY(22px); transition: opacity .7s ease, transform .7s ease; }
  .w1 .fade.in { opacity: 1; transform: none; }

  @media (max-width: 860px) {
    .w1-nav .menu { display: none; }
    .w1-hero .in { grid-template-columns: 1fr; padding: 34px 22px 44px; }
    .w1-himg img { height: 260px; }
    .w1-gal { grid-template-columns: 1fr; }
    .w1-steps { grid-template-columns: repeat(3, 1fr); }
    .w1-portal { grid-template-columns: 1fr; }
    .w1-foot .in { justify-content: center; text-align: center; }
  }
`;

export default function WebDemo1Page() {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const io = new IntersectionObserver(
      entries => entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('in'); }),
      { threshold: 0.12 }
    );
    rootRef.current?.querySelectorAll('.fade').forEach(el => io.observe(el));
    return () => io.disconnect();
  }, []);

  return (
    <div ref={rootRef} className={`w1 ${sans.className}`}>
      <style>{CSS}</style>

      <nav className="w1-nav">
        <div className="in">
          <div className="logo"><LineIcon name="building" size={22} color={GOLD} />JAMA HOME</div>
          <div className="menu">
            <a href="#dichvu">Dịch vụ</a>
            <a href="#congtrinh">Công trình</a>
            <a href="#quytrinh">Quy trình</a>
            <a href="https://jamahome.vn/cam-nang-noi-that/" target="_blank" rel="noreferrer">Cẩm nang</a>
            <a href="#portal">Về JAMA</a>
          </div>
          <a className="btn btn-gold" href="/bao-gia" style={{ padding: '10px 18px', fontSize: 13 }}>
            <LineIcon name="zap" size={15} color="#fff" />Báo giá 30 giây
          </a>
        </div>
      </nav>

      <header className="w1-hero" id="dichvu">
        <div className="in">
          <div>
            <span className="badge"><LineIcon name="star" size={14} color="#8A6F3F" />10 năm · Dẫn đầu cải tạo trọn gói TP.HCM</span>
            <h1>Cải tạo tổ ấm cũ thành <em>không gian sống mới</em> — trọn gói, đúng hẹn</h1>
            <p className="sub">Nhà phố · chung cư · biệt thự tại TP.HCM &amp; miền Tây. Theo dõi tiến độ online từng ngày, nghiệm thu minh bạch từng giai đoạn.</p>
            <div className="w1-quote">
              <div className="qt"><LineIcon name="zap" size={17} color={GOLD} />Nhận khoảng giá ngay — không cần chờ gọi lại</div>
              <div className="row">
                <input placeholder="Diện tích (m²)" inputMode="numeric" />
                <select defaultValue=""><option value="" disabled>Loại nhà</option><option>Nhà phố</option><option>Chung cư</option><option>Biệt thự</option></select>
              </div>
              <div className="row"><input placeholder="Số điện thoại của bạn" inputMode="tel" /></div>
              <a className="btn btn-gold" href="/bao-gia" style={{ width: '100%', justifyContent: 'center' }}>Xem khoảng giá trong 30 giây</a>
              <div className="note">Miễn phí khảo sát &amp; dự toán chi tiết sau đó · Thông tin được bảo mật</div>
            </div>
          </div>
          <div className="w1-himg">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={IMG.hero} alt="Công trình cải tạo nhà phố Quận 7 hoàn thiện bởi JAMA HOME" />
            <div className="tag">Nhà phố Q7 — hoàn thiện 45 ngày</div>
          </div>
        </div>
      </header>

      <section className="w1-trust">
        <div className="in">
          <div><b>10</b><span>năm kinh nghiệm</span></div>
          <div><b>100+</b><span>công trình cải tạo 2025</span></div>
          <div><b>100%</b><span>hợp đồng rõ ràng từng đợt</span></div>
          <div><b>12 tháng</b><span>bảo hành — nhắc tự động</span></div>
        </div>
      </section>

      <section className="w1-sec" id="congtrinh">
        <div className="wrap fade">
          <h2>Công trình thật — Trước &amp; Sau</h2>
          <p className="ss">Kéo thanh so sánh trước/sau trên từng dự án · lọc theo Nhà phố / Chung cư / Biệt thự</p>
          <div className="w1-gal">
            {[
              [IMG.g1, 'Nhà phố Bình Chánh', 'Cải tạo trọn gói · 60 ngày'],
              [IMG.g2, 'Căn hộ Urban Green', 'Nội thất mới · 21 ngày'],
              [IMG.g3, 'Nhà phố Gò Vấp', 'Bếp & phòng khách · 30 ngày'],
            ].map(([img, name, meta]) => (
              <div className="w1-gcard" key={name}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={img} alt={`Công trình ${name}`} />
                <div className="w1-gmeta">
                  <div><b>{name}</b><span>{meta}</span></div>
                  <span className="ba">TRƯỚC ⇄ SAU</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="w1-sec alt" id="quytrinh">
        <div className="wrap fade">
          <h2>Quy trình 6 bước minh bạch</h2>
          <p className="ss">Bạn biết chính xác mình đang ở bước nào — mọi lúc, ngay trên điện thoại</p>
          <div className="w1-steps">
            {[
              ['message', 'Tư vấn', 'miễn phí'],
              ['zap', 'Báo giá 30s', 'khoảng giá ngay'],
              ['compass', 'Khảo sát', 'đo đạc tận nơi'],
              ['check', 'Hợp đồng', 'rõ từng đợt'],
              ['building', 'Thi công', 'cập nhật mỗi ngày'],
              ['shield', 'Bảo hành', '12 tháng'],
            ].map(([ic, name, meta]) => (
              <div className="w1-step" key={name}>
                <div className="ic"><LineIcon name={ic} size={21} color={GOLD} /></div>
                <b>{name}</b><span>{meta}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="w1-sec" id="portal">
        <div className="wrap fade">
          <div className="w1-portal">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={IMG.portal} alt="Khách hàng theo dõi tiến độ công trình qua Customer Portal" />
            <div>
              <h2>Theo dõi tổ ấm của bạn — ngay trên điện thoại</h2>
              <p className="ss" style={{ marginBottom: 16 }}>Đặc quyền chỉ có tại JAMA HOME</p>
              <ul>
                <li><span className="tick"><LineIcon name="check" size={16} color="#2E9E6B" /></span>Xem tiến độ, hình ảnh công trường cập nhật từng ngày</li>
                <li><span className="tick"><LineIcon name="check" size={16} color="#2E9E6B" /></span>Xác nhận nghiệm thu online từng giai đoạn — minh bạch, không tranh cãi</li>
                <li><span className="tick"><LineIcon name="check" size={16} color="#2E9E6B" /></span>Không cần cài app — chỉ một đường link riêng bảo mật</li>
              </ul>
              <a className="btn btn-navy" href="/portal/demo" target="_blank" rel="noreferrer">Xem portal mẫu</a>
            </div>
          </div>
        </div>
      </section>

      <footer className="w1-foot">
        <div className="in">
          <div className="fl">Sẵn sàng làm mới tổ ấm của bạn?<span>Khảo sát &amp; dự toán chi tiết miễn phí tại TP.HCM · 070.56.23456</span></div>
          <div className="btns">
            <a className="btn btn-gold" href="/bao-gia"><LineIcon name="zap" size={15} color="#fff" />Báo giá 30 giây</a>
            <a className="btn btn-line" href="https://zalo.me/0705623456" target="_blank" rel="noreferrer"><LineIcon name="message" size={15} color="#CBD8E8" />Chat Zalo</a>
          </div>
        </div>
      </footer>

      <div className="w1-badge">BẢN DEMO 1 — corporate premium<a href="/web-demo">Xem bản 2 →</a></div>
    </div>
  );
}
