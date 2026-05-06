import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './App.css';

// ---- ICONOS INLINE (sin dependencias extra) ----
const Icon = ({ d, size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);
const MusicIcon = () => <Icon d="M9 18V5l12-2v13M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zm12-2a3 3 0 1 1-6 0 3 3 0 0 1 6 0z" />;
const ZapIcon = () => <Icon d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />;
const UploadIcon = () => <Icon d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" />;
const SpinIcon = () => <Icon d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />;
const PenIcon = () => <Icon d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />;
const LayersIcon = () => <Icon d="M12 2l10 6.5v7L12 22 2 15.5v-7L12 2zM12 22v-6.5M22 8.5l-10 7-10-7" />;
const LightbulbIcon = () => <Icon d="M9 18h6M10 22h4M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17H8v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z" />;

// ---- MODELOS DISPONIBLES ----
const MODELS = [
  {
    id: 'yue',
    name: 'YuE 7B',
    badge: 'Letra + Voz',
    desc: 'Genera canciones completas: letra, melodía y voz. Ideal para producción creativa desde cero.',
    className: 'yue',
  },
  {
    id: 'ace-step',
    name: 'ACE-Step 1.5',
    badge: 'Control fino',
    desc: 'Control avanzado sobre el audio generado. Ideal para respetar letras exactas con precisión.',
    className: 'ace',
  },
];

// ---- GÉNEROS MUSICALES ----
const GENRES = ['Pop', 'Rock', 'Electronic', 'Jazz', 'Cinematic', 'Lo-Fi', 'Reggaeton', 'Classical', 'Hip-Hop', 'Cumbia'];

export default function App() {
  const [model, setModel] = useState('yue');
  const [mode, setMode] = useState('creative'); // creative | exact | factory
  const [serverStatus, setServerStatus] = useState(null);

  // Modo Creativo
  const [idea, setIdea] = useState('');
  const [style, setStyle] = useState('');
  const [genre, setGenre] = useState('Cinematic');

  // Modo Exacto
  const [exactLyrics, setExactLyrics] = useState('');
  const [exactGenre, setExactGenre] = useState('Pop');

  // Modo Fábrica
  const [wordFile, setWordFile] = useState(null);
  const [batchQueue, setBatchQueue] = useState([]);
  const [dragover, setDragover] = useState(false);
  const fileInputRef = useRef(null);

  // Estado de generación
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Consultar estado del servidor via proxy de Vite
  useEffect(() => {
    axios.get('/api/')
      .then(r => setServerStatus(r.data))
      .catch(() => setServerStatus({ gpu_name: 'Offline', gpu_status: 'Disconnected', vram_total: '--' }));
  }, []);

  // ---- HANDLERS ----
  const handleGenerate = async () => {
    setLoading(true);
    setProgress(0);
    setResult(null);
    setError(null);

    // Simulación de progreso mientras se genera
    const interval = setInterval(() => {
      setProgress(p => Math.min(p + Math.random() * 8, 90));
    }, 800);

    try {
      let payload = { model };

      if (mode === 'creative') {
        payload = { ...payload, mode: 'creative', prompt: idea, style, genre };
      } else if (mode === 'exact') {
        payload = { ...payload, mode: 'exact', lyrics: exactLyrics, genre: exactGenre };
      }

      const res = await axios.post('/api/generate', payload);
      setProgress(100);
      setResult(res.data);
    } catch (e) {
      setError('Error al conectar con el servidor de Madrid. Verifica que el contenedor esté activo.');
    } finally {
      clearInterval(interval);
      setLoading(false);
    }
  };

  const handleFileDrop = (e) => {
    e.preventDefault();
    setDragover(false);
    const file = e.dataTransfer?.files[0] || e.target.files[0];
    if (file) {
      setWordFile(file);
      // Simular parsing del Word para mostrar cola
      setBatchQueue([
        { id: 1, title: 'Canción 1 (del Word)', status: 'pending' },
        { id: 2, title: 'Canción 2 (del Word)', status: 'pending' },
        { id: 3, title: 'Canción 3 (del Word)', status: 'pending' },
      ]);
    }
  };

  const handleBatchProcess = async () => {
    setLoading(true);
    for (let i = 0; i < batchQueue.length; i++) {
      setBatchQueue(q => q.map((item, idx) =>
        idx === i ? { ...item, status: 'processing' } : item
      ));
      await new Promise(r => setTimeout(r, 3000)); // Simulación por item
      setBatchQueue(q => q.map((item, idx) =>
        idx === i ? { ...item, status: 'done' } : item
      ));
    }
    setLoading(false);
  };

  const isOnline = serverStatus?.gpu_status !== 'Disconnected';

  return (
    <div className="app">
      {/* ---- HEADER ---- */}
      <header>
        <div className="logo">
          <div className="logo-icon">♪</div>
          DocuMusic
        </div>
        <div className="gpu-status">
          <div className={`gpu-dot ${isOnline ? 'online' : ''}`} />
          {isOnline
            ? `${serverStatus?.gpu_name} · ${serverStatus?.vram_total} VRAM`
            : 'Servidor Offline'}
        </div>
      </header>

      <main>
        {/* ---- SELECTOR DE MODELO ---- */}
        <p className="section-title">Motor de Generación</p>
        <div className="model-selector">
          {MODELS.map(m => (
            <div
              key={m.id}
              className={`model-card ${m.className} ${model === m.id ? 'selected' : ''}`}
              onClick={() => setModel(m.id)}
            >
              <span className={`model-badge ${m.className}`}>{m.badge}</span>
              <div className="model-name">{m.name}</div>
              <div className="model-desc">{m.desc}</div>
            </div>
          ))}
        </div>

        {/* ---- SELECTOR DE MODALIDAD ---- */}
        <p className="section-title">Modalidad de Composición</p>
        <div className="mode-tabs">
          <button className={`mode-tab ${mode === 'creative' ? 'active' : ''}`} onClick={() => setMode('creative')}>
            <LightbulbIcon /> Modo Creativo
          </button>
          <button className={`mode-tab ${mode === 'exact' ? 'active' : ''}`} onClick={() => setMode('exact')}>
            <PenIcon /> Letra Exacta
          </button>
          <button className={`mode-tab ${mode === 'factory' ? 'active' : ''}`} onClick={() => setMode('factory')}>
            <LayersIcon /> Fábrica por Lotes
          </button>
        </div>

        {/* ======== MODO CREATIVO ======== */}
        {mode === 'creative' && (
          <div className="panel">
            <div className="form-group">
              <label>Tu Idea Musical</label>
              <textarea
                rows="4"
                placeholder="Describe tu visión: una melodía de piano melancólica con sintetizadores espaciales que evocan soledad en una ciudad nocturna..."
                value={idea}
                onChange={e => setIdea(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>Estilo Musical Libre</label>
              <textarea
                rows="2"
                placeholder="Ej: Influenciado por Hans Zimmer, tempo lento, acordes menores, ambiente cinematográfico..."
                value={style}
                onChange={e => setStyle(e.target.value)}
              />
              <div className="style-chips">
                {GENRES.map(g => (
                  <span key={g} className={`chip ${genre === g ? 'active' : ''}`} onClick={() => setGenre(g)}>
                    {g}
                  </span>
                ))}
              </div>
            </div>
            <button className="generate-btn" onClick={handleGenerate} disabled={loading || !idea || !isOnline}>
              {loading ? <><span className="spin"><SpinIcon /></span> Generando...</> : <><ZapIcon /> Generar Composición</>}
            </button>
          </div>
        )}

        {/* ======== MODO LETRA EXACTA ======== */}
        {mode === 'exact' && (
          <div className="panel">
            <div className="form-group">
              <label>Letra Exacta (el modelo la respetará al 100%)</label>
              <textarea
                rows="10"
                placeholder={"Escribe aquí la letra completa de la canción.\n\n[Verso 1]\nEscribe tu letra...\n\n[Coro]\nEscribe el coro..."}
                value={exactLyrics}
                onChange={e => setExactLyrics(e.target.value)}
                style={{ fontFamily: 'monospace', fontSize: '0.9rem' }}
              />
            </div>
            <div className="form-group">
              <label>Género Musical</label>
              <select value={exactGenre} onChange={e => setExactGenre(e.target.value)}>
                {GENRES.map(g => <option key={g}>{g}</option>)}
              </select>
            </div>
            <button className="generate-btn" onClick={handleGenerate} disabled={loading || !exactLyrics || !isOnline}>
              {loading ? <><span className="spin"><SpinIcon /></span> Musicalizando Letra...</> : <><MusicIcon /> Musicalizar Letra Exacta</>}
            </button>
          </div>
        )}

        {/* ======== MODO FÁBRICA ======== */}
        {mode === 'factory' && (
          <div className="panel">
            <p className="section-title">Cargar Archivo Word</p>
            <div
              className={`upload-zone ${dragover ? 'dragover' : ''}`}
              onDragOver={e => { e.preventDefault(); setDragover(true); }}
              onDragLeave={() => setDragover(false)}
              onDrop={handleFileDrop}
              onClick={() => fileInputRef.current.click()}
            >
              <div className="upload-icon">📄</div>
              <div className="upload-text">
                {wordFile ? `✅ ${wordFile.name}` : 'Arrastra tu archivo Word aquí'}
              </div>
              <div className="upload-hint">
                El Word debe contener las letras separadas por secciones y el estilo de cada canción
              </div>
              <input type="file" ref={fileInputRef} accept=".docx,.doc" onChange={handleFileDrop} style={{ display: 'none' }} />
            </div>

            {batchQueue.length > 0 && (
              <>
                <div className="batch-queue">
                  {batchQueue.map(item => (
                    <div key={item.id} className="batch-item">
                      <span>{item.title}</span>
                      <span className={`batch-status ${item.status}`}>
                        {item.status === 'pending' && 'En Cola'}
                        {item.status === 'processing' && '⚡ Procesando...'}
                        {item.status === 'done' && '✅ Completado'}
                      </span>
                    </div>
                  ))}
                </div>
                <button
                  className="generate-btn"
                  onClick={handleBatchProcess}
                  disabled={loading || !isOnline}
                  style={{ marginTop: 20 }}
                >
                  {loading
                    ? <><span className="spin"><SpinIcon /></span> Procesando Lote...</>
                    : <><LayersIcon /> Iniciar Proceso en Fábrica</>}
                </button>
              </>
            )}
          </div>
        )}

        {/* ---- PROGRESO ---- */}
        {loading && (
          <div className="progress-container">
            <div className="progress-label">
              <span>Generando en la RTX 5080 de Madrid...</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        {/* ---- ERROR ---- */}
        {error && (
          <div className="result-panel" style={{ borderColor: '#ef4444' }}>
            <p style={{ color: '#f87171', fontSize: '0.9rem' }}>⚠️ {error}</p>
          </div>
        )}

        {/* ---- RESULTADO ---- */}
        {result && (
          <div className="result-panel">
            <div className="result-header">
              <div className="result-title">
                <MusicIcon /> Composición Lista
              </div>
              <span className="result-meta">Modelo: {model.toUpperCase()}</span>
            </div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-dim)', marginBottom: 16 }}>
              {result.message}
            </p>
            {result.audio_url && (
              <audio controls className="audio-player" src={result.audio_url}>
                Tu navegador no soporta audio HTML5.
              </audio>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
