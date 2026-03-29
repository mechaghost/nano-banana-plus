import { useState, useRef, useEffect } from 'react';
import { UploadCloud, Download, Image as ImageIcon, Loader2, RefreshCw, Copy } from 'lucide-react';
import './index.css';

// Auth-aware fetch wrapper
const apiFetch = (url, options = {}) => {
  const token = localStorage.getItem('auth_token');
  const headers = { ...(options.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return fetch(url, { ...options, headers });
};

function LoginForm({ onLogin }) {
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [step, setStep] = useState('email'); // 'email' | 'otp'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const requestOTP = async () => {
    if (!email.trim()) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/auth/request-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() }),
      });
      if (res.ok) {
        setStep('otp');
      } else {
        setError('Failed to send OTP. Please try again.');
      }
    } catch {
      setError('Could not reach server.');
    } finally {
      setLoading(false);
    }
  };

  const verifyOTP = async () => {
    if (!code.trim()) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/auth/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), code: code.trim() }),
      });
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('auth_token', data.token);
        onLogin();
      } else {
        setError('Invalid or expired code. Please try again.');
      }
    } catch {
      setError('Could not reach server.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
      <div className="glass-panel modal-content" style={{ maxWidth: '400px', width: '100%' }}>
        <div className="panel-header">
          <h2>Sign In</h2>
        </div>
        {error && (
          <p style={{ color: '#ef4444', fontSize: '0.9rem', marginBottom: '1rem' }}>{error}</p>
        )}
        {step === 'email' ? (
          <>
            <p className="subtitle" style={{ marginBottom: '1rem' }}>
              Enter your admin email to receive a login code.
            </p>
            <div className="input-group">
              <label>Email</label>
              <input
                type="email"
                placeholder="admin@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && requestOTP()}
              />
            </div>
            <button
              className="btn btn-primary"
              onClick={requestOTP}
              disabled={loading || !email.trim()}
              style={{ marginTop: '1rem', width: '100%' }}
            >
              {loading ? <><Loader2 className="spinner" /> Sending...</> : 'Send Login Code'}
            </button>
          </>
        ) : (
          <>
            <p className="subtitle" style={{ marginBottom: '1rem' }}>
              Check your email for a 6-digit code.
            </p>
            <div className="input-group">
              <label>Login Code</label>
              <input
                type="text"
                placeholder="000000"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && verifyOTP()}
                maxLength={6}
                style={{ textAlign: 'center', fontSize: '1.5rem', letterSpacing: '0.5em' }}
              />
            </div>
            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
              <button className="btn btn-secondary" onClick={() => { setStep('email'); setCode(''); setError(''); }} style={{ flex: 1 }}>
                Back
              </button>
              <button
                className="btn btn-primary"
                onClick={verifyOTP}
                disabled={loading || !code.trim()}
                style={{ flex: 1 }}
              >
                {loading ? <><Loader2 className="spinner" /> Verifying...</> : 'Verify'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function App() {
  // Auth State
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('auth_token'));

  // Config State
  const [hasApiKey, setHasApiKey] = useState(true);
  const [hasRemovebgKey, setHasRemovebgKey] = useState(true);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [removebgKeyInput, setRemovebgKeyInput] = useState('');
  const [autoSaveDirInput, setAutoSaveDirInput] = useState('');
  const [rateLimitThrottle, setRateLimitThrottle] = useState(4.0);
  const [isSavingConfig, setIsSavingConfig] = useState(false);

  // API Key
  const [agentApiKey, setAgentApiKey] = useState('');

  // Generation State
  const [prompt, setPrompt] = useState('');
  const [model, setModel] = useState('imagen-4.0-fast-generate-001');
  const [aspectRatio, setAspectRatio] = useState('1:1');
  const [targetWidth, setTargetWidth] = useState('');
  const [targetHeight, setTargetHeight] = useState('');
  const [outputResolution, setOutputResolution] = useState('');
  const [outputFormat, setOutputFormat] = useState('png');
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

  // Handle 401 globally
  const authFetch = async (url, options = {}) => {
    const res = await apiFetch(url, options);
    if (res.status === 401) {
      localStorage.removeItem('auth_token');
      setIsAuthenticated(false);
      return null;
    }
    return res;
  };

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
      }].slice(-50));
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

  // Check config on mount (only when authenticated)
  useEffect(() => {
    if (isAuthenticated) {
      checkConfig();
      loadApiKey();
    }
  }, [isAuthenticated]);

  const checkConfig = async () => {
    try {
      const res = await authFetch('/api/v1/config');
      if (!res) return;
      const data = await res.json();
      setHasApiKey(data.has_api_key);
      setHasRemovebgKey(data.has_removebg_key);
      setAutoSaveDirInput(data.auto_save_dir || '');
      if (data.rate_limit_throttle !== undefined) {
        setRateLimitThrottle(data.rate_limit_throttle);
      }
      if (!data.has_api_key) {
        setShowConfigModal(true);
      }
    } catch (e) {
      console.error("Failed to check config", e);
    }
  };

  const loadApiKey = async () => {
    try {
      const res = await authFetch('/api/v1/api-key');
      if (!res) return;
      const data = await res.json();
      setAgentApiKey(data.key || '');
    } catch (e) {
      console.error("Failed to load API key", e);
    }
  };

  const saveConfig = async () => {
    setIsSavingConfig(true);
    try {
      const res = await authFetch('/api/v1/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: apiKeyInput.trim(),
          removebg_api_key: removebgKeyInput.trim(),
          auto_save_dir: autoSaveDirInput.trim(),
          rate_limit_throttle: parseFloat(rateLimitThrottle) || 4.0
        }),
      });
      if (!res) return;
      const data = await res.json();
      if (data.status === 'success') {
        setHasApiKey(data.has_api_key);
        setShowConfigModal(false);
        setApiKeyInput('');
        setRemovebgKeyInput('');
        checkConfig();
      }
    } catch (e) {
      console.error("Failed to save config", e);
      alert("Failed to save settings to the server.");
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

      let finalAspectRatio = aspectRatio;
      if (targetWidth && targetHeight) {
        const w = parseInt(targetWidth);
        const h = parseInt(targetHeight);
        if (!isNaN(w) && !isNaN(h) && w > 0 && h > 0) {
          const targetRatio = w / h;
          const ratios = {
            "1:1": 1.0,
            "4:3": 4 / 3,
            "3:4": 3 / 4,
            "16:9": 16 / 9,
            "9:16": 9 / 16
          };
          let closestMatch = "1:1";
          let minDiff = Infinity;
          for (const [ratioStr, ratioVal] of Object.entries(ratios)) {
            const diff = Math.abs(ratioVal - targetRatio);
            if (diff < minDiff) {
              minDiff = diff;
              closestMatch = ratioStr;
            }
          }
          finalAspectRatio = closestMatch;
          formData.append('target_width', w);
          formData.append('target_height', h);
        }
      }

      formData.append('aspect_ratio', finalAspectRatio);
      formData.append('output_resolution', outputResolution);
      formData.append('output_format', outputFormat);

      if (baseImageFile) {
        formData.append('file', baseImageFile);
      }

      const response = await authFetch('/api/v1/generate', {
        method: 'POST',
        body: formData,
      });

      if (!response) return;
      if (!response.ok) throw new Error('Generation failed');

      const blob = await response.blob();
      const imageUrl = URL.createObjectURL(blob);
      setGeneratedImage(imageUrl);
      setSourceImageFile(new File([blob], `generated.${outputFormat}`, { type: `image/${outputFormat}` }));

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
      formData.append('output_format', outputFormat);

      const response = await authFetch('/api/v1/process', {
        method: 'POST',
        body: formData,
      });

      if (!response) return;
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

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    setIsAuthenticated(false);
  };

  // Show login form if not authenticated
  if (!isAuthenticated) {
    return <LoginForm onLogin={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="app-container">
      {/* Config Modal Overlay */}
      {showConfigModal && (
        <div className="modal-overlay">
          <div className="glass-panel modal-content">
            <div className="panel-header">
              <h2>Configuration</h2>
            </div>
            <p className="subtitle" style={{ marginBottom: '1rem' }}>
              Configure your API keys and settings.
            </p>

            {/* Gemini API Key */}
            <div className="input-group">
              <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                Gemini API Key
                {hasApiKey && <span style={{ fontSize: '0.8rem', color: 'var(--success-color, #4ade80)' }}>Currently Set</span>}
              </label>
              <input
                type="password"
                placeholder={hasApiKey ? "API Key is active (Type to replace)" : "Enter Gemini API Key (e.g. AIzaSy...)"}
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                style={{
                  borderColor: !hasApiKey && !apiKeyInput.trim() ? 'rgba(239, 68, 68, 0.5)' : 'var(--panel-border)'
                }}
              />
              {!hasApiKey && !apiKeyInput.trim() && (
                <small style={{ color: '#ef4444', display: 'block', marginTop: '0.25rem' }}>
                  A valid API key is required to generate images.
                </small>
              )}
            </div>

            {/* remove.bg API Key */}
            <div className="input-group" style={{ marginTop: '1rem' }}>
              <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                remove.bg API Key
                {hasRemovebgKey && <span style={{ fontSize: '0.8rem', color: 'var(--success-color, #4ade80)' }}>Currently Set</span>}
              </label>
              <input
                type="password"
                placeholder={hasRemovebgKey ? "Key is active (Type to replace)" : "Enter remove.bg API Key"}
                value={removebgKeyInput}
                onChange={(e) => setRemovebgKeyInput(e.target.value)}
              />
              <small style={{ color: 'var(--text-secondary)', display: 'block', marginTop: '0.25rem' }}>
                Required for background removal. Get a free key at remove.bg
              </small>
            </div>

            {/* Auto-Save Directory */}
            <div className="input-group" style={{ marginTop: '1rem' }}>
              <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Auto-Save Directory Path <span style={{ color: 'var(--text-secondary)', fontWeight: 'normal' }}>(Optional)</span></span>
                {autoSaveDirInput ? <span style={{ fontSize: '0.8rem', color: 'var(--success-color, #4ade80)' }}>Active</span> : <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Disabled</span>}
              </label>
              <input
                type="text"
                placeholder="e.g. /Users/username/Desktop/AI_Generations"
                value={autoSaveDirInput}
                onChange={(e) => setAutoSaveDirInput(e.target.value)}
                style={{ fontStyle: !autoSaveDirInput ? 'italic' : 'normal' }}
              />
              <small style={{ color: 'var(--text-secondary)', display: 'block', marginTop: '0.25rem' }}>
                Paste the absolute folder path. Leave completely blank to disable auto-saving.
              </small>
            </div>

            {/* Rate Limit */}
            <div className="input-group" style={{ marginTop: '1rem' }}>
              <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>API Rate Limit Throttle <span style={{ color: 'var(--text-secondary)', fontWeight: 'normal' }}>(Queue Delay)</span></span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{rateLimitThrottle}s</span>
              </label>
              <input
                type="number"
                step="0.5"
                min="0"
                value={rateLimitThrottle}
                onChange={(e) => setRateLimitThrottle(e.target.value)}
              />
              <small style={{ color: 'var(--text-secondary)', display: 'block', marginTop: '0.25rem' }}>
                The minimum delay between Gemini API requests to prevent "429 Too Many Requests". Free-tier requires at least 4.0 seconds. Set to 0 to disable the queue.
              </small>
            </div>

            {/* Agent API Key */}
            {agentApiKey && (
              <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--panel-border)', paddingTop: '1rem' }}>
                <label style={{ fontWeight: 600, marginBottom: '0.5rem', display: 'block' }}>Agent API Key</label>
                <small style={{ color: 'var(--text-secondary)', display: 'block', marginBottom: '0.75rem' }}>
                  Give this key to your AI agents. They send it as the X-API-Key header.
                </small>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <code style={{ flex: 1, wordBreak: 'break-all', fontSize: '0.85rem', padding: '0.5rem 0.75rem', background: 'rgba(20, 17, 14, 0.6)', borderRadius: '8px', border: '1px solid var(--panel-border)' }}>{agentApiKey}</code>
                  <button
                    className="btn btn-secondary"
                    style={{ padding: '0.4rem 0.6rem', fontSize: '0.8rem' }}
                    onClick={() => navigator.clipboard.writeText(agentApiKey)}
                  >
                    <Copy size={14} /> Copy
                  </button>
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem', justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setShowConfigModal(false)}>
                Close
              </button>
              <button
                className="btn btn-primary"
                onClick={saveConfig}
                disabled={isSavingConfig}
              >
                {isSavingConfig ? <Loader2 className="spinner" /> : 'Save Settings'}
              </button>
            </div>
          </div>
        </div>
      )}

      <header>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
          <button
            className="btn btn-secondary"
            style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
            onClick={() => setShowConfigModal(true)}
          >
            Settings
          </button>
          <button
            className="btn btn-secondary"
            style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
            onClick={handleLogout}
          >
            Sign Out
          </button>
        </div>
      </header>

      <div className="main-grid">
        {/* Generative Panel */}
        <section className="glass-panel">
          <div className="panel-header">
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

          <div className="input-group">
            <label>Aspect Ratio</label>
            <select
              value={aspectRatio}
              onChange={(e) => setAspectRatio(e.target.value)}
              disabled={!!(targetWidth && targetHeight)}
              title={targetWidth && targetHeight ? "Aspect ratio is calculated automatically when Exact Dimensions are provided." : ""}
            >
              <option value="1:1">1:1 (Square)</option>
              <option value="3:4">3:4 (Portrait)</option>
              <option value="4:3">4:3 (Landscape)</option>
              <option value="9:16">9:16 (Vertical Portrait)</option>
              <option value="16:9">16:9 (Widescreen)</option>
            </select>
          </div>

          <div className="input-group">
            <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Exact Dimensions (Optional)</span>
              {(targetWidth || targetHeight) && <span style={{ fontSize: '0.8rem', color: 'var(--success-color, #4ade80)' }}>Center Crop enabled</span>}
            </label>
            <div style={{ display: 'flex', gap: '1rem' }}>
              <input
                type="number"
                placeholder="Width (px)"
                value={targetWidth}
                min="1"
                onChange={(e) => setTargetWidth(e.target.value)}
                style={{ flex: 1 }}
              />
              <span style={{ display: 'flex', alignItems: 'center', color: 'var(--text-secondary)' }}>x</span>
              <input
                type="number"
                placeholder="Height (px)"
                value={targetHeight}
                min="1"
                onChange={(e) => setTargetHeight(e.target.value)}
                style={{ flex: 1 }}
              />
            </div>
            <small style={{ color: 'var(--text-secondary)', display: 'block', marginTop: '0.25rem' }}>
              If provided, we will automatically select the closest Aspect Ratio and perform a perfect center-crop to guarantee these exact dimensions without stretching.
            </small>
          </div>

          <div className="input-group">
            <label>Output Resolution</label>
            <select
              value={outputResolution}
              onChange={(e) => setOutputResolution(e.target.value)}
              disabled={model !== 'imagen-4.0-ultra-generate-001'}
              title={model !== 'imagen-4.0-ultra-generate-001' ? "High resolution is only supported by the Imagen 4.0 Ultra model." : ""}
            >
              <option value="">1K (Default)</option>
              <option value="2K">2K (High Resolution)</option>
            </select>
            {model !== 'imagen-4.0-ultra-generate-001' && (
              <small style={{ color: 'var(--text-secondary)', display: 'block', marginTop: '0.25rem' }}>
                *Select Imagen 4.0 Ultra to unlock 2K generation.
              </small>
            )}
          </div>

          <div className="input-group">
            <label>Output Format</label>
            <select
              value={outputFormat}
              onChange={(e) => setOutputFormat(e.target.value)}
            >
              <option value="png">PNG (Lossless)</option>
              <option value="webp">WebP (Smaller Size)</option>
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
            {isGenerating ? <><Loader2 className="spinner" /> Generating...</> : 'Generate Image'}
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
                <a className="btn btn-secondary" href={generatedImage} download={`generated.${outputFormat}`}>
                  <Download size={18} /> Download
                </a>
              </div>
            )}
          </div>
        </section>

        {/* Processing Panel */}
        <section className="glass-panel">
          <div className="panel-header">
            <h2>Background Removal</h2>
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
                <a className="btn className-primary" href={processedImage} download={`processed.${outputFormat}`}>
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
            {isProcessing ? <><Loader2 className="spinner" /> Processing...</> : 'Remove Background & Cut'}
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
