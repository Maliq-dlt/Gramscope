import { AccountGate, Landing, Profile } from './Account';
import { Workspace } from './Workspace';
import { NgramLab } from './NgramLab';

export function App() {
 return (<>
   <Landing />
   <AccountGate />
   <a className="skip-link" href="#mainContent">Lewati navigasi</a>
   <Sidebar />
   <div className="app-shell">
     <Header />
     <main id="mainContent">
       <p id="authError" className="error" role="alert" hidden />
       <Workspace />
       <Profile />
       <div id="ngramPane" hidden><NgramLab /></div>
     </main>
   </div>
   <UploadDialog />
 </>);
}

export function Sidebar() {
  return (
    <aside className="sidebar" aria-label="Navigasi dashboard">
          <a className="brand" href="/"><svg viewBox="0 0 256 256" className="brand-mark" aria-hidden="true"><path fill="currentColor" d="M32 40h40l56 128 56-128h40l-80 176h-32zM112 40h32v64h-32z"/></svg><span>Video Insight<small>VIDEO ANALYSIS STUDIO</small></span></a>
          <p className="nav-label">WORKSPACE</p>
          <nav>
            <button
              className="button nav-item"
              data-view="analysis"
              aria-current="page"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="3" y="3" width="7" height="7" rx="1" />
                <rect x="14" y="3" width="7" height="7" rx="1" />
                <rect x="3" y="14" width="7" height="7" rx="1" />
                <rect x="14" y="14" width="7" height="7" rx="1" /></svg
              >Analisis video
            </button>
            <button className="button nav-item" data-view="evidence">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 4h16v16H4zM4 15l5-5 4 4 3-3 4 4" />
                <circle cx="16" cy="8" r="1" /></svg
              >Bukti &amp; hasil
            </button>
            <button className="button nav-item" data-view="annotation">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5M9 9h6v6H9z" /></svg
              >Anotasi manual
            </button>
            <button className="button nav-item" data-view="ngram"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h16v16H4zM8 8h8M8 12h5M8 16h8" /></svg>Chatbot N-gram</button>
          </nav>
          <div className="sidebar-bottom">
            <span className="local-dot"></span> Semua data di perangkat ini<span
              className="sidebar-foot"
              >Portofolio lokal / v0.1</span
            >
          </div>
        </aside>
  );
}

export function Header() {
  return (
    <header className="topbar">
            <div className="breadcrumb">
              Workspace <span>/</span>
              <strong id="pageTitle">Analisis video</strong>
            </div>
            <div className="topbar-tools">
    <button id="themeToggleBtn" className="theme-toggle-btn" type="button" role="switch" aria-checked="false" aria-label="Mode gelap" title="Ganti tema">
     <span className="theme-toggle-track" aria-hidden="true"><svg className="theme-icon-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4"/></svg><svg className="theme-icon-moon" viewBox="0 0 24 24"><path d="M20 15A8.5 8.5 0 0 1 9 4a8.5 8.5 0 1 0 11 11Z"/></svg><span className="theme-toggle-thumb"></span></span></button>
              <button
                id="profileButton"
                className="profile-trigger"
                type="button"
                aria-label="Buka profil pengguna"
              >
                <span
                  id="accountAvatar"
                  className="avatar avatar--small"
                  aria-hidden="true"
                ></span>
                <span id="accountIdentity" className="account-identity"></span>
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="m9 5 7 7-7 7" />
                </svg>
              </button>
            </div>
          </header>
  );
}

export function UploadDialog() {
  return (
    <dialog id="uploadDialog" aria-labelledby="uploadTitle">
          <div className="dialog-head">
            <div>
              <span className="eyebrow">SUMBER REKAMAN</span>
              <h2 id="uploadTitle">Analisis video baru</h2>
            </div>
            <button
              className="button button--tertiary button--sm"
              id="closeUpload"
              type="button"
              aria-label="Tutup upload"
            >
              ✕
            </button>
          </div>
          <div id="uploadProcessView" className="process-view" hidden></div>
          <p id="uploadTransferStatus" className="hint" role="status" hidden></p>
          <form id="uploadForm">
            <label htmlFor="videoFile">Pilih rekaman</label>
            <div className="file-box">
              <input
                id="videoFile"
                name="file"
                type="file"
                accept=".mp4,.mov,.avi,.mkv,.webm,.m4v"
                required
                aria-describedby="uploadHelp"
              />
            </div>
            <p className="hint" id="uploadHelp">
              <span id="uploadLimits">MP4, MOV, AVI, MKV, WEBM, M4V · maks. 250 MiB, 2 menit, 4K.</span>
            </p>
            <details className="count-settings">
              <summary>Garis counting</summary>
              <label htmlFor="countLine"
                >Posisi garis:
                <output id="lineValue" htmlFor="countLine">50%</output></label
              ><input
                id="countLine"
                name="line"
                type="range"
                min="10"
                max="90"
                defaultValue="50"
              />
              <p className="hint">
                Pusat kotak melewati garis untuk mencatat lintasan.
              </p>
            </details>
            <p className="hint">
              Menggunakan perangkat yang dipilih di dashboard. Auto memilih RTX 4060
              saat VRAM cukup, dengan fallback CPU.
            </p>
            <button className="button button--primary" id="uploadButton" type="submit">
              Analisis video
            </button>
          </form>
        </dialog>
  );
}
