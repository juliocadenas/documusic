import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const LoadingOverlay = ({ status, logs, numVariants, completedVariants }) => {
  const consoleRef = React.useRef(null);
  
  React.useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [logs]);

  const progress = numVariants > 0 ? Math.round((completedVariants / numVariants) * 100) : 0;

  return (
    <div className="loading-overlay">
      <div className="loading-content">
        <div className="waveform">{[...Array(8)].map((_, i) => <span key={i} />)}</div>
        <div className="loading-overlay-title">
          {status === 'generating' ? `🎤 Generando en Madrid (YuE 7B)...` : '⚡ Conectando con RTX 5080...'}
        </div>
        <div className="loading-overlay-sub">
          {status === 'generating' 
            ? `${numVariants} variante(s) · ${completedVariants}/${numVariants} completada(s) · Esto suele tardar 2-5 minutos`
            : 'Preparando entorno de ejecución...'}
        </div>
        
        {numVariants > 0 && (
          <div style={{ width: '80%', margin: '12px auto', background: 'rgba(255,255,255,0.1)', borderRadius: 8, height: 6, overflow: 'hidden' }}>
            <div style={{ width: `${progress}%`, height: '100%', background: 'linear-gradient(90deg, #6366f1, #a855f7)', borderRadius: 8, transition: 'width 0.5s ease' }} />
          </div>
        )}
        
        <div className="progress-console" ref={consoleRef}>
          {logs && logs.length > 0 ? (
            logs.slice(-30).map((log, i) => (
              <div key={i} className={`console-line ${log.includes('ERROR') || log.includes('error') || log.includes('❌') ? 'error-line' : ''} ${log.includes('✅') || log.includes('🏆') ? 'success-line' : ''}`}>
                <span className="console-prompt">{'>'}</span> {log}
              </div>
            ))
          ) : (
            <div className="console-line waiting">Esperando logs del servidor...</div>
          )}
        </div>
      </div>
    </div>
  );
};

const Toast = ({ msg, type }) => <div className={`toast ${type}`}>{msg}</div>;

const MODELS = [
  { id: 'yue', name: 'YuE 7B', badge: 'Letra + Voz', desc: 'Voces cantadas reales desde tu letra. El modelo estrella de DocuMusic.', className: 'yue' },
  { id: 'ace-step', name: 'ACE-Step 1.5', badge: 'Control fino', desc: 'Control avanzado sobre el audio. Ideal para ajustes de producción.', className: 'ace' },
];

const VariantCard = ({ variant, isSelected, onSelect, jobPrefix }) => {
  const audioUrl = variant.audio_url 
    ? (variant.audio_url.startsWith('http') ? variant.audio_url : `/api${variant.audio_url}`)
    : null;
  
  return (
    <div className={`variant-card ${isSelected ? 'selected' : ''} ${!audioUrl ? 'failed' : ''}`} onClick={onSelect}>
      <div className="variant-header">
        <span className="variant-label">V{variant.index + 1}</span>
        {variant.is_best_copy && <span className="variant-badge best">🏆 Best</span>}
        {!audioUrl && <span className="variant-badge failed">Failed</span>}
      </div>
      {audioUrl ? (
        <div className="variant-content">
          <audio controls src={audioUrl} className="variant-player" preload="none" />
          <div className="variant-meta">
            <span>⏱ {variant.duration?.toFixed(1) || '?'}s</span>
            <span>🔊 {variant.lufs?.toFixed(1) || '?'} LUFS</span>
            <span>🎲 seed: {variant.seed}</span>
          </div>
          <a href={audioUrl} download={`documusic_v${variant.index + 1}.mp3`} className="download-btn-sm" onClick={e => e.stopPropagation()}>
            ⬇ MP3
          </a>
        </div>
      ) : (
        <div className="variant-error">
          <span>❌ {variant.error || 'Generation failed'}</span>
        </div>
      )}
    </div>
  );
};

export default function App() {
  const [model, setModel] = useState('yue');
  const [serverStatus, setServerStatus] = useState(null);
  const [lyrics, setLyrics] = useState('');
  const [stylePrompt, setStylePrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [genStatus, setGenStatus] = useState('idle');
  const [logs, setLogs] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [errorDetail, setErrorDetail] = useState(null);
  const [toast, setToast] = useState(null);
  const [numVariants, setNumVariants] = useState(2);
  const [completedVariants, setCompletedVariants] = useState(0);
  const [gpuAlert, setGpuAlert] = useState(null);       // 🐕 Watchdog alert
  const [enrichedPreview, setEnrichedPreview] = useState(null); // 🎨 Enriched prompt preview
  const [selectedVariant, setSelectedVariant] = useState(0);
  const [variants, setVariants] = useState([]);

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

  // 🐕 GPU Watchdog — poll every 5s for alerts
  useEffect(() => {
    const checkGpu = () => {
      axios.get('/api/gpu').then(r => {
        const gpu = r.data;
        if (gpu.status === 'critical') {
          setGpuAlert({ level: 'critical', message: gpu.block_reason || 'GPU crítica', alerts: gpu.alerts || [] });
        } else if (gpu.status === 'warning') {
          const latestAlert = gpu.alerts?.[0];
          if (latestAlert) {
            setGpuAlert({ level: 'warning', message: latestAlert.message, alerts: gpu.alerts || [] });
          }
        } else {
          setGpuAlert(null);
        }
      }).catch(() => {});
    };
    checkGpu();
    const t = setInterval(checkGpu, 5000);
    return () => clearInterval(t);
  }, []);

  // 🎨 Prompt Enrichment preview — when user stops typing
  useEffect(() => {
    if (!stylePrompt.trim()) { setEnrichedPreview(null); return; }
    const timer = setTimeout(() => {
      axios.post('/api/enrich-preview', { style_prompt: stylePrompt })
        .then(r => setEnrichedPreview(r.data))
        .catch(() => setEnrichedPreview(null));
    }, 800); // Debounce 800ms
    return () => clearTimeout(timer);
  }, [stylePrompt]);

  const pollJob = (jobId) => {
    const iv = setInterval(async () => {
      try {
        const res = await axios.get(`/api/job/${jobId}`);
        if (res.data.logs && res.data.logs.length > 0) setLogs(res.data.logs);
        if (res.data.completed_variants !== undefined) setCompletedVariants(res.data.completed_variants);
        
        if (res.data.status === 'done') {
          clearInterval(iv);
          setResult(prev => ({ 
            ...prev, 
            audio_url: res.data.audio_url,
            variants: res.data.variants || [],
            best_variant: res.data.best_variant,
          }));
          setVariants(res.data.variants || []);
          setSelectedVariant(res.data.best_variant || 0);
          setGenStatus('done');
          setLoading(false);
          showToast(`✅ ¡Canción lista! ${res.data.variants?.length || 1} variante(s) generada(s)`);
        } else if (res.data.status === 'error') {
          clearInterval(iv);
          setGenStatus('idle');
          setLoading(false);
          const errMsg = res.data.error || 'Error desconocido';
          const detail = res.data.error_detail || '';
          setLogs(prev => [...(res.data.logs || prev), `❌ ERROR: ${errMsg}`]);
          setError('Error en la generación: ' + errMsg);
          setErrorDetail(detail);
          showToast('❌ Error en YuE', 'error');
        }
      } catch (e) { /* silencio */ }
    }, 1500);
  };

  const handleGenerate = async () => {
    if (!lyrics.trim()) { showToast('⚠️ Escribe la letra primero', 'error'); return; }
    setLoading(true);
    setResult(null);
    setError(null);
    setErrorDetail(null);
    setVariants([]);
    setCompletedVariants(0);
    setGenStatus('processing');
    showToast('⚡ Enviando a Madrid...');
    try {
      const res = await axios.post('/api/generate', { 
        lyrics, 
        style_prompt: stylePrompt, 
        model,
        num_variants: numVariants,
      });
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
  
  // Get the audio source for the primary player
  const getAudioSrc = () => {
    if (variants.length > 0 && variants[selectedVariant]?.audio_url) {
      const url = variants[selectedVariant].audio_url;
      return url.startsWith('http') ? url : `/api${url}`;
    }
    if (result?.audio_url) {
      return result.audio_url.startsWith('http') ? result.audio_url : `/api${result.audio_url}`;
    }
    return null;
  };
  const audioSrc = getAudioSrc();

  return (
    <div className="app">
      {loading && <LoadingOverlay status={genStatus} logs={logs} numVariants={numVariants} completedVariants={completedVariants} />}
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
          {/* 🎨 Enriched prompt preview */}
          {enrichedPreview && enrichedPreview.enriched !== enrichedPreview.original && (
            <div className="enriched-preview">
              <div className="enriched-label">🎨 Prompt enriquecido automáticamente:</div>
              <div className="enriched-text">{enrichedPreview.enriched}</div>
            </div>
          )}
        </div>

        {/* 🐕 GPU WATCHDOG ALERT */}
        {gpuAlert && (
          <div className={`gpu-alert ${gpuAlert.level}`}>
            <span className="gpu-alert-icon">{gpuAlert.level === 'critical' ? '🔴' : '🟡'}</span>
            <span className="gpu-alert-text">🐕 {gpuAlert.message}</span>
          </div>
        )}

        {/* ---- VARIANT SELECTOR ---- */}
        <div className="suno-block">
          <div className="suno-block-header">
            <span className="suno-block-icon">🎲</span>
            <span className="suno-block-title">Variants</span>
            <span className="suno-block-hint">Genera múltiples versiones y elige la mejor</span>
          </div>
          <div className="variant-selector">
            {[1, 2, 3].map(n => (
              <button 
                key={n} 
                className={`variant-btn ${numVariants === n ? 'selected' : ''}`}
                onClick={() => setNumVariants(n)}
              >
                {n === 1 ? '1 variante' : `${n} variantes`}
                {n > 1 && <span className="variant-time">~{2 + (n - 1) * 2} min</span>}
              </button>
            ))}
          </div>
          {numVariants > 1 && (
            <div className="variant-hint">
              Cada variante usa una semilla aleatoria diferente. Se selecciona automáticamente la mejor.
            </div>
          )}
        </div>

        {/* ---- BOTÓN GENERAR ---- */}
        <button className="generate-btn" onClick={handleGenerate} disabled={loading || !isOnline}>
          {loading 
            ? `🎼 Procesando en Madrid (${completedVariants}/${numVariants} variantes)...` 
            : `🎵 Crear Canción${numVariants > 1 ? ` (${numVariants} variantes)` : ''}`}
        </button>

        {/* ---- ERROR ---- */}
        {error && (
          <div className="error-panel">
            <div>⚠️ {error}</div>
            {errorDetail && (
              <details style={{ marginTop: 8, fontSize: '0.78rem', opacity: 0.85 }}>
                <summary style={{ cursor: 'pointer' }}>Ver detalles del error</summary>
                <pre style={{ marginTop: 6, whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto' }}>
                  {errorDetail}
                </pre>
              </details>
            )}
          </div>
        )}

        {/* ---- RESULTADO ---- */}
        {result && (
          <div className="result-panel">
            <div className="result-header">
              <div className="result-title">🎵 Resultado</div>
              <span className="result-meta">
                RTX 5080 · {model === 'yue' ? 'YuE 7B' : 'ACE-Step 1.5'} · 
                {variants.length > 0 ? ` ${variants.length} variante(s)` : ' Masterizado'}
              </span>
            </div>

            {result.message && (
              <p style={{ fontSize: '0.82rem', color: 'var(--text-dim)', marginBottom: 16 }}>{result.message}</p>
            )}

            {audioSrc ? (
              <div className="audio-card">
                <audio controls src={audioSrc} className="audio-player" autoPlay />
                <div style={{ marginTop: 14, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <a href={audioSrc} download={`documusic_v${selectedVariant + 1}.mp3`} className="download-btn">
                    ⬇ Descargar MP3
                  </a>
                  {variants.length > 1 && variants[selectedVariant] && (
                    <span className="download-meta">
                      V{selectedVariant + 1} · {variants[selectedVariant]?.duration?.toFixed(1)}s · 
                      {variants[selectedVariant]?.lufs?.toFixed(1)} LUFS
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <div className="pending-audio">
                <div className="loading-overlay-title" style={{ fontSize: '1rem', marginBottom: 12 }}>
                  🎤 Generando {numVariants} variante(s) en Madrid...
                </div>
                <div className="progress-console">
                  {logs && logs.length > 0 ? (
                    logs.slice(-20).map((log, i) => (
                      <div key={i} className={`console-line ${log.includes('ERROR') || log.includes('error') || log.includes('❌') ? 'error-line' : ''} ${log.includes('✅') || log.includes('🏆') ? 'success-line' : ''}`}>
                        <span className="console-prompt">{'>'}</span> {log}
                      </div>
                    ))
                  ) : (
                    <div className="console-line waiting">Iniciando motor YuE 7B...</div>
                  )}
                </div>
              </div>
            )}

            {/* ---- VARIANTES ---- */}
            {variants.length > 1 && (
              <div className="variants-section">
                <div className="variants-title">🎨 Variantes generadas</div>
                <div className="variants-grid">
                  {variants.map((v, i) => (
                    <VariantCard 
                      key={i} 
                      variant={v} 
                      isSelected={selectedVariant === i}
                      onSelect={() => setSelectedVariant(i)}
                      jobPrefix={result.job_id}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
