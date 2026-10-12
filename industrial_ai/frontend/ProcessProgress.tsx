// Progress Bar and Task Steps adapted from ddoemonn on 21st.dev; native CSS motion.
export interface ProcessState {
 kind: 'upload' | 'analysis' | 'training' | 'reanalysis';
 status: string;
 value: number | null;
 title?: string;
}
const steps = {
 upload: ['Mengirim video', 'Memeriksa rekaman', 'Siap dianalisis'],
 analysis: ['Rekaman diterima', 'Menyiapkan video', 'Mendeteksi & mengikuti objek', 'Menyimpan hasil'],
 training: ['Menyiapkan koreksi', 'Melatih detektor', 'Menyimpan model'],
 reanalysis: ['Model hasil koreksi siap', 'Menganalisis ulang', 'Menyimpan hasil baru']
};
const titles = {upload: 'Mengunggah rekaman', analysis: 'Menganalisis rekaman', training: 'Belajar dari koreksi', reanalysis: 'Menerapkan hasil belajar'};
export function processStage(state: ProcessState): number {
 if (state.status === 'done') return steps[state.kind].length;
 if (state.kind === 'upload') return state.status === 'validating' ? 1 : 0;
 if (state.kind === 'training') return (state.value ?? 0) < 5 ? 0 : 1;
 // Backend reports preparation below 5, tracking up to 90, and final output at 94.
 if (state.kind === 'reanalysis') return (state.value ?? 0) < 94 ? 1 : 2;
 return (state.value ?? 0) < 5 ? 1 : (state.value ?? 0) < 94 ? 2 : 3;
}
export function ProcessProgress(state: ProcessState) {
 const failed = ['error', 'cancelled', 'interrupted'].includes(state.status);
 const paused = failed || state.status === 'waiting' || state.status === 'cancelling';
 const complete = state.status === 'done';
 const value = state.value === null ? null : Math.max(0, Math.min(complete ? 100 : 99, state.value));
 const stage = processStage(state);
 const readout = complete ? 'Selesai' : state.status === 'cancelled' ? 'Dibatalkan' : failed ? 'Terhenti' : state.status === 'waiting' ? 'Menunggu koreksi' : state.status === 'cancelling' ? 'Membatalkan…' : value === null ? 'Memproses…' : `${Math.round(value)}%`;
 return <div className="process-progress" data-state={paused ? 'paused' : complete ? 'done' : 'active'}>
  <div className="process-heading"><strong>{state.title || titles[state.kind]}</strong><span>{readout}</span></div>
  <div className={`process-track${value === null && !paused ? ' indeterminate' : ''}`} role="progressbar" aria-label={state.title || titles[state.kind]} aria-valuemin={0} aria-valuemax={100} aria-valuenow={value ?? undefined} aria-valuetext={readout}>
   <span className="process-fill" style={{transform: `scaleX(${value === null ? .35 : value / 100})`}} />
  </div>
  <ol className="task-steps" aria-label="Langkah proses">
   {steps[state.kind].map((label, index) => {
    const status = index < stage ? 'done' : index === stage ? (failed ? 'error' : paused ? 'waiting' : 'active') : 'pending';
    return <li key={label} data-state={status} aria-current={status === 'active' ? 'step' : undefined}>
     <span className="task-icon" aria-hidden="true">{status === 'done' ? '✓' : status === 'error' ? '×' : <i />}</span>
     <span>{label}</span><span className="sr-only"> · {({done:'selesai', error:'terhenti', waiting:'menunggu', active:'berjalan', pending:'belum dimulai'})[status]}</span>
    </li>;
   })}
  </ol>
 </div>;
}
