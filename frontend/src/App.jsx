import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const LoadingOverlay = ({ status }) => (
  <div className="loading-overlay">
    <div className="waveform">{[...Array(8)].map((_, i) => <span key={i} />)}</div>
    <div className="loading-overlay-title">
      {status === 'generating' ? '🎤 Componiendo Voces con YuE 7B...' : '⚡ Enviando a Madrid...'}
    </div>
    <div className="loading-overlay-sub">
      La RTX 5080 está procesando tu solicitud.<br />
      {status === 'generating' ? 'Las voces tardan 2-3 minutos. ¡No cierres esta ventana!' : 'Conectando con el servidor...'}
    </div>
  </div>
);

const Toast = ({ msg, type }) => <div className={`toast ${type}`}>{msg}</div>;

const MODELS = [
  { id: 'yue', name: 'YuE 7B', badge: 'Letra + Voz', desc: 'Voces cantadas reales desde tu letra. El modelo estrella de DocuMusic.', className: 'yue' },
  { id: 'ace-step', name: 'ACE-Step 1.5', badge: 'Control fino', desc: 'Control avanzado sobre el audio. Ideal para ajustes de producción.', className: 'ace' },
];

export default function App() {
  const [model, setModel] = useState('yue');
  const [serverStatus, setServerStatus] = useState(null);
  const [lyrics, setLyrics] = useState('');
  const [stylePrompt, setStylePrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [genStatus, setGenStatus] = useState('idle');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  useEffect(() => {
    const check = () => axios.get('/api/').then(r => setServerStatus(r.data)).catch(() => setServerStatus({ gpu: 'Offline', status: 'Disconnected' }));
    check();
    const t = setInterval(check, 15000);
    return () => clearInterval(t);
  }, []);

  const pollJob = (jobId) => {
    const iv = setInterval(async () => {
      try {
        const res = await axios.get(`/api/job/${jobId}`);
        if (res.data.status === 'done') {
          clearInterval(iv);
          setResult(prev => ({ ...prev, audio_url: res.data.audio_url }));
          setLoading(false);
          setGenStatus('done');
          showToast('✅ ¡Canción con voces lista!');
        } else if (res.data.status === 'error') {
          clearInterval(iv);
          setLoading(false);
          setGenStatus('idle');
          setError('Error en la generación: ' + res.data.error);
          showToast('❌ Error en YuE', 'error');
        }
      } catch (e) { /* silencio */ }
    }, 5000);
  };

  const handleGenerate = async () => {
    if (!lyrics.trim()) { showToast('⚠️ Escribe la letra primero', 'error'); return; }
    setLoading(true);
    setResult(null);
    setError(null);
    setGenStatus('processing');
    showToast('⚡ Enviando a Madrid...');
    try {
      const res = await axios.post('/api/generate', { lyrics, style_prompt: stylePrompt, model });
      setResult(res.data);
      if (res.data.model_status === 'generating') {
        setGenStatus('generating');
        pollJob(res.data.job_id);
      } else {
        setLoading(false);
        setGenStatus('done');
      }
    } catch (e) {
      setLoading(false);
      setGenStatus('idle');
      setError('Error al conectar con el servidor de Madrid.');
      showToast('❌ Error de conexión', 'error');
    }
  };

  const isOnline = serverStatus?.status === 'Online' || (serverStatus && serverStatus.gpu !== 'Offline');
  const audioSrc = result?.audio_url ? (result.audio_url.startsWith('http') ? result.audio_url : `/api${result.audio_url}`) : null;

  return (
    <div className="app">
      {loading && <LoadingOverlay status={genStatus} />}
      {toast && <Toast msg={toast.msg} type={toast.type} />}

      {/* ---- HEADER ---- */}
      <header>
        <div className="logo"><div className="logo-icon">♪</div> DocuMusic</div>
        <div className="gpu-status">
          <div className={`status-indicator ${isOnline ? 'active' : ''}`}>
            <span className="status-dot"></span>
            {serverStatus ? `${serverStatus.gpu} · ${serverStatus.vram_free || '--'} VRAM` : 'Conectando...'}
          </div>
        </div>
      </header>

      <main>
        {/* ---- SELECTOR DE MODELO ---- */}
        <p className="section-title">Motor de Generación</p>
        <div className="model-selector">
          {MODELS.map(m => (
            <div key={m.id} className={`model-card ${m.className} ${model === m.id ? 'selected' : ''}`} onClick={() => setModel(m.id)}>
              <span className={`model-badge ${m.className}`}>{m.badge}</span>
              <div className="model-name">{m.name}</div>
              <div className="model-desc">{m.desc}</div>
            </div>
          ))}
        </div>

        {/* ---- LYRICS (estilo Suno) ---- */}
        <div className="suno-block">
          <div className="suno-block-header">
            <span className="suno-block-icon">🎵</span>
            <span className="suno-block-title">Lyrics</span>
            <span className="suno-block-hint">Usa [Verse] y [Chorus] para estructurar</span>
          </div>
          <textarea
            className="suno-textarea"
            rows="12"
            placeholder={"[Verse]\nEscribe tu letra aquí...\n\n[Chorus]\nEl coro va aquí...\n\n[Bridge]\nPuente opcional...\n\nDeja en blanco para instrumental."}
            value={lyrics}
            onChange={e => setLyrics(e.target.value)}
          />
        </div>

        {/* ---- STYLE (texto libre, como Suno) ---- */}
        <div className="suno-block">
          <div className="suno-block-header">
            <span className="suno-block-icon">🎸</span>
            <span className="suno-block-title">Style of Music</span>
            <span className="suno-block-hint">Describe género, voz, instrumentos y más</span>
          </div>
          <textarea
            className="suno-textarea style-textarea"
            rows="3"
            placeholder={"Ejemplos:\n• American Country, alternating male and female voices, acoustic guitar, fiddle\n• Latin Pop, female vocalist, upbeat, trumpet, piano\n• Rock ballad, powerful male voice, electric guitar solo, emotional"}
            value={stylePrompt}
            onChange={e => setStylePrompt(e.target.value)}
          />
          <div className="style-suggestions">
            {[
              'male voice',
              'female voice',
              'male & female duet',
              'choir',
              'acoustic guitar',
              'piano ballad',
              'electric guitar',
              'American Country',
              'Latin Pop',
              'Rock',
              'Jazz, saxophone',
              'Cinematic',
            ].map(s => (
              <span key={s} className="chip" onClick={() => setStylePrompt(p => p ? p + ', ' + s : s)}>+ {s}</span>
            ))}
          </div>
        </div>

        {/* ---- BOTÓN GENERAR ---- */}
        <button className="generate-btn" onClick={handleGenerate} disabled={loading || !isOnline}>
          {loading ? '🎼 Procesando en Madrid (2-3 min)...' : '🎵 Crear Canción'}
        </button>

        {/* ---- ERROR ---- */}
        {error && <div className="error-panel">⚠️ {error}</div>}

        {/* ---- RESULTADO ---- */}
        {result && (
          <div className="result-panel">
            <div className="result-header">
              <div className="result-title">🎵 Resultado</div>
              <span className="result-meta">RTX 5080 · {model === 'yue' ? 'YuE 7B' : 'ACE-Step 1.5'}</span>
            </div>

            {result.message && (
              <p style={{ fontSize: '0.82rem', color: 'var(--text-dim)', marginBottom: 16 }}>{result.message}</p>
            )}

            {audioSrc ? (
              <div className="audio-card">
                <audio controls src={audioSrc} className="audio-player" autoPlay />
                <div style={{ marginTop: 14 }}>
                  <a href={audioSrc} download="documusic.mp3" className="download-btn">
                    ⬇ Descargar MP3
                  </a>
                </div>
              </div>
            ) : (
              <div className="pending-audio">
                ⏳ <strong>Generando voces en Madrid...</strong><br />
                El reproductor aparecerá automáticamente cuando esté lista.
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
