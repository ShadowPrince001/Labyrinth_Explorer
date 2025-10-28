// Precompiled source for the web client (to be built to static/app.js via Babel)
// This is the same logic currently embedded in index.html in a <script type="text/babel"> block.
// After building to app.js and updating index.html to load it, you can remove the inline Babel script.

window.initApp = (function () {
    const { useState, useEffect, useRef } = React;
    function App() {
        const [log, setLog] = useState([]);
        const [choices, setChoices] = useState([]);
        const [prompt, setPrompt] = useState(null);
        const [background, setBackground] = useState('labyrinth.png'); // Default to labyrinth for character creation
        const [nextBackground, setNextBackground] = useState(null);
        const [isTransitioning, setIsTransitioning] = useState(false);
        const transitionTimeoutRef = useRef(null);
        const lastBackgroundRef = useRef('labyrinth.png');


        // Reveal queue state (character-by-character typing)
        const revealQueueRef = useRef([]); // queued full lines
        const revealingRef = useRef(false);
        const fastForwardRef = useRef(false);
        const pendingChoicesRef = useRef(null);
        const pendingPromptRef = useRef(null);
        const currentLineRef = useRef(null); // string being typed
        const currentIdxRef = useRef(0); // char index in current line
        const [hud, setHud] = useState({ enabled: false, stats: null });
        const [connected, setConnected] = useState(false);
        const [error, setError] = useState('');
        const socketRef = useRef(null);
        const inputRef = useRef(null);
        function append(text) { setLog(prev => [...prev, text]); const el = document.getElementById('output'); if (el) setTimeout(() => { try { el.scrollTop = el.scrollHeight; } catch (e) { } }, 0); }
        function startRevealLoop() {
            if (revealingRef.current) return;
            revealingRef.current = true;
            const step = () => {
                const q = revealQueueRef.current;
                // Fast-forward: flush current partial and the rest immediately
                if (fastForwardRef.current) {
                    // If currently typing a line, finish it
                    if (currentLineRef.current != null) {
                        const remaining = currentLineRef.current.slice(currentIdxRef.current);
                        if (remaining) {
                            setLog(prev => {
                                const next = prev.slice();
                                const last = next.length - 1;
                                if (last >= 0) next[last] = (next[last] || '') + remaining;
                                return next;
                            });
                        }
                        currentLineRef.current = null;
                        currentIdxRef.current = 0;
                    }
                    // Flush queued lines
                    if (q.length) {
                        const items = q.splice(0, q.length);
                        setLog(prev => [...prev, ...items.map(String)]);
                    }
                    // Turn off fast-forward after we've flushed the queued lines
                    fastForwardRef.current = false;
                }
                // If nothing left and no active line, finish
                if (!q.length && currentLineRef.current == null) {
                    revealingRef.current = false;
                    if (pendingPromptRef.current) { setPrompt(pendingPromptRef.current); pendingPromptRef.current = null; }
                    if (pendingChoicesRef.current) { setChoices(pendingChoicesRef.current); pendingChoicesRef.current = null; }
                    return;
                }
                // Start a new line if needed
                if (currentLineRef.current == null) {
                    currentLineRef.current = String(q.shift());
                    currentIdxRef.current = 0;
                    // Insert an empty line to fill
                    setLog(prev => [...prev, ""]);
                }
                // Type next character
                const line = currentLineRef.current;
                const i = currentIdxRef.current;
                if (i < line.length) {
                    const ch = line.charAt(i);
                    currentIdxRef.current = i + 1;
                    setLog(prev => {
                        const next = prev.slice();
                        const last = next.length - 1;
                        if (last >= 0) next[last] = (next[last] || '') + ch;
                        return next;
                    });
                    const delay = fastForwardRef.current ? 0 : 28; // medium pace per character
                    setTimeout(step, delay);
                    return;
                }
                // Line complete; prepare for next loop
                currentLineRef.current = null;
                currentIdxRef.current = 0;
                const delay = fastForwardRef.current ? 0 : 80; // slight pause between lines
                setTimeout(step, delay);
            };
            setTimeout(step, 0);
        }
        function enqueueDialogue(text) {
            revealQueueRef.current.push(text);
            startRevealLoop();
        }
        function clearUI() {
            setLog([]); setChoices([]); setPrompt(null);
            revealQueueRef.current = [];
            revealingRef.current = false;
            fastForwardRef.current = false;
            pendingChoicesRef.current = null;
            pendingPromptRef.current = null;
            currentLineRef.current = null;
            currentIdxRef.current = 0;
        }
        function flushNow() {
            // Request immediate fast-forward/flush of the reveal queue.
            fastForwardRef.current = true;
            // If revealer isn't active, start it so flush happens immediately
            if (!revealingRef.current) startRevealLoop();
            // fastForwardRef will be turned off by the reveal loop after flushing
        }
        function sendAction(action, payload) { if (!socketRef.current) return; socketRef.current.emit('player_action', { action, payload }); }
        function startEngine() { if (!socketRef.current) return; socketRef.current.emit('player_start'); }
        useEffect(() => {
            if (typeof io !== 'function') { setError('Socket.IO not loaded'); return; }
            const s = io({
                transports: ['polling'],
                forceNew: true,
                timeout: 10000
            }); socketRef.current = s;
            s.on('connect', () => {
                setConnected(true);
                startEngine();
            });
            s.on('disconnect', (reason) => {
                setConnected(false);
            });
            s.on('connect_error', (error) => {
                setError('Connection failed: ' + error.message);
            });
            s.on('connected', () => { });
            // Ignore legacy channels to prevent duplicate text; use only new events below
            s.on('game_output', (_data) => { /* legacy ignored */ });
            s.on('game_menu', (_data) => { /* legacy ignored */ });
            s.on('game_pause', (_data) => { /* legacy ignored */ });
            s.on('game_update', (data) => {
                // Only use legacy state for HUD if present; do not append text
                if (data && data.state && data.state.character) {
                    setHud(prev => ({ ...prev, stats: data.state }));
                }
            });
            s.on('game_prompt', (data) => {
                // Defer prompt until text reveal completes
                if (revealingRef.current || (revealQueueRef.current && revealQueueRef.current.length)) {
                    pendingPromptRef.current = data || null;
                } else {
                    setPrompt(data || null);
                }
            });
            // New richer event types
            s.on('dialogue', (data) => { if (data && data.text != null) enqueueDialogue(String(data.text)); });
            s.on('menu', (data) => {
                const opts = Array.isArray(data.options) ? data.options : [];
                // Defer showing choices until after reveal completes
                if (revealingRef.current || (revealQueueRef.current && revealQueueRef.current.length)) {
                    pendingChoicesRef.current = opts;
                } else {
                    setChoices(opts);
                }
            });
            // 'pause' is informational; engine will follow with proper menu id for Continue
            s.on('pause', (_data) => { /* ignore to avoid wrong continue id */ });
            // Combat text goes through typed queue for consistency
            s.on('combat_update', (data) => { if (data && data.text != null) enqueueDialogue(String(data.text)); });
            s.on('update_stats', (data) => { if (data && data.state) setHud(prev => ({ ...prev, stats: data.state })); });
            // Scene events for background images and overlay text
            s.on('scene', (data) => {
                const sceneData = data.data || data; // Handle both nested and flat structures
                if (sceneData && sceneData.background !== undefined) {
                    const newBackground = sceneData.background;
                    // Use ref for accurate current state (state variables are stale in this closure)
                    const currentBg = lastBackgroundRef.current;
                    console.log('[SCENE] Received:', newBackground, '| LastRef:', currentBg, '| Next:', nextBackground, '| Transitioning:', isTransitioning);

                    // Allow null/undefined to clear background state for forced resets
                    if (newBackground === null || newBackground === '') {
                        console.log('[SCENE] Clearing background state');
                        if (transitionTimeoutRef.current) {
                            clearTimeout(transitionTimeoutRef.current);
                            transitionTimeoutRef.current = null;
                        }
                        // Use a special sentinel value that won't match any real background
                        setBackground('__RESET__');
                        setNextBackground(null);
                        setIsTransitioning(false);
                        lastBackgroundRef.current = '__RESET__';
                        return;
                    }

                    // Check if this is genuinely a new background we need to apply
                    // Use lastBackgroundRef.current instead of background state (which is stale in closure)
                    const needsUpdate = (
                        currentBg === '__RESET__' ||
                        (newBackground !== currentBg && newBackground !== nextBackground)
                    );

                    if (needsUpdate) {
                        console.log('[SCENE] Applying background:', newBackground);
                        // If a transition is mid-flight, finalize it immediately to avoid dropping the new scene
                        if (isTransitioning) {
                            if (transitionTimeoutRef.current) {
                                clearTimeout(transitionTimeoutRef.current);
                                transitionTimeoutRef.current = null;
                            }
                            // Hard switch to ensure correctness over animation in edge cases
                            lastBackgroundRef.current = newBackground;
                            setBackground(newBackground);
                            setNextBackground(null);
                            setIsTransitioning(false);
                        } else {
                            // Normal crossfade transition
                            lastBackgroundRef.current = newBackground;
                            if (transitionTimeoutRef.current) {
                                clearTimeout(transitionTimeoutRef.current);
                            }
                            setNextBackground(newBackground);
                            requestAnimationFrame(() => {
                                setIsTransitioning(true);
                                transitionTimeoutRef.current = setTimeout(() => {
                                    setBackground(newBackground);
                                    setNextBackground(null);
                                    setIsTransitioning(false);
                                }, 800);
                            });
                        }
                    } else {
                        console.log('[SCENE] Skipped (duplicate)');
                    }
                }
                if (sceneData && sceneData.text != null && sceneData.text !== '') {
                    enqueueDialogue(String(sceneData.text));
                }
            });
            s.on('clear', () => {
                setLog([]); setChoices([]); setPrompt(null);
                // Cancel any in-flight background transitions to prevent race conditions
                if (transitionTimeoutRef.current) {
                    clearTimeout(transitionTimeoutRef.current);
                    transitionTimeoutRef.current = null;
                }
                setNextBackground(null);
                setIsTransitioning(false);
                // Reset the last background reference so the next scene event isn't considered a duplicate
                lastBackgroundRef.current = '';
                // Reset reveal
                revealQueueRef.current = [];
                revealingRef.current = false;
                fastForwardRef.current = false;
                pendingChoicesRef.current = null;
                pendingPromptRef.current = null;
                currentLineRef.current = null;
                currentIdxRef.current = 0;
            });
            s.on('connect_error', (e) => setError(String(e)));
            s.on('error', (e) => setError(String(e)));
            return () => {
                try {
                    s.disconnect();
                    if (transitionTimeoutRef.current) {
                        clearTimeout(transitionTimeoutRef.current);
                    }
                } catch (e) { }
            };
        }, []);
        // Autofocus prompt input when it appears
        useEffect(() => { if (prompt && inputRef.current) { try { inputRef.current.focus(); } catch (e) { } } }, [prompt]);
        return (
            // Note: This is JSX and will be compiled by Babel to JS in app.js
            <div className="app-container" onClickCapture={flushNow}>
                {/* Dual-layer background for ultra-smooth crossfade transitions */}
                {/* Current/Previous background layer - always visible except during active transition */}
                <div
                    className="background-image background-current"
                    style={{
                        backgroundImage: background === '__RESET__' ? 'none' : `url(/static/images/${background})`,
                        backgroundSize: 'cover',
                        backgroundPosition: 'center',
                        backgroundRepeat: 'no-repeat',
                        position: 'fixed',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '100%',
                        zIndex: -2,
                        opacity: (isTransitioning && nextBackground) ? 0 : 1,
                        transition: isTransitioning ? 'opacity 800ms cubic-bezier(0.4, 0.0, 0.2, 1)' : 'none'
                    }}
                />
                {/* Next background layer - pre-load and fade in */}
                {nextBackground && (
                    <div
                        className="background-image background-next"
                        style={{
                            backgroundImage: `url(/static/images/${nextBackground})`,
                            backgroundSize: 'cover',
                            backgroundPosition: 'center',
                            backgroundRepeat: 'no-repeat',
                            position: 'fixed',
                            top: 0,
                            left: 0,
                            width: '100%',
                            height: '100%',
                            zIndex: -1,
                            opacity: isTransitioning ? 1 : 0,
                            transition: 'opacity 800ms cubic-bezier(0.4, 0.0, 0.2, 1)'
                        }}

                    />
                )}
                <div className="game-content" style={{ height: '100%', display: 'flex', flexDirection: 'column', position: 'relative', zIndex: 1 }}>

                    {hud.enabled && hud.stats && hud.stats.character ? (
                        <div className="hud">
                            <span className="pill">HP: {hud.stats.character.hp}/{hud.stats.character.max_hp}</span>
                            <span className="pill">Gold: {hud.stats.character.gold}</span>
                            <span className="pill">XP: {hud.stats.character.xp}</span>
                            <span className="pill">Level: {hud.stats.character.level}</span>
                            <span className="pill">Depth: {hud.stats.depth}</span>
                        </div>
                    ) : null}
                    <div className="content-area" style={{ flex: '1 1 auto', display: 'flex', flexDirection: 'column' }}>
                        <div className="spacer" style={{ flex: '1 1 50%' }} />
                        <div className="text-overlay" onClick={flushNow}>
                            <div id="output">
                                {log.map((ln, i) => (<div key={i}>{ln}</div>))}
                            </div>
                            {prompt ? (
                                <div style={{ marginTop: 8 }}>
                                    <input
                                        ref={inputRef}
                                        className="text-input"
                                        placeholder={prompt.label || 'Enter'}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') {
                                                const v = e.target.value; e.target.value = '';
                                                // Send first, then clear local UI so action is reliably emitted
                                                sendAction('prompt:submit', { id: prompt.id, value: v });
                                                clearUI();
                                            }
                                        }}
                                    />
                                </div>
                            ) : null}
                            <div className="options">
                                {choices.map((c, i) => (
                                    <button key={i} className="option-btn" onClick={() => { sendAction(c.id); clearUI(); }}>{c.label}</button>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        );
    }
    ReactDOM.createRoot(document.getElementById('root')).render(<App />)
});
