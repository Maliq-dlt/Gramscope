import { VideoPanel } from './VideoPanel';
import { Annotation } from './Annotation';
import { ChatPanel } from './ChatPanel';

export function Workspace() {
  return (
    <div id="videoWorkspace">
              <div className="page-heading studio-heading">
                <div>
                  <p className="workspace-kicker">STUDIO VIDEO</p>
                  <h1 id="workspaceTitle" tabIndex={-1}>Analisis rekaman</h1><p className="studio-subtitle">Lihat yang terjadi. Koreksi yang terlewat.</p>
                </div>
                <button
                  className="button button--primary"
                  id="newVideoButton"
                  type="button"
                >
                  <span aria-hidden="true">＋</span> Video baru
                </button>
              </div>
              <div className="source-bar">
                <div className="source-history">
                  <label htmlFor="historySelect">Rekaman</label
                  ><select className="select__trigger" id="historySelect">
                    <option value="">Belum ada video</option>
                  </select>
                </div>

                <details className="analysis-settings">
                  <summary>Pengaturan analisis</summary>
                  <div className="settings-content">
                    <div className="source-device">
                      <label htmlFor="deviceMode">Perangkat AI</label
                      ><select className="select__trigger" id="deviceMode">
                        <option value="auto">Auto · GPU jika tersedia</option>
                        <option value="cpu">CPU</option>
                        <option value="cuda">GPU NVIDIA · fallback CPU</option>
                      </select>
                    </div>

                    <div className="model-bar">
                      <label htmlFor="analysisModel">Model deteksi</label
                      ><select id="analysisModel" className="select__trigger">
                        <option value="">YOLO dasar · pretrained</option></select
                      ><button
                        className="button button--outline button--sm"
                        id="reanalyzeButton"
                        type="button"
                      >
                        Analisis ulang
                      </button>
                      <p className="hint" id="modelHelp">Hasil lama tetap tersimpan.</p>
                    </div>

                    <p className="system" id="systemStatus" role="status">
                      Memeriksa model…
                    </p>
                  </div>
                </details>
              </div>
              <div id="learningProgress" className="progress-area" hidden>
                <div id="learningProcessView" className="process-view"></div>
                <progress
                  id="learningProgressBar" className="sr-only" aria-hidden="true"
                  max="100"
                  value="0"
                  aria-label="Kemajuan belajar dan analisis ulang"
                ></progress>
                <p id="learningStatus" role="status" aria-live="polite"></p>
                <button
                  id="cancelLearning"
                  className="button button--outline button--sm"
                  type="button"
                  hidden
                >
                  Batalkan belajar</button
                ><button
                  id="showLearnedResult"
                  className="button button--secondary button--sm"
                  type="button"
                  hidden
                >
                  Lihat analisis baru
                </button>
              </div>
              <div id="progressArea" className="progress-area" hidden>
                <div id="jobProcessView" className="process-view"></div>
                <progress
                  id="jobProgress" className="sr-only" aria-hidden="true"
                  max="100"
                  value="0"
                  aria-label="Kemajuan analisis"
                ></progress>
                <p id="jobStatus" role="status" aria-live="polite"></p>
                <button
                  id="cancelJob"
                  className="button button--outline button--sm"
                  type="button"
                  hidden
                >
                  Batalkan analisis</button
                ><button
                  id="retryJob"
                  className="button button--secondary button--sm"
                  type="button"
                  hidden
                >
                  Coba lagi dari upload
                </button>
              </div>
              <div id="exportProgress" className="progress-area" hidden>
                <progress
                  id="exportProgressBar"
                  max="100"
                  value="0"
                  aria-label="Kemajuan ekspor"
                ></progress>
                <p id="exportStatus" role="status" aria-live="polite"></p>
                <button
                  id="cancelExport"
                  className="button button--outline button--sm"
                  type="button"
                  hidden
                >
                  Batalkan ekspor
                </button>
              </div>
              <p className="error" id="uploadError" role="alert" hidden></p>
              <div className="work-grid">
                <div className="work-main">
                  <VideoPanel />

                  <Annotation />
                </div>
                <ChatPanel />
              </div>
            </div>
  );
}
