import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// ---- LOADING OVERLAY ----
const LoadingOverlay = () => (
  <div className="loading-overlay">
    <div className="waveform">{[...Array(8)].map((_, i) => <span key={i} />)}</div>
    <div className="loading-overlay-title">Generando con YuE 7B...</div>
    <div className="loading-overlay-sub">La RTX 5080 de Madrid está procesando tu solicitud.</div>
  </div>
);

const Toast = ({ msg, type }) => <div className={`toast ${type}`}>{msg}</div>;

export default function App() {
  const [serverStatus, setServerStatus] = useState(null);
  const [lyrics, setLyrics] = useState('');
  const [stylePrompt, setStylePrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  useEffect(() => {
    axios.get('/api/')
      .then(r => setServerStatus(r.data))
      .catch(() => setServerStatus({ gpu: 'Offline', status: 'Disconnected' }));
  }, []);

  const handleGenerate = async () => {
    if (!lyrics.trim()) { showToast('⚠️ Escribe una letra primero', 'error'); return; }
    setLoading(true);
    setResult(null);
    setError(null);
    showToast('⚡ Enviando a Madrid...');
    try {
      const res = await axios.post('/api/generate', {
        lyrics,
        style_prompt: stylePrompt,
        mode: 'exact'
      });
      setResult(res.data);
      showToast('✅ ¡Composición lista!');
    } catch (e) {
      setError('Error al conectar con Madrid. Verifica el servidor.');
      showToast('❌ Error de conexión', 'error');
    } finally {
      setLoading(false);
    }
  };

  const isOnline = serverStatus?.status === 'Online' || (serverStatus && serverStatus.gpu !== 'Offline');

  return (
    <div className="app">
      {loading && <LoadingOverlay />}
      {toast && <Toast msg={toast.msg} type={toast.type} />}

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
        {/* ---- LETRA ---- */}
        <div className="suno-block">
          <div className="suno-block-header">
            <span className="suno-block-icon">🎵</span>
            <span className="suno-block-title">Lyrics</span>
            <span className="suno-block-hint">Escribe la letra completa de tu canción</span>
          </div>
          <textarea
            className="suno-textarea"
            rows="10"
            placeholder={"[Verse]\nWrite your lyrics here...\n\n[Chorus]\nSing the chorus...\n\n[Bridge]\nThe bridge goes here...\n\nDeja en blanco para instrumental"}
            value={lyrics}
            onChange={e => setLyrics(e.target.value)}
          />
        </div>

        {/* ---- ESTILOS (texto libre) ---- */}
        <div className="suno-block">
          <div className="suno-block-header">
            <span className="suno-block-icon">🎸</span>
            <span className="suno-block-title">Style of Music</span>
            <span className="suno-block-hint">Describe el estilo, voces e instrumentos en detalle</span>
          </div>
          <textarea
            className="suno-textarea style-textarea"
            rows="4"
            placeholder={"Ejemplos:\n• American Country, alternating male and female voices, acoustic guitar, fiddle, steel guitar, emotional ballad\n• Latin Pop, female vocalist, trumpet, piano, upbeat tempo, romantic\n• Classical orchestral, choir, violins, dramatic, cinematic soundtrack"}
            value={stylePrompt}
            onChange={e => setStylePrompt(e.target.value)}
          />
          {/* Chips de sugerencias rápidas */}
          <div className="style-suggestions">
            {[
              'male vocalist, guitar',
              'female vocalist, piano',
              'male & female duet',
              'choir, orchestral',
              'American Country',
              'Latin Pop',
              'Rock, electric guitar',
              'Jazz, saxophone, smoky',
            ].map(s => (
              <span key={s} className="chip" onClick={() => setStylePrompt(p => p ? p + ', ' + s : s)}>+ {s}</span>
            ))}
          </div>
        </div>

        {/* ---- BOTÓN CREAR ---- */}
        <button className="generate-btn" onClick={handleGenerate} disabled={loading || !isOnline}>
          {loading ? '🎼 Procesando en Madrid...' : '🎵 Crear Canción'}
        </button>

        {/* ---- ERROR ---- */}
        {error && <div className="error-panel">⚠️ {error}</div>}

        {/* ---- RESULTADO ---- */}
        {result && (
          <div className="result-panel">
            <div className="result-header">
              <div className="result-title">🎵 Composición Lista</div>
              <span className="result-meta">RTX 5080 · YuE 7B</span>
            </div>

            {result.generated_lyrics && (
              <div style={{ marginBottom: 20 }}>
                <p className="result-label">LETRA GENERADA</p>
                <pre className="lyrics-box">{result.generated_lyrics}</pre>
              </div>
            )}

            {result.audio_url ? (
              <div className="audio-card">
                <audio
                  controls
                  src={result.audio_url.startsWith('http') ? result.audio_url : `/api${result.audio_url}`}
                  className="audio-player"
                />
                <a
                  href={result.audio_url.startsWith('http') ? result.audio_url : `/api${result.audio_url}`}
                  download="documusic.mp3"
                  className="download-btn"
                >
                  ⬇ Descargar MP3
                </a>
              </div>
            ) : (
              <div className="pending-audio">
                🎵 <strong>Audio en preparación:</strong> El modelo YuE necesita descargarse en Madrid.<br />
                <code>huggingface-cli download mradermacher/YuE-7B-GGUF YuE-7B.Q4_K_M.gguf --local-dir ~/AI_MODELS/YuE-7B</code>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
