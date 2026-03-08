import { useState, useRef, useEffect } from 'react';
import { Sparkles, UploadCloud, Download, Image as ImageIcon, Scissors, Loader2, RefreshCw, Key, Settings } from 'lucide-react';
import './index.css';

function App() {
  // Config State
  const [hasApiKey, setHasApiKey] = useState(true); // Assume true initially to prevent flash
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [isSavingConfig, setIsSavingConfig] = useState(false);

  // Generation State
  const [prompt, setPrompt] = useState('');
  const [model, setModel] = useState('imagen-4.0-generate-001');
  const [aspectRatio, setAspectRatio] = useState('1:1');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedImage, setGeneratedImage] = useState(null);
  const [baseImageFile, setBaseImageFile] = useState(null);
  const genFileInputRef = useRef(null);

  // Processing State
  const [isProcessing, setIsProcessing] = useState(false);
  const [processedImage, setProcessedImage] = useState(null);
  const [sourceImageFile, setSourceImageFile] = useState(null);
  const fileInputRef = useRef(null);

  // Console Log State
  const [logs, setLogs] = useState([]);
  const logsEndRef = useRef(null);

  // Intercept console messages
  useEffect(() => {
    const originalLog = console.log;
    const originalError = console.error;
    const originalWarn = console.warn;

    const addLog = (type, args) => {
      const message = args.map(arg =>
        typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg)
      ).join(' ');

      setLogs(prev => [...prev, {
        id: Date.now() + Math.random(),
        type,
        message,
        time: new Date().toLocaleTimeString([], { hour12: false })
      }].slice(-50)); // Keep last 50 logs
    };

    console.log = (...args) => {
      originalLog(...args);
      addLog('log', args);
    };

    console.error = (...args) => {
      originalError(...args);
      addLog('error', args);
    };

    console.warn = (...args) => {
      originalWarn(...args);
      addLog('warn', args);
    };

    return () => {
      console.log = originalLog;
      console.error = originalError;
      console.warn = originalWarn;
    };
  }, []);

  // Check config on mount
  useEffect(() => {
    checkConfig();
  }, []);

  const checkConfig = async () => {
    try {
      const res = await fetch('http://127.0.0.1:43211/api/v1/config');
      const data = await res.json();
      setHasApiKey(data.has_api_key);
      if (!data.has_api_key) {
        setShowConfigModal(true);
      }
    } catch (e) {
      console.error("Failed to check config", e);
    }
  };

  const saveConfig = async () => {
    if (!apiKeyInput.trim()) return;
    setIsSavingConfig(true);
    try {
      const res = await fetch('http://127.0.0.1:43211/api/v1/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKeyInput.trim() }),
      });
      const data = await res.json();
      if (data.status === 'success') {
        setHasApiKey(data.has_api_key);
        setShowConfigModal(!data.has_api_key);
        setApiKeyInput(''); // clear it
      }
    } catch (e) {
      console.error("Failed to save config", e);
      alert("Failed to save API key to the server.");
    } finally {
      setIsSavingConfig(false);
    }
  };

  const handleGenerate = async () => {
    if (!prompt) return;
    setIsGenerating(true);
    setGeneratedImage(null);
    try {
      if (!hasApiKey) {
        setShowConfigModal(true);
        return;
      }

      const formData = new FormData();
      formData.append('prompt', prompt);
      formData.append('model', model);
      formData.append('aspect_ratio', aspectRatio);

      if (baseImageFile) {
        formData.append('file', baseImageFile);
      }

      const response = await fetch('http://127.0.0.1:43211/api/v1/generate', {
        method: 'POST',
        // No Content-Type header needed for FormData; browser sets it with boundary
        body: formData,
      });

      if (!response.ok) throw new Error('Generation failed');

      const blob = await response.blob();
      const imageUrl = URL.createObjectURL(blob);
      setGeneratedImage(imageUrl);

      // Auto-set as source for processing if we want to chain them
      setSourceImageFile(new File([blob], 'generated.png', { type: 'image/png' }));

    } catch (error) {
      console.error(error);
      alert('Failed to generate image. Make sure the server is running and your prompt/image meet the API guidelines.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleProcess = async () => {
    if (!sourceImageFile) return;
    setIsProcessing(true);
    setProcessedImage(null);
    try {
      const formData = new FormData();
      formData.append('file', sourceImageFile);

      const response = await fetch('http://127.0.0.1:43211/api/v1/process', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Processing failed');

      const blob = await response.blob();
      setProcessedImage(URL.createObjectURL(blob));
    } catch (error) {
      console.error(error);
      alert('Failed to process image. Make sure the backend server is running.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDrop = (e, setter) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setter(e.dataTransfer.files[0]);
    }
  };

  const clearProcessingState = () => {
    setProcessedImage(null);
    setSourceImageFile(null);
  };

  return (
    <div className="app-container">
      {/* Config Modal Overlay */}
      {showConfigModal && (
        <div className="modal-overlay">
          <div className="glass-panel modal-content">
            <div className="panel-header">
              <Key size={24} />
              <h2>Configuration</h2>
            </div>
            <p className="subtitle" style={{ marginBottom: '1rem' }}>
              To use Image Generation, you must provide a Gemini API Key.
              This key will be saved locally to your `server/.env` file.
            </p>
            <div className="input-group">
              <label>Gemini API Key</label>
              <input
                type="password"
                placeholder="AIzaSy..."
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem', justifyContent: 'flex-end' }}>
              {hasApiKey && (
                <button className="btn btn-secondary" onClick={() => setShowConfigModal(false)}>
                  Cancel
                </button>
              )}
              <button
                className="btn btn-primary"
                onClick={saveConfig}
                disabled={!apiKeyInput.trim() || isSavingConfig}
              >
                {isSavingConfig ? <Loader2 className="spinner" /> : 'Save Key'}
              </button>
            </div>
          </div>
        </div>
      )}

      <header>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '-2rem' }}>
          <button
            className="btn btn-secondary"
            style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
            onClick={() => setShowConfigModal(true)}
          >
            <Settings size={18} /> Settings
          </button>
        </div>
        <h1>AI Studio</h1>
        <p className="subtitle">Gemini Generation & Local Background Processing</p>
      </header>

      <div className="main-grid">
        {/* Generative Panel */}
        <section className="glass-panel">
          <div className="panel-header">
            <Sparkles size={24} />
            <h2>Image Generation</h2>
          </div>

          <div className="input-group">
            <label>Prompt</label>
            <textarea
              placeholder="A futuristic cybernetic tiger roaming a neon wasteland..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>

          <div className="input-group">
            <label>Model</label>
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="imagen-4.0-generate-001">Imagen 4.0 Standard</option>
              <option value="imagen-4.0-fast-generate-001">Imagen 4.0 Fast</option>
              <option value="imagen-4.0-ultra-generate-001">Imagen 4.0 Ultra</option>
            </select>
          </div>

          <div
            className="input-group dropzone"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => handleDrop(e, setBaseImageFile)}
            onClick={() => genFileInputRef.current?.click()}
            style={{
              cursor: 'pointer',
              padding: '1rem',
              border: '1px dashed var(--panel-border)',
              borderRadius: '8px',
              textAlign: 'center',
              marginBottom: '1rem'
            }}
          >
            <input
              type="file"
              ref={genFileInputRef}
              onChange={(e) => setBaseImageFile(e.target.files[0])}
              accept="image/*"
              style={{ display: 'none' }}
            />
            {baseImageFile ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>{baseImageFile.name} (Ready)</span>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem' }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setBaseImageFile(null);
                  }}
                >
                  Clear
                </button>
              </div>
            ) : (
              <div>
                <UploadCloud size={20} style={{ marginBottom: '0.5rem', color: 'var(--text-secondary)' }} />
                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                  Optional: Drop a base image here or click to upload
                </div>
              </div>
            )}
          </div>

          <button
            className="btn btn-primary"
            onClick={handleGenerate}
            disabled={isGenerating || !prompt}
          >
            {isGenerating ? <><Loader2 className="spinner" /> Generating...</> : <><Sparkles size={20} /> Generate Image</>}
          </button>

          <div className="preview-container">
            {isGenerating && (
              <div className="loader-overlay">
                <Loader2 className="spinner" />
                <span className="loader-text">Summoning pixels from Gemini...</span>
              </div>
            )}

            {generatedImage ? (
              <img src={generatedImage} alt="Generated" />
            ) : (
              !isGenerating && (
                <div className="empty-state">
                  <ImageIcon />
                  <p>Your creation will appear here</p>
                </div>
              )
            )}

            {generatedImage && (
              <div className="result-actions">
                <a className="btn btn-secondary" href={generatedImage} download="generated.png">
                  <Download size={18} /> Download
                </a>
              </div>
            )}
          </div>
        </section>

        {/* Processing Panel */}
        <section className="glass-panel">
          <div className="panel-header">
            <Scissors size={24} />
            <h2>Local Processing</h2>
          </div>

          <div
            className="preview-container dropzone"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => handleDrop(e, setSourceImageFile)}
            onClick={() => !processedImage && fileInputRef.current?.click()}
            style={{ cursor: processedImage ? 'default' : 'pointer' }}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => setSourceImageFile(e.target.files[0])}
              accept="image/*"
            />

            {isProcessing && (
              <div className="loader-overlay">
                <Loader2 className="spinner" />
                <span className="loader-text">Removing background & trimming...</span>
              </div>
            )}

            {processedImage ? (
              <img src={processedImage} alt="Processed Result" className="checkboard-bg" />
            ) : sourceImageFile ? (
              <img src={URL.createObjectURL(sourceImageFile)} alt="Source" />
            ) : (
              <div className="empty-state">
                <UploadCloud />
                <p>Drag & drop or click to upload</p>
                <small>Generated images are automatically piped here.</small>
              </div>
            )}

            {processedImage && (
              <div className="result-actions">
                <a className="btn btn-primary" href={processedImage} download="processed.png">
                  <Download size={18} /> Save Asset
                </a>
                <button className="btn btn-secondary" onClick={(e) => {
                  e.stopPropagation();
                  clearProcessingState();
                }}>
                  <RefreshCw size={18} /> Reset
                </button>
              </div>
            )}
          </div>

          <button
            className="btn btn-primary"
            onClick={handleProcess}
            disabled={isProcessing || !sourceImageFile}
          >
            {isProcessing ? <><Loader2 className="spinner" /> Processing Local...</> : <><Scissors size={20} /> Remove Background & Cut</>}
          </button>
        </section>
      </div>

      {/* Terminal / Debugger Panel */}
      <section className="glass-panel" style={{ marginTop: '2rem' }}>
        <div className="panel-header" style={{ fontSize: '1.2rem', paddingBottom: '0.5rem' }}>
          <h2>Console Output</h2>
          <button
            className="btn btn-secondary"
            style={{ marginLeft: 'auto', padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
            onClick={() => setLogs([])}
          >
            Clear
          </button>
        </div>
        <div className="terminal-window">
          {logs.length === 0 ? (
            <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>Listening for console events...</div>
          ) : (
            logs.map(log => (
              <div key={log.id} className={`log-entry log-${log.type}`}>
                <span className="log-time">[{log.time}]</span>
                <span className="log-message">{log.message}</span>
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      </section>
    </div>
  );
}

export default App;
