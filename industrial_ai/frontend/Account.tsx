import { useEffect } from 'react';
import Lenis from 'lenis';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { ArrowDown, ArrowUpRight, Scan, MousePointer2, MessageCircle, Monitor, MoveUpRight, Film, PencilLine, Link2 } from 'lucide-react';

const chapters = [
  { label: '01 / MENGAMATI', title: 'Lihat yang terjadi.', emphasis: 'Satu rekaman, banyak detail.', description: 'Unggah video dan ikuti objek sepanjang rekaman. Putar kembali, berhenti di satu momen, lalu bandingkan video asli dengan hasil analisis.', note: 'Mulai dari rekaman Anda sendiri.', icon: Scan },
  { label: '02 / MENGOREKSI', title: 'Anda tetap memegang kendali.', emphasis: 'Hasil pertama bukan akhir cerita.', description: 'Saat objek terlewat atau kotaknya kurang pas, perbaiki langsung pada frame. Koreksi tersimpan bisa dipakai untuk menyempurnakan model lokal.', note: 'Tinjau sebelum menyimpulkan.', icon: MousePointer2 },
  { label: '03 / MEMAHAMI', title: 'Tanyakan yang berarti.', emphasis: 'Dari melihat, menjadi mengerti.', description: 'Ajukan pertanyaan tentang rekaman. Jawaban merujuk pada hasil yang tersedia, sehingga Anda dapat kembali ke sumber dan memeriksanya.', note: 'Ada sumber untuk ditelusuri.', icon: MessageCircle },
];

function StoryScene({ step }: { step: number }) {
  return (
    <div className={`story-scene story-scene--${step}`} aria-hidden="true">
      <div className="scene-topline"><span>VIDEO INSIGHT / FIELD NOTES</span><span>0{step + 1}</span></div>
      {step < 2 ? <>
        <div className="scene-field"><div className="scene-grid"></div>
          <span className="scene-person scene-person--back"></span><span className="scene-person scene-person--front"></span><span className="scene-person scene-person--side"></span>
          <div className="scene-box scene-box--main"><span>{step === 0 ? 'AMATI' : 'SESUAIKAN'}</span><i></i><i></i><i></i><i></i></div>
          {step === 0 ? <><div className="scene-box scene-box--side"></div><div className="scene-scan"></div></> : <><div className="scene-before"></div><MousePointer2 className="scene-cursor" size={30} fill="currentColor" /></>}
          <div className="scene-floor"></div>
        </div>
        <div className="scene-bottomline"><span>{step === 0 ? 'Ada cerita di setiap frame.' : 'Perbaikan kecil. Konteks lebih jelas.'}</span>{step === 0 ? <Scan size={20} /> : <PencilLine size={20} />}</div>
      </> : <>
        <svg className="scene-network" viewBox="0 0 500 500" fill="none"><path pathLength="1" d="M75 160C150 160 160 225 250 225M420 220C350 220 340 225 250 225M250 225C250 300 290 340 380 360"/><circle cx="75" cy="160" r="5"/><circle cx="420" cy="220" r="5"/><circle cx="380" cy="360" r="5"/></svg>
        <div className="scene-evidence scene-evidence--video"><Film size={16} /><span>Rekaman</span></div><div className="scene-evidence scene-evidence--review"><PencilLine size={16} /><span>Koreksi</span></div>
        <div className="scene-connections">
          <div className="scene-orbit"><div className="scene-orbit-inner"><MessageCircle size={40} strokeWidth={1} /></div><span className="scene-orbit-dot"></span></div>
          <p>Lihat. Periksa.<br /><em>Pahami.</em></p>
          <div className="scene-source"><Film size={18} /><span>Rekaman</span><Link2 size={14} /><PencilLine size={18} /><span>Anotasi</span></div>
        </div>
        <div className="scene-bottomline"><span>Jawaban berawal dari sumber.</span><Link2 size={20} /></div>
      </>}
    </div>
  );
}

// CSS keeps the story readable before JavaScript; GSAP only enhances the visible landing.
function useLandingMotion() {
  useEffect(() => {
    const page = document.getElementById('landingPage');
    const content = page?.querySelector<HTMLElement>('.landing-scroll-content');
    if (!page || !content) return;
    gsap.registerPlugin(ScrollTrigger);
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    let cleanup: (() => void) | undefined;
    const stop = () => { cleanup?.(); cleanup = undefined; };
    const sync = () => {
      const active = !page.hidden && !reduced.matches && document.visibilityState === 'visible';
      if (!active) { stop(); return; }
      if (cleanup) return;
      const scroll = new Lenis({ wrapper: page, content, autoRaf: false, lerp: .14, overscroll: false, respectReducedMotion: true });
      const tick = (time: number) => scroll.raf(time * 1000);
      scroll.on('scroll', ScrollTrigger.update);
      gsap.ticker.add(tick);
      const media = gsap.matchMedia();
      const stage = page.querySelector<HTMLElement>('.landing-stage')!;
      const frame = stage.querySelector<HTMLElement>('.landing-stage-frame')!;
      const scenes = [...frame.querySelectorAll<HTMLElement>('.story-scene')];
      let story: gsap.core.Timeline;
      const update = () => { stage.dataset.phase = String(Math.min(2, Math.floor(story.time()))); };
      const choreography = gsap.context(() => {
        gsap.set(scenes, { opacity: 1 });
        gsap.set(scenes[2].querySelectorAll('.scene-evidence'), { opacity: 0 });
        story = gsap.timeline({ paused: true, defaults: { ease: 'power2.inOut' }, onUpdate: update });
        story.fromTo(scenes[0].querySelector('.scene-person--front'), { xPercent: -120, yPercent: 15, rotation: -8 }, { xPercent: 0, yPercent: 0, rotation: 0, duration: .8 }, 0)
          .fromTo(scenes[0].querySelector('.scene-person--back'), { xPercent: -80 }, { xPercent: 0, duration: .8 }, .05)
          .fromTo(scenes[0].querySelector('.scene-person--side'), { xPercent: 100, rotation: 8 }, { xPercent: 0, rotation: 0, duration: .8 }, .1)
          .fromTo(scenes[0].querySelectorAll('.scene-box'), { scaleX: .05, opacity: 0, transformOrigin: 'left center' }, { scaleX: 1, opacity: 1, stagger: .1, duration: .4 }, .35)
          .fromTo(scenes[0].querySelector('.scene-scan'), { y: () => -frame.clientHeight * .27 }, { y: () => frame.clientHeight * .27, ease: 'none', duration: 1 }, 0)
          .to(scenes[0].querySelectorAll('.scene-topline,.scene-bottomline'), { opacity: 0, duration: .15 }, .9)
          .to(scenes[0], { opacity: 0, duration: .15 }, 1.25)
          .fromTo(scenes[1], { clipPath: 'inset(0 0 100% 0)' }, { clipPath: 'inset(0 0 0% 0)', duration: .4 }, 1)
          .fromTo(scenes[1].querySelector('.scene-box--main'), { scaleX: .6, scaleY: .7, xPercent: 14, yPercent: 12 }, { scaleX: 1, scaleY: 1, xPercent: 0, yPercent: 0, duration: .5 }, 1.35)
          .fromTo(scenes[1].querySelector('.scene-cursor'), { x: 40, y: 36, scale: 1.2 }, { x: 0, y: 0, scale: 1, duration: .5 }, 1.35)
          .to(scenes[1].querySelector('.scene-before'), { opacity: 0, duration: .25 }, 1.7)
          .to(scenes[1].querySelectorAll('.scene-topline,.scene-bottomline'), { opacity: 0, duration: .15 }, 1.9)
          .to(scenes[1], { opacity: 0, duration: .15 }, 2.4)
          .fromTo(scenes[2], { clipPath: 'circle(0% at 50% 45%)' }, { clipPath: 'circle(100% at 50% 45%)', duration: .5 }, 2)
          .fromTo(scenes[2].querySelector('.scene-orbit'), { rotation: -160, scale: .4 }, { rotation: 0, scale: 1, duration: .65 }, 2.1)
          .fromTo(scenes[2].querySelector('.scene-network path'), { strokeDasharray: 1, strokeDashoffset: 1 }, { strokeDashoffset: 0, ease: 'none', duration: .5 }, 2.4)
          .fromTo(scenes[2].querySelectorAll('.scene-evidence'), { y: 28, opacity: 0, scale: .8 }, { y: 0, opacity: 1, scale: 1, stagger: .15, duration: .35 }, 2.45)
          .to({}, { duration: .05 }, 2.95);
        story.progress(.26);
        const xTo = gsap.quickTo(frame.querySelector('.story-focus-lens'), 'x', { duration: .35, ease: 'power3.out' });
        const yTo = gsap.quickTo(frame.querySelector('.story-focus-lens'), 'y', { duration: .35, ease: 'power3.out' });
        const panX = gsap.quickTo(frame.querySelectorAll('.scene-field,.scene-connections,.scene-network'), 'x', { duration: .7, ease: 'power3.out' });
        const panY = gsap.quickTo(frame.querySelectorAll('.scene-field,.scene-connections,.scene-network'), 'y', { duration: .7, ease: 'power3.out' });
        const move = (event: PointerEvent) => {
          if (event.pointerType !== 'mouse') return;
          const rect = frame.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top;
          xTo(x - 54); yTo(y - 54); panX((x / rect.width - .5) * 22); panY((y / rect.height - .5) * 16);
        };
        const leave = () => { panX(0); panY(0); };
        frame.addEventListener('pointermove', move); frame.addEventListener('pointerleave', leave);
        return () => { frame.removeEventListener('pointermove', move); frame.removeEventListener('pointerleave', leave); };
      }, stage);
      media.add('(min-width: 961px) and (min-height: 650px)', () => {
        ScrollTrigger.create({ animation: story, trigger: page.querySelector('.landing-chapters')!, scroller: page, start: 'top 65%', end: 'bottom 95%', scrub: .35, invalidateOnRefresh: true });
      }, page);
      const context = gsap.context(() => {
        page.querySelectorAll<HTMLElement>('[data-landing-reveal]').forEach(element => {
          gsap.from(element, { y: 22, duration: .75, ease: 'power2.out', scrollTrigger: { trigger: element, scroller: page, start: 'top 95%', toggleActions: 'play none none none' } });
        });
      }, page);
      ScrollTrigger.refresh();
      cleanup = () => { gsap.ticker.remove(tick); scroll.destroy(); context.revert(); media.revert(); choreography.revert(); delete stage.dataset.phase; };
    };
    const observer = new MutationObserver(sync);
    observer.observe(page, { attributes: true, attributeFilter: ['hidden'] });
    reduced.addEventListener('change', sync);
    document.addEventListener('visibilitychange', sync);
    window.addEventListener('pagehide', stop);
    window.addEventListener('pageshow', sync);
    sync();
    return () => { observer.disconnect(); reduced.removeEventListener('change', sync); document.removeEventListener('visibilitychange', sync); window.removeEventListener('pagehide', stop); window.removeEventListener('pageshow', sync); cleanup?.(); };
  }, []);
}


// Composition adapted from Editorial Collage Hero, Scroll 01 (felipemenezes098) and Navbar 1 (preetsuthar17), 21st.dev.
export function Landing() {
  useLandingMotion();
  return (
    <section id="landingPage" className="landing-page" aria-labelledby="landingTitle" hidden>
      <div className="landing-scroll-content">
      <a className="skip-link" href="#landingOverview">Lewati ke pengantar</a>
      <header className="landing-header">
        <a className="landing-brand" href="#landingOverview" aria-label="Video Insight, halaman awal">
          <img src="/assets/brand.svg" width="32" height="32" alt="" />
          <span>Video Insight<small>VIDEO ANALYSIS STUDIO</small></span>
        </a>
        <nav aria-label="Navigasi halaman awal">
          <a href="#landingOverview">Tentang</a>
          <a href="#landingWorkflow">Cara kerja</a>
        </nav>
        <a className="landing-login" href="#login">Masuk <ArrowUpRight size={16} aria-hidden="true" /></a>
      </header>
      <main id="landingOverview" className="landing-content">
        <div className="landing-hero">
          <div className="landing-copy">
            <p className="landing-eyebrow"><span aria-hidden="true"></span> RUANG UNTUK MELIHAT LEBIH DEKAT</p>
            <h1 id="landingTitle" tabIndex={-1}>Dari rekaman,<br /><em>jadi pemahaman.</em></h1>
            <p className="landing-description">Ada lebih banyak cerita di setiap rekaman. Temukan objek, periksa hasilnya, dan tanyakan apa yang ingin Anda pahami.</p>
            <div className="landing-actions">
              <a className="landing-primary" href="#login">Masuk ke studio <ArrowUpRight size={18} aria-hidden="true" /></a>
              <a className="landing-text-link" href="#landingWorkflow">Jelajahi alurnya <ArrowDown size={16} aria-hidden="true" /></a>
            </div>
            <p className="landing-local"><Monitor size={15} aria-hidden="true" /> Diproses di perangkat Anda.</p>
          </div>
          <div className="landing-collage" aria-label="Kolase ilustrasi, melihat detail dan memahami manusia">
            <figure className="landing-art-main">
              <div className="landing-art-top"><span>THE ART OF SEEING</span><span aria-hidden="true">01 — 02</span></div>
              <img src="/assets/creation-of-adam.webp" alt="Ilustrasi ASCII dua tangan yang saling mendekat." width="960" height="540" />
              <figcaption>Detail kecil.<br /><em>Cerita besar.</em></figcaption>
            </figure>
            <figure className="landing-art-people">
              <div className="landing-peeps" aria-hidden="true"><span></span><span></span><span></span></div>
              <figcaption><span>BEYOND THE FRAME</span><strong>Temukan<br />konteksnya.</strong></figcaption>
            </figure>
            <span className="landing-collage-note" aria-hidden="true">A different way to look.</span>
          </div>
        </div>
        <section id="landingWorkflow" className="landing-workflow" aria-labelledby="landingWorkflowTitle">
          <div className="landing-workflow-heading" data-landing-reveal>
            <p className="landing-eyebrow">DARI SATU VIDEO, KE SUDUT PANDANG BARU</p>
            <h2 id="landingWorkflowTitle">Lebih dari melihat.<br /><em>Belajar memahami.</em></h2>
            <p>Ikuti detailnya. Perbaiki yang terlewat.<br />Temukan pertanyaan yang tepat.</p>
          </div>
          <div className="landing-story">
            <div className="landing-stage" role="img" aria-label="Ilustrasi alur: mengamati rekaman, mengoreksi kotak, dan menelusuri sumber.">
              <div className="landing-stage-frame">{chapters.map((_, step) => <StoryScene step={step} key={step} />)}<div className="story-focus-lens" aria-hidden="true"><span></span></div></div>
            </div>
            <div className="landing-chapters">
              {chapters.map((chapter, step) => <article className="story-chapter" key={chapter.label} aria-labelledby={`landingChapter${step}`}>
                <div className="story-chapter-copy" data-landing-reveal>
                  <p className="landing-step"><chapter.icon size={18} aria-hidden="true" />{chapter.label}</p>
                  <h3 id={`landingChapter${step}`}>{chapter.title}</h3>
                  <p className="story-emphasis">{chapter.emphasis}</p>
                  <p className="story-description">{chapter.description}</p>
                  <p className="story-note"><span aria-hidden="true"></span>{chapter.note}</p>
                </div>
                <div className="landing-inline-scene"><StoryScene step={step} /><p className="landing-scene-note">Ilustrasi alur · bukan hasil analisis</p></div>
              </article>)}
            </div>
          </div>
        </section>
        <section id="landingQuestions" className="landing-questions" aria-labelledby="landingQuestionsTitle">
          <div className="landing-question-heading" data-landing-reveal><p className="landing-eyebrow">MULAI DARI RASA INGIN TAHU</p><h2 id="landingQuestionsTitle">Satu pertanyaan.<br /><em>Sudut pandang baru.</em></h2><p>Tak harus tahu istilah teknis.<br />Mulai dengan hal yang ingin Anda pahami.</p></div>
          <ol className="landing-question-list">
            <li data-landing-reveal><span>01 / GAMBARAN BESAR</span><p>“Ringkas hasil video ini.”</p><MoveUpRight size={26} strokeWidth={1} aria-hidden="true" /></li>
            <li data-landing-reveal><span>02 / SATU MOMEN</span><p>“Berapa orang di detik 3?”</p><MoveUpRight size={26} strokeWidth={1} aria-hidden="true" /></li>
            <li data-landing-reveal><span>03 / LIHAT LEBIH TELITI</span><p>“Apakah ada kandidat tanpa helm?”</p><MoveUpRight size={26} strokeWidth={1} aria-hidden="true" /></li>
          </ol>
          <p className="landing-question-note"><Link2 size={16} aria-hidden="true" />Contoh pertanyaan. Jawaban bergantung pada rekaman dan hasil analisis Anda.</p>
        </section>
        <section className="landing-closing" aria-label="Mulai menggunakan studio" data-landing-reveal>
          <p className="landing-eyebrow">GILIRAN ANDA MELIHAT LEBIH DEKAT</p><h2>Ceritanya sudah ada.<br /><em>Mari temukan bersama.</em></h2>
          <a className="landing-primary" href="#login">Mulai dari satu video <ArrowUpRight size={18} aria-hidden="true" /></a>
        </section>
        <footer className="landing-footer"><p>Video Insight <span>· Workspace lokal</span></p><p>Amati. Koreksi. Pahami.</p></footer>
      </main>
      </div>
    </section>
  );
}

export function AccountGate() {
  useEffect(() => {
    const gate = document.getElementById('authGate');
    const video = document.querySelector<HTMLVideoElement>('.auth-art video');
    if (!gate || !video) return;
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => {
      if (gate.hidden || reduced.matches || document.visibilityState !== 'visible') { video.pause(); return; }
      if (!video.getAttribute('src')) video.src = '/assets/creation-of-adam.mp4';
      void video.play().catch(() => {}); // Poster remains usable when autoplay is unavailable.
    };
    const observer = new MutationObserver(sync);
    observer.observe(gate, {attributes: true, attributeFilter: ['hidden']});
    reduced.addEventListener('change', sync);
    document.addEventListener('visibilitychange', sync);
    sync();
    return () => { observer.disconnect(); reduced.removeEventListener('change', sync); document.removeEventListener('visibilitychange', sync); video.pause(); };
  }, []);
  return (
    <>
    <div id="loginTransitionLoader" className="login-transition-loader" hidden>
          <div className="loader-heading"><svg viewBox="0 0 256 256" className="brand-mark" aria-hidden="true"><path fill="currentColor" d="M32 40h40l56 128 56-128h40l-80 176h-32zM112 40h32v64h-32z"/></svg><span>VIDEO INSIGHT</span></div>
          <h1>Menyiapkan studio Anda.</h1>
          <p id="loginTransitionStatus" role="status">Memuat rekaman dan pengaturan workspace…</p>
          <canvas id="loginCrowdCanvas" width="1440" height="600" aria-hidden="true"></canvas>
          <button id="loginTransitionRetry" className="button button--primary" type="button" hidden>Coba lagi</button>
        </div>
    <section id="authGate" className="auth-gate" aria-labelledby="loginTitle" hidden>
          <a className="auth-back" href="#landingOverview"><span aria-hidden="true">←</span> Kembali ke halaman awal</a>
          <div className="auth-art" aria-hidden="true"><video poster="/assets/creation-of-adam.webp" muted loop playsInline preload="none" tabIndex={-1}></video></div>
          <div className="auth-story"><p className="eyebrow">DARI REKAMAN MENJADI PEMAHAMAN</p><h2>Lihat lebih dekat.<br />Pahami lebih banyak.</h2></div>
          <form id="loginForm" className="auth-card auth-card-modern">
            <div className="auth-logo"><svg viewBox="0 0 256 256" className="brand-mark" aria-hidden="true"><path fill="currentColor" d="M32 40h40l56 128 56-128h40l-80 176h-32zM112 40h32v64h-32z"/></svg></div>
            <p className="eyebrow">VIDEO INSIGHT STUDIO</p>
            <h1 id="loginTitle">Selamat datang kembali.</h1>
            <p className="auth-intro">Rekaman, koreksi, dan insight. Dalam satu workspace.</p>
            <label htmlFor="loginUsername">Username</label>
            <input className="input" id="loginUsername" autoComplete="username" required maxLength={80} placeholder="Username akun Anda" />
            <label htmlFor="loginPassword">Password</label>
            <div className="password-field">
              <input className="input" id="loginPassword" type="password" autoComplete="current-password" required maxLength={256} placeholder="Masukkan password" />
              <button type="button" id="toggleLoginPassword" className="password-toggle-eye" aria-label="Tampilkan password" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg></button>
            </div>
            <p id="loginError" className="error" role="alert" hidden></p>
            <button id="loginSubmit" className="button button--primary" type="submit">Masuk ke studio <span aria-hidden="true">→</span></button>
            <p className="auth-account-help">Belum punya akun? Hubungi administrator workspace.</p>
            <details><summary>Akses pertama di perangkat ini</summary><p>Administrator dapat membuat akun melalui <code>uv run python access.py init --username owner</code>. Password diisi secara interaktif.</p></details>
          </form>
          <p className="auth-footnote">Workspace lokal · Data tetap di perangkat Anda</p>
        </section>
    </>
  );
}

export function Profile() {
  return (
    <section
              id="profilePane"
              className="profile-page"
              aria-labelledby="profileTitle"
              hidden
            >
              <button
                id="profileBack"
                className="button button--tertiary button--sm"
                type="button"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="m14 5-7 7 7 7" />
                </svg>
                Kembali ke studio
              </button>
              <header className="profile-heading">
                <span
                  id="profileAvatar"
                  className="avatar avatar--large"
                  aria-hidden="true"
                ></span>
                <div>
                  <p className="profile-kicker">AKUN WORKSPACE</p>
                  <h1 id="profileTitle" tabIndex={-1}>Profil pengguna</h1><p id="profileDisplayName"></p>
                </div>
              </header>
              <section className="profile-section" aria-labelledby="personalTitle">
                <div className="profile-section-heading"><h2 id="personalTitle">Profil Anda</h2><p>Nama dan foto yang ditampilkan di studio.</p></div>
                <div className="personal-fields">
                  <label htmlFor="profileNameInput">Nama tampilan</label>
                  <div className="profile-name-edit"><input className="input" id="profileNameInput" maxLength={80} required placeholder="Nama lengkap atau panggilan" /><button className="button button--secondary" id="saveNameBtn" type="button">Simpan</button></div>
                  <p id="nameSaveStatus" className="hint" role="status"></p>
                  <label className="photo-upload" htmlFor="avatarFileInput">Foto profil<input id="avatarFileInput" type="file" accept="image/jpeg,image/png,image/webp" /></label>
                  <div className="photo-help"><span className="hint">JPG, PNG, WebP · maksimal 2 MB / 4 MP</span><button id="removeAvatarBtn" type="button" className="button button--tertiary button--sm">Hapus foto</button></div>
                  <p id="avatarStatus" className="hint" role="status"></p>
                </div>
              </section>
              <section className="profile-section" aria-labelledby="identityTitle">
                <div className="profile-section-heading">
                  <h2 id="identityTitle">Identitas</h2>
                  <p>Akses Anda pada workspace ini.</p>
                </div>
                <dl className="identity-list">
                  <div>
                    <dt>Username</dt>
                    <dd id="profileUsername"></dd>
                  </div>
                  <div>
                    <dt>Workspace</dt>
                    <dd id="profileWorkspace"></dd>
                  </div>
                  <div>
                    <dt>Peran</dt>
                    <dd id="profileRole"></dd>
                  </div>
                </dl>
              </section>
              <section className="profile-section" aria-labelledby="passwordTitle">
                <div className="profile-section-heading">
                  <h2 id="passwordTitle">Password &amp; keamanan</h2>
                  <p id="passwordHelp">
                    Setelah diperbarui, sesi lain akan keluar. Rekaman Anda tetap
                    terbuka.
                  </p>
                </div>
                <form id="passwordForm">
                  <label htmlFor="currentPassword">Password saat ini</label
                  ><div className="password-field"><input
                    className="input"
                    id="currentPassword"
                    type="password"
                    autoComplete="current-password"
                    maxLength={256}
                    required
                  /><button type="button" className="password-toggle-eye" data-password-target="currentPassword" aria-label="Tampilkan password" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg></button></div>
                  <label htmlFor="newPassword">Password baru</label
                  ><div className="password-field"><input
                    className="input"
                    id="newPassword"
                    type="password"
                    autoComplete="new-password"
                    minLength={12}
                    maxLength={256}
                    aria-describedby="passwordLength"
                    required
                  /><button type="button" className="password-toggle-eye" data-password-target="newPassword" aria-label="Tampilkan password" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg></button></div>
                  <p id="passwordLength" className="hint">
                    Minimal 12 karakter. Gunakan password yang unik.
                  </p>
    <div id="passwordMeter" className="password-meter" role="meter" aria-label="Kekuatan password baru" aria-valuemin={0} aria-valuemax={4} aria-valuenow={0} aria-valuetext="Kosong"><div className="password-meter-bars"><span className="password-meter-cell"><span className="password-meter-fill"></span></span><span className="password-meter-cell"><span className="password-meter-fill"></span></span><span className="password-meter-cell"><span className="password-meter-fill"></span></span><span className="password-meter-cell"><span className="password-meter-fill"></span></span></div><div className="password-meter-status"><span className="password-meter-label">Kosong</span><span className="password-meter-common" hidden>Pola mudah ditebak</span></div></div><ul className="password-rules-list"><li id="ruleLen" className="password-rule-item"><span className="password-rule-icon" aria-hidden="true">○</span>12+ karakter</li><li id="ruleCase" className="password-rule-item"><span className="password-rule-icon" aria-hidden="true">○</span>Huruf besar & kecil</li><li id="ruleDigit" className="password-rule-item"><span className="password-rule-icon" aria-hidden="true">○</span>Angka</li><li id="ruleSymbol" className="password-rule-item"><span className="password-rule-icon" aria-hidden="true">○</span>Simbol</li></ul><p id="passwordStrengthAnnouncement" className="sr-only" aria-live="polite"></p>
                  <label htmlFor="confirmPassword">Ulangi password baru</label
                  ><div className="password-field"><input
                    className="input"
                    id="confirmPassword"
                    type="password"
                    autoComplete="new-password"
                    minLength={12}
                    maxLength={256}
                    required
                  /><button type="button" className="password-toggle-eye" data-password-target="confirmPassword" aria-label="Tampilkan password" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg></button></div>
                  <p
                    id="passwordStatus"
                    role="status"
                    aria-live="polite"
                    aria-atomic="true"
                  ></p>
                  <button
                    id="passwordSubmit"
                    className="button button--primary"
                    type="submit"
                  >
                    Simpan password
                  </button>
                </form>
              </section>
              <section className="profile-section" aria-labelledby="appearanceTitle"><div className="profile-section-heading"><h2 id="appearanceTitle">Tampilan</h2><p>Pilih tema atau ikuti perangkat.</p></div><div><label htmlFor="themeSelect">Tema studio</label><select id="themeSelect" className="select__trigger"><option value="system">Ikuti sistem</option><option value="light">Terang</option><option value="dark">Gelap</option></select></div></section>
              <section
                className="profile-section profile-signout"
                aria-labelledby="signoutTitle"
              >
                <div className="profile-section-heading">
                  <h2 id="signoutTitle">Sesi perangkat ini</h2>
                  <p>Keluar dari akun setelah selesai bekerja.</p>
                </div>
                <button
                  id="logoutButton"
                  className="button button--outline"
                  type="button"
                >
                  Keluar dari akun
                </button>
              </section>
            </section>
  );
}
