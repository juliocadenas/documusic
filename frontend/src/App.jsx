import { useState, useEffect } from 'react'
import './App.css'

const API = 'http://localhost:8000'

// ─── Engine cards config ────────────────────────────────────────────────────
const ENGINE_META = {
  'yue': {
    color: '#7c3aed',
    glow: 'rgba(124, 58, 237, 0.4)',
    icon: '🎤',
    badge: 'VOCALS · ESTRUCTURA · HI-FI',
  },
  'ace-step': {
    color: '#db2777',
    glow: 'rgba(219, 39, 119, 0.4)',
    icon: '⚡',
    badge: 'FULL SONG · 10 MIN · APACHE 2.0',
  },
}

export default function App() {
  const [mode, setMode] = useState('idea')
  const [status, setStatus] = useState('')
  const [queue, setQueue] = useState([])
  const [library, setLibrary] = useState([])
  const [form, setForm] = useState({ title: '', style: '', lyrics: '', idea: '' })
  const [engines, setEngines] = useState([])
  const [activeEngine, setActiveEngine] = useState(null)
  const [gpuInfo, setGpuInfo] = useState(null)
  const [switching, setSwitching] = useState(false)
  const [activeTab, setActiveTab] = useState('studio') // 'studio' | 'library'

  // ── Cargar estado inicial ──────────────────────────────────────────────────
  useEffect(() => {
    fetchEngines()
    fetchGpuStatus()
    fetchLibrary()

    const gpuInterval = setInterval(fetchGpuStatus, 5000)
    return () => clearInterval(gpuInterval)
  }, [])

  // ── Polling de progreso ────────────────────────────────────────────────────
  useEffect(() => {
    const active = queue.filter(i => i.status !== 'completed' && i.status !== 'error')
    if (!active.length) return

    const interval = setInterval(async () => {
      const updated = await Promise.all(queue.map(async item => {
        if (item.status === 'completed' || item.status === 'error') return item
        try {
          const res = await fetch(`${API}/progress/${item.id}`)
          const data = await res.json()
          if (data.status === 'completed') fetchLibrary()
          return data.status !== 'not_found' ? { ...item, ...data } : item
        } catch { return item }
      }))
      setQueue(updated)
    }, 2000)

    return () => clearInterval(interval)
  }, [queue])

  async function fetchEngines() {
    try {
      const res = await fetch(`${API}/engines/`)
      const data = await res.json()
      setEngines(data.engines || [])
      setActiveEngine(data.active)
    } catch { /* backend offline */ }
  }

  async function fetchGpuStatus() {
    try {
      const res = await fetch(`${API}/engines/status/`)
      const data = await res.json()
      setGpuInfo(data)
    } catch { /* backend offline */ }
  }

  async function fetchLibrary() {
    try {
      const res = await fetch(`${API}/library/`)
      const data = await res.json()
      setLibrary(data.songs || [])
    } catch { /* backend offline */ }
  }

  async function handleSwitchEngine(engineId) {
    if (switching || engineId === activeEngine) return
    setSwitching(true)
    setStatus(`Cambiando al motor ${engineId.toUpperCase()}... liberando VRAM...`)

    try {
      const res = await fetch(`${API}/engines/switch/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ engine: engineId }),
      })
      const data = await res.json()
      setActiveEngine(engineId)
      setStatus(`✅ Motor ${engineId.toUpperCase()} activo y listo.`)
      fetchGpuStatus()
    } catch (e) {
      setStatus(`❌ Error al cambiar de motor: ${e.message}`)
    } finally {
      setSwitching(false)
    }
  }

  async function handleGenerate(e) {
    e.preventDefault()
    if (!activeEngine) { setStatus('⚠️ Selecciona un motor de IA antes de generar.'); return }
    setStatus('Enviando a la cola de producción...')

    try {
      let response
      if (mode === 'bulk') {
        const fileInput = document.querySelector('input[type="file"]')
        const fd = new FormData()
        fd.append('file', fileInput.files[0])
        response = await fetch(`${API}/bulk-generate/`, { method: 'POST', body: fd })
      } else {
        response = await fetch(`${API}/generate-song/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: form.title || 'Sin título',
            style: form.style || 'Pop',
            lyrics: mode === 'idea' ? form.idea : form.lyrics,
          }),
        })
      }

      const data = await response.json()
      if (data.song_id) {
        setQueue([{ id: data.song_id, title: form.title || 'Nueva Canción', status: 'queued', percent: 0, engine: activeEngine }, ...queue])
        setStatus(`🎵 Canción encolada con motor ${activeEngine.toUpperCase()}.`)
      } else if (data.songs_found) {
        setStatus(`📦 ${data.songs_found} canciones en cola.`)
      } else if (data.detail) {
        setStatus(`⚠️ ${data.detail}`)
      }
    } catch (err) {
      setStatus(`❌ Error: ${err.message}`)
    }
  }

  const handleInput = e => setForm({ ...form, [e.target.name]: e.target.value })

  // ─── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="app-container">

      {/* HEADER */}
      <header>
        <div className="logo">DOCUMUSIC <span>FACTORY</span></div>
        <div className="header-right">
          {gpuInfo?.gpu_name && (
            <div className="gpu-pill">
              <span className="gpu-dot"></span>
              {gpuInfo.gpu_name} · {gpuInfo.vram_used_gb}GB / {gpuInfo.vram_total_gb}GB VRAM
            </div>
          )}
          <div className="tabs">
            {['studio', 'library'].map(t => (
              <button key={t} className={`tab-btn ${activeTab === t ? 'active' : ''}`} onClick={() => setActiveTab(t)}>
                {t === 'studio' ? '🎛️ Studio' : '📚 Librería'}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* ENGINE SELECTOR */}
      <section className="engine-selector">
        <h3 className="section-label">Motor de IA Activo</h3>
        <div className="engine-grid">
          {engines.map(eng => {
            const meta = ENGINE_META[eng.id] || {}
            const isActive = eng.id === activeEngine
            return (
              <div
                key={eng.id}
                className={`engine-card ${isActive ? 'engine-active' : ''} ${switching ? 'engine-switching' : ''}`}
                style={{ '--engine-color': meta.color, '--engine-glow': meta.glow }}
                onClick={() => handleSwitchEngine(eng.id)}
              >
                <div className="engine-icon">{meta.icon}</div>
                <div className="engine-info">
                  <strong>{eng.id.toUpperCase()}</strong>
                  <span className="engine-badge">{meta.badge}</span>
                  <small>{eng.description}</small>
                </div>
                <div className="engine-specs">
                  <span>💾 {eng.capabilities.vram_gb_required}GB VRAM</span>
                  {eng.capabilities.vocals && <span>🎤 Voces</span>}
                  {eng.capabilities.structure_aware && <span>📋 Estructura</span>}
                  <span>⏱ {eng.capabilities.max_duration_min} min</span>
                </div>
                {isActive && <div className="engine-active-indicator">ACTIVO {switching ? '⟳' : '✓'}</div>}
              </div>
            )
          })}
        </div>
        {status && <div className="status-box">{status}</div>}
      </section>

      {/* STUDIO TAB */}
      {activeTab === 'studio' && (
        <main className="dashboard-grid">
          {/* Form */}
          <section className="panel">
            <h2 style={{ marginBottom: '1.5rem' }}>
              {mode === 'idea' ? '💡 Nueva Creación' : mode === 'lyrics' ? '📝 Editor de Producción' : '📦 Carga Industrial'}
            </h2>

            <div className="mode-tabs">
              {[['idea', '💡 Idea'], ['lyrics', '📝 Letra'], ['bulk', '📦 Masivo']].map(([m, label]) => (
                <button key={m} className={`mode-btn ${mode === m ? 'mode-active' : ''}`} onClick={() => setMode(m)}>{label}</button>
              ))}
            </div>

            <form onSubmit={handleGenerate} style={{ marginTop: '1.5rem' }}>
              {mode !== 'bulk' && (
                <div className="form-group">
                  <label>Título del Proyecto</label>
                  <input name="title" type="text" placeholder="Ej: Atardecer en el Cosmos" value={form.title} onChange={handleInput} />
                </div>
              )}
              <div className="form-group">
                <label>{mode === 'bulk' ? 'Archivo .docx' : 'Estilo y Mood'}</label>
                {mode === 'bulk'
                  ? <input type="file" accept=".docx" required />
                  : <input name="style" type="text" placeholder="Ej: Melodic Techno, 128bpm, ethereal pads" value={form.style} onChange={handleInput} />
                }
              </div>
              {mode === 'idea' && (
                <div className="form-group">
                  <label>Concepto Creativo</label>
                  <textarea name="idea" rows="5" placeholder="Describe de qué trata la canción..." value={form.idea} onChange={handleInput}></textarea>
                </div>
              )}
              {mode === 'lyrics' && (
                <div className="form-group">
                  <label>Script (usa [Verse], [Chorus], [Bridge])</label>
                  <textarea name="lyrics" rows="10" placeholder={`[Verse 1]\nLetra aquí...\n\n[Chorus]\nEstribillo aquí...`} value={form.lyrics} onChange={handleInput}></textarea>
                </div>
              )}
              <button type="submit" className="btn generate-btn" disabled={!activeEngine || switching}>
                {!activeEngine ? 'Selecciona un motor primero' : mode === 'bulk' ? '⚡ PROCESAR FACTORÍA' : '🎵 INICIAR GENERACIÓN'}
              </button>
            </form>
          </section>

          {/* Monitor */}
          <section className="panel">
            <h2 style={{ marginBottom: '1.5rem' }}>📡 Monitor de Producción</h2>

            <div className="audio-preview-mock">
              <div className="visualizer-bars">
                {[...Array(24)].map((_, i) => (
                  <div key={i} className={`v-bar ${queue.some(q => q.status === 'generating_audio') ? 'v-bar-active' : ''}`}
                    style={{ animationDelay: `${i * 0.04}s` }}></div>
                ))}
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '1.2rem' }}>
                {queue.length > 0 ? `Procesando en ${activeEngine?.toUpperCase()}...` : 'Esperando señal...'}
              </p>
            </div>

            <div className="queue-list">
              {queue.length === 0 && (
                <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem 0' }}>
                  La cola está vacía.
                </p>
              )}
              {queue.map(item => (
                <div key={item.id} className="queue-item">
                  <div style={{ flex: 1 }}>
                    <div className="queue-item-header">
                      <strong>{item.title}</strong>
                      <span className={`badge badge-${item.status === 'completed' ? 'done' : item.status === 'error' ? 'error' : 'proc'}`}>
                        {item.engine ? `[${item.engine}] ` : ''}{item.status}
                      </span>
                    </div>
                    {item.current_section && (
                      <small style={{ color: 'var(--primary)', fontSize: '0.72rem' }}>↪ {item.current_section}</small>
                    )}
                    <div className="progress-bar-bg">
                      <div className="progress-bar-fill" style={{ width: `${item.percent || 0}%` }}></div>
                    </div>
                    <small style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>{item.percent || 0}% · ID: {item.id}</small>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </main>
      )}

      {/* LIBRARY TAB */}
      {activeTab === 'library' && (
        <section className="panel library-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h2>📚 Canciones Generadas</h2>
            <button className="btn" style={{ padding: '0.5rem 1rem', fontSize: '0.8rem' }} onClick={fetchLibrary}>↻ Actualizar</button>
          </div>

          {library.length === 0 && (
            <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '3rem' }}>
              No hay canciones generadas todavía. Ve al Studio y genera tu primera canción.
            </p>
          )}

          <div className="library-grid">
            {library.map(song => (
              <div key={song.filename} className="library-card">
                <div className="library-card-icon">🎵</div>
                <div className="library-card-info">
                  <strong>{song.filename.replace(/_/g, ' ').replace('.mp3', '')}</strong>
                  <small>{song.size_mb} MB</small>
                </div>
                <div className="library-actions">
                  <button className="btn" style={{ padding: '0.4rem 0.8rem', fontSize: '0.75rem' }}
                    onClick={() => window.open(`${API}${song.url}`)}>▶ PLAY</button>
                  <a href={`${API}${song.url}`} download className="btn" style={{ padding: '0.4rem 0.8rem', fontSize: '0.75rem', background: 'rgba(255,255,255,0.05)' }}>
                    ↓ DL
                  </a>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

    </div>
  )
}
