// Precompiled source for the web client (to be built to static/app.js via Babel)
// This is the same logic currently embedded in index.html in a <script type="text/babel"> block.
// After building to app.js and updating index.html to load it, you can remove the inline Babel script.

window.initApp = function () {
  const {
    useState,
    useEffect,
    useRef
  } = React;
  function App() {
    const [log, setLog] = useState([]);
    const [choices, setChoices] = useState([]);
    const [prompt, setPrompt] = useState(null);
    // Town menu split state
    const [townSplit, setTownSplit] = useState({
      active: false,
      inner: false,
      main: [],
      innerChoices: []
    });
    const [background, setBackground] = useState('labyrinth.png'); // Default to labyrinth for character creation
    const [nextBackground, setNextBackground] = useState(null);
    const [isTransitioning, setIsTransitioning] = useState(false);
    const transitionTimeoutRef = useRef(null);
    const coalesceTimerRef = useRef(null); // debounce rapid background changes
    const pendingBgRef = useRef(null); // last requested bg during debounce window
    const lastBackgroundRef = useRef('labyrinth.png');
    // Orientation and device flags
    const [isLandscape, setIsLandscape] = useState(typeof window !== 'undefined' ? window.innerWidth >= window.innerHeight : true);
    const [isMobileLike, setIsMobileLike] = useState(typeof window !== 'undefined' ? window.innerWidth <= 1024 && ("ontouchstart" in window || (navigator.maxTouchPoints || 0) > 0) : false);
    const [showRotateHint, setShowRotateHint] = useState(false);
    const rotateDismissedRef = useRef(false);

    // Reveal queue state (character-by-character typing)
    const revealQueueRef = useRef([]); // queued full lines
    const revealingRef = useRef(false);
    const fastForwardRef = useRef(false);
    const pendingChoicesRef = useRef(null);
    const pendingPromptRef = useRef(null);
    const currentLineRef = useRef(null); // string being typed
    const currentIdxRef = useRef(0); // char index in current line
    const [hud, setHud] = useState({
      enabled: false,
      stats: null
    });
    const [connected, setConnected] = useState(false);
    const [error, setError] = useState('');
    const socketRef = useRef(null);
    const inputRef = useRef(null);
    // Dynamic story container: refs and state
    const overlayRef = useRef(null); // story/dialogue container
    const outputRef = useRef(null); // inner text content
    const bottomRef = useRef(null); // prompt + buttons wrapper
    const [textBoxHeight, setTextBoxHeight] = useState(null);
    const [bottomHeight, setBottomHeight] = useState(0);
    const [bottomGapPx, setBottomGapPx] = useState(12); // small gap below textbox
    function append(text) {
      setLog(prev => [...prev, text]);
      const el = document.getElementById('output');
      if (el) setTimeout(() => {
        try {
          el.scrollTop = el.scrollHeight;
        } catch (e) {}
      }, 0);
    }
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
          if (pendingPromptRef.current) {
            setPrompt(pendingPromptRef.current);
            pendingPromptRef.current = null;
          }
          if (pendingChoicesRef.current) {
            // Apply Town split and update state when reveal completes
            try {
              const opts = pendingChoicesRef.current;
              const split = computeTownSplit(opts);
              if (split.active) {
                setTownSplit(split);
                setChoices(opts);
              } else {
                setTownSplit({
                  active: false,
                  inner: false,
                  main: [],
                  innerChoices: []
                });
                setChoices(opts);
              }
            } catch (e) {
              setTownSplit({
                active: false,
                inner: false,
                main: [],
                innerChoices: []
              });
              setChoices(pendingChoicesRef.current);
            }
            pendingChoicesRef.current = null;
          }
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
      setLog([]);
      setChoices([]);
      setPrompt(null);
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
    function sendAction(action, payload) {
      if (!socketRef.current) return;
      socketRef.current.emit('player_action', {
        action,
        payload
      });
    }
    function startEngine() {
      if (!socketRef.current) return;
      socketRef.current.emit('player_start');
    }
    useEffect(() => {
      // Prevent mobile zoom gestures (double-tap, pinch) for better game UX
      const preventPinch = e => {
        if (e.touches && e.touches.length > 1) {
          e.preventDefault();
        }
      };
      let lastTouchEnd = 0;
      const preventDoubleTap = e => {
        const now = Date.now();
        if (now - lastTouchEnd < 350) {
          e.preventDefault();
        }
        lastTouchEnd = now;
      };
      const preventGesture = e => {
        e.preventDefault();
      };
      document.addEventListener('touchstart', preventPinch, {
        passive: false
      });
      document.addEventListener('touchend', preventDoubleTap, {
        passive: false
      });
      document.addEventListener('dblclick', preventGesture, {
        passive: false
      });
      // iOS Safari specific
      document.addEventListener('gesturestart', preventGesture);
      return () => {
        document.removeEventListener('touchstart', preventPinch);
        document.removeEventListener('touchend', preventDoubleTap);
        document.removeEventListener('dblclick', preventGesture);
        document.removeEventListener('gesturestart', preventGesture);
      };
    }, []);
    useEffect(() => {
      if (typeof io !== 'function') {
        setError('Socket.IO not loaded');
        return;
      }
      const s = io({
        transports: ['polling'],
        forceNew: true,
        timeout: 10000
      });
      socketRef.current = s;
      s.on('connect', () => {
        setConnected(true);
        startEngine();
      });
      s.on('disconnect', reason => {
        setConnected(false);
      });
      s.on('connect_error', error => {
        setError('Connection failed: ' + error.message);
      });
      s.on('connected', () => {});
      // Ignore legacy channels to prevent duplicate text; use only new events below
      s.on('game_output', _data => {/* legacy ignored */});
      s.on('game_menu', _data => {/* legacy ignored */});
      s.on('game_pause', _data => {/* legacy ignored */});
      s.on('game_update', data => {
        // Only use legacy state for HUD if present; do not append text
        if (data && data.state && data.state.character) {
          setHud(prev => ({
            ...prev,
            stats: data.state
          }));
        }
      });
      s.on('game_prompt', data => {
        // Defer prompt until text reveal completes
        if (revealingRef.current || revealQueueRef.current && revealQueueRef.current.length) {
          pendingPromptRef.current = data || null;
        } else {
          setPrompt(data || null);
        }
      });
      // New richer event types
      s.on('dialogue', data => {
        if (data && data.text != null) enqueueDialogue(String(data.text));
      });
      s.on('menu', data => {
        const opts = Array.isArray(data.options) ? data.options : [];
        // Defer showing choices until after reveal completes
        if (revealingRef.current || revealQueueRef.current && revealQueueRef.current.length) {
          pendingChoicesRef.current = opts;
        } else {
          // Apply Town menu split if this looks like the Town menu
          const split = computeTownSplit(opts);
          if (split.active) {
            setTownSplit(split);
            setChoices(opts); // keep original for reference
          } else {
            setTownSplit({
              active: false,
              inner: false,
              main: [],
              innerChoices: []
            });
            setChoices(opts);
          }
        }
      });
      // 'pause' is informational; engine will follow with proper menu id for Continue
      s.on('pause', _data => {/* ignore to avoid wrong continue id */});
      // Combat text goes through typed queue for consistency
      s.on('combat_update', data => {
        if (data && data.text != null) enqueueDialogue(String(data.text));
      });
      s.on('update_stats', data => {
        if (data && data.state) setHud(prev => ({
          ...prev,
          stats: data.state
        }));
      });
      // Scene events for background images and overlay text
      s.on('scene', data => {
        const sceneData = data.data || data; // Handle both nested and flat structures
        // Helper to actually apply a background with preload + crossfade
        const applyBackground = newBackground => {
          const currentBg = lastBackgroundRef.current;
          // Allow null/empty to clear background state for forced resets
          if (newBackground === null || newBackground === '') {
            if (transitionTimeoutRef.current) {
              clearTimeout(transitionTimeoutRef.current);
              transitionTimeoutRef.current = null;
            }
            setBackground('__RESET__');
            setNextBackground(null);
            setIsTransitioning(false);
            lastBackgroundRef.current = '__RESET__';
            return;
          }
          const needsUpdate = currentBg === '__RESET__' || newBackground !== currentBg && newBackground !== nextBackground;
          if (!needsUpdate) {
            return;
          }
          const path = `/static/images/${newBackground}`;
          // If a transition is mid-flight, finalize immediately after preload
          if (isTransitioning) {
            if (transitionTimeoutRef.current) {
              clearTimeout(transitionTimeoutRef.current);
              transitionTimeoutRef.current = null;
            }
            preloadImage(path, () => {
              lastBackgroundRef.current = newBackground;
              setBackground(newBackground);
              setNextBackground(null);
              setIsTransitioning(false);
            });
          } else {
            if (transitionTimeoutRef.current) {
              clearTimeout(transitionTimeoutRef.current);
            }
            preloadImage(path, () => {
              lastBackgroundRef.current = newBackground;
              setNextBackground(newBackground);
              requestAnimationFrame(() => {
                setIsTransitioning(true);
                const duration = typeof window !== 'undefined' && window.innerWidth <= 1024 && ("ontouchstart" in window || (navigator.maxTouchPoints || 0) > 0) ? 600 : 800;
                transitionTimeoutRef.current = setTimeout(() => {
                  setBackground(newBackground);
                  setNextBackground(null);
                  setIsTransitioning(false);
                }, duration);
              });
            });
          }
        };
        if (sceneData && sceneData.background !== undefined) {
          const newBackground = sceneData.background;
          // Debounce/coalesce rapid bg updates (e.g., town -> labyrinth -> room)
          if (coalesceTimerRef.current) {
            clearTimeout(coalesceTimerRef.current);
          }
          pendingBgRef.current = newBackground;
          const delay = typeof window !== 'undefined' && window.innerWidth <= 1024 && ("ontouchstart" in window || (navigator.maxTouchPoints || 0) > 0) ? 220 : 140;
          coalesceTimerRef.current = setTimeout(() => {
            const toApply = pendingBgRef.current;
            pendingBgRef.current = null;
            coalesceTimerRef.current = null;
            applyBackground(toApply);
          }, delay);
        }
        if (sceneData && sceneData.text != null && sceneData.text !== '') {
          enqueueDialogue(String(sceneData.text));
        }
      });
      s.on('clear', () => {
        setLog([]);
        setChoices([]);
        setPrompt(null);
        // Cancel any in-flight background transitions to prevent race conditions
        if (transitionTimeoutRef.current) {
          clearTimeout(transitionTimeoutRef.current);
          transitionTimeoutRef.current = null;
        }
        if (coalesceTimerRef.current) {
          clearTimeout(coalesceTimerRef.current);
          coalesceTimerRef.current = null;
          pendingBgRef.current = null;
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
        // Reset Town split state
        setTownSplit({
          active: false,
          inner: false,
          main: [],
          innerChoices: []
        });
      });
      s.on('connect_error', e => setError(String(e)));
      s.on('error', e => setError(String(e)));
      return () => {
        try {
          s.disconnect();
          if (transitionTimeoutRef.current) {
            clearTimeout(transitionTimeoutRef.current);
          }
        } catch (e) {}
      };
    }, []);
    // Autofocus prompt input when it appears
    useEffect(() => {
      if (prompt && inputRef.current) {
        try {
          inputRef.current.focus();
        } catch (e) {}
      }
    }, [prompt]);
    // Measure container so it's anchored to the bottom with a tiny gap and grows upward as content increases
    useEffect(() => {
      const padTop = 8,
        padBottom = 8; // keep in sync with inline style below
      const contentEl = outputRef.current;
      const bottomEl = bottomRef.current;
      const contentH = contentEl ? contentEl.scrollHeight : 0;
      const bH = bottomEl ? bottomEl.offsetHeight : 0;
      setBottomHeight(bH);
      const desired = Math.max(60, contentH + bH + padTop + padBottom);
      if (typeof window !== 'undefined') {
        const viewport = window.innerHeight || 800;
        // Slight gap between container border and screen bottom, responsive
        const bottomGap = Math.max(20, Math.floor(viewport * 0.024)); // ~2.4vh or at least 20px
        const available = Math.max(60, viewport - bottomGap);
        setBottomGapPx(bottomGap);
        setTextBoxHeight(Math.max(60, Math.min(desired, available)));
      } else {
        setBottomGapPx(20);
        setTextBoxHeight(desired);
      }
    }, [log, choices, prompt]);

    // Recompute on window resize/orientation change
    useEffect(() => {
      const handler = () => {
        // trigger re-measure by changing state with same values
        setLog(prev => prev.slice());
      };
      if (typeof window !== 'undefined') {
        window.addEventListener('resize', handler);
        window.addEventListener('orientationchange', handler);
      }
      return () => {
        if (typeof window !== 'undefined') {
          window.removeEventListener('resize', handler);
          window.removeEventListener('orientationchange', handler);
        }
      };
    }, []);
    // Track orientation and device type; optionally show rotate hint on mobile portrait
    useEffect(() => {
      const updateFlags = () => {
        if (typeof window === 'undefined') return;
        const w = window.innerWidth;
        const h = window.innerHeight;
        const mobileLike = w <= 1024 && ("ontouchstart" in window || (navigator.maxTouchPoints || 0) > 0);
        const landscape = w >= h;
        setIsMobileLike(mobileLike);
        setIsLandscape(landscape);
        if (mobileLike && !landscape && !rotateDismissedRef.current) {
          setShowRotateHint(true);
        } else {
          setShowRotateHint(false);
        }
      };
      updateFlags();
      if (typeof window !== 'undefined') {
        window.addEventListener('resize', updateFlags);
        window.addEventListener('orientationchange', updateFlags);
      }
      return () => {
        if (typeof window !== 'undefined') {
          window.removeEventListener('resize', updateFlags);
          window.removeEventListener('orientationchange', updateFlags);
        }
      };
    }, []);
    const imgObjectFit = 'cover';
    const isMonster = bg => typeof bg === 'string' && bg.toLowerCase().includes('/monsters/') || typeof bg === 'string' && bg.toLowerCase().startsWith('monsters/');
    const currentObjPos = isMonster(background) ? 'top center' : 'center';
    const nextObjPos = isMonster(nextBackground) ? 'top center' : 'center';
    const fadeMs = typeof window !== 'undefined' && window.innerWidth <= 1024 && ("ontouchstart" in window || (navigator.maxTouchPoints || 0) > 0) ? 600 : 800;

    // Preload helper for smoother transitions
    const preloadImage = (path, cb) => {
      try {
        const img = new Image();
        img.onload = () => cb && cb(true);
        img.onerror = () => cb && cb(false);
        img.src = path;
      } catch (e) {
        if (cb) cb(false);
      }
    };

    // ----- Town menu split helpers (inside App scope to access state) -----
    function normalizeLabel(lbl) {
      return ('' + (lbl || '')).trim().toLowerCase();
    }
    // Prefer grouping by action IDs for robustness; labels are fallbacks
    const MAIN_ID_ORDER = ['town:enter',
    // Labyrinth
    'town:shop', 'town:inventory', 'town:companion',
    // ensure Companion is in Main
    'town:quests', 'town:level', 'town:save', 'town:quit', 'town:sleep'];
    const INNER_ID_ORDER = ['town:gamble', 'town:remove_curses', 'town:repair', 'town:train', 'town:rest',
    // Inn
    'town:tavern', 'town:pray',
    // Temple
    'town:eat', 'town:healer'];
    // Label-based fallback synonyms (used only if IDs are missing/unexpected)
    const MAIN_ORDER = ['labyrinth', 'shop', 'inventory', 'companion', 'quest', 'quests', 'level up', 'save', 'quit', 'sleep'];
    const INNER_ORDER = ['gamble', 'remove curses', 'curses', 'repair', 'train', 'training', 'inn', 'tavern', 'temple', 'eat', 'healer'];
    function computeTownSplit(opts) {
      try {
        if (!Array.isArray(opts) || !opts.length) return {
          active: false,
          inner: false,
          main: [],
          innerChoices: []
        };
        const byId = new Map();
        const byLabel = new Map();
        const presentIds = new Set();
        let townScore = 0;
        for (const o of opts) {
          const oid = String(o.id || '').toLowerCase();
          const lbl = normalizeLabel(o.label);
          if (oid) byId.set(oid, o);
          if (lbl) byLabel.set(lbl, o);
          if (oid.startsWith('town:')) {
            townScore++;
            presentIds.add(oid);
          } else if (MAIN_ORDER.includes(lbl) || INNER_ORDER.includes(lbl)) townScore++;
        }
        // Heuristic: detect the root Town menu robustly
        const hasAnyMainId = MAIN_ID_ORDER.some(id => presentIds.has(id));
        const hasAnyInnerId = INNER_ID_ORDER.some(id => presentIds.has(id));
        const likelyTownRoot = townScore >= 8 || hasAnyMainId && hasAnyInnerId;
        if (!likelyTownRoot) return {
          active: false,
          inner: false,
          main: [],
          innerChoices: []
        };
        // Build main/inner from IDs first (preferred)
        const main = [];
        for (const k of MAIN_ID_ORDER) if (byId.has(k)) main.push(byId.get(k));
        const innerChoices = [];
        for (const k of INNER_ID_ORDER) if (byId.has(k)) innerChoices.push(byId.get(k));
        // If ID-based grouping yields too few, fall back to labels
        if (main.length === 0 && innerChoices.length === 0) {
          for (const k of MAIN_ORDER) if (byLabel.has(k)) main.push(byLabel.get(k));
          for (const k of INNER_ORDER) if (byLabel.has(k)) innerChoices.push(byLabel.get(k));
        }
        return {
          active: true,
          inner: false,
          main,
          innerChoices
        };
      } catch (e) {
        return {
          active: false,
          inner: false,
          main: [],
          innerChoices: []
        };
      }
    }
    function focusFirstButtonSoon() {
      try {
        setTimeout(() => {
          const btn = document.querySelector('.options .option-btn');
          if (btn) btn.focus();
        }, 0);
      } catch (e) {}
    }
    // Shorten labels for buttons for better fit while preserving meaning
    function shortenLabel(id, label) {
      const idKey = String(id || '').toLowerCase();
      let t = String(label || '').trim();
      // Remove leading numbering like '12) '
      t = t.replace(/^\s*\d+\)\s*/, '');
      // Remove trailing gold price like ' (10g)'
      t = t.replace(/\s*\(\d+g\)\s*$/i, '');
      // Specific compressions by ID
      const map = {
        'town:enter': 'Enter',
        'town:shop': 'Shop',
        'town:inventory': 'Inventory',
        'town:rest': 'Inn',
        'town:healer': 'Healer',
        'town:tavern': 'Tavern',
        'town:eat': 'Eat',
        'town:gamble': 'Gamble',
        'town:pray': 'Temple',
        'town:level': 'Level',
        'town:quests': 'Quests',
        'town:train': 'Train',
        'town:sleep': 'Sleep',
        'town:companion': 'Companion',
        'town:repair': 'Repair',
        'town:remove_curses': 'Uncurse',
        'town:save': 'Save',
        'town:quit': 'Quit',
        // Shop root
        'shop:weapons': 'Weapons',
        'shop:armor': 'Armor',
        'shop:potions': 'Potions',
        'shop:spells': 'Spells',
        'shop:sell': 'Sell',
        'shop:back': 'Back',
        // Level/back/general
        'level:continue': 'Continue',
        'quests:continue': 'Continue',
        'prompt:submit': 'OK'
      };
      if (map[idKey]) return map[idKey];
      // Generic compressions
      t = t.replace(/\bLevel Up\b/i, 'Level');
      t = t.replace(/\bRemove Curses?\b/i, 'Uncurse');
      t = t.replace(/\bLeave Shop\b/i, 'Leave');
      t = t.replace(/\bBack to main shop\b/i, 'Back');
      t = t.replace(/\bHeal companion.*$/i, 'Heal companion');
      return t.trim();
    }
    function getRenderableChoices() {
      if (townSplit.active) {
        if (!townSplit.inner) {
          const innerVirtual = {
            label: 'Inner town',
            _virtual: 'go-inner'
          };
          // Preserve original backend labels for real options; only add the virtual toggle
          return [...townSplit.main, innerVirtual];
        } else {
          const returnVirtual = {
            label: 'Return to outskirts',
            _virtual: 'go-main'
          };
          // Preserve original backend labels for real options; only add the virtual toggle
          return [...townSplit.innerChoices, returnVirtual];
        }
      }
      // No split: return options exactly as provided by backend
      return choices;
    }
    function handleChoiceClick(c) {
      if (c && c._virtual === 'go-inner') {
        setTownSplit(prev => ({
          ...prev,
          inner: true
        }));
        focusFirstButtonSoon();
        return;
      }
      if (c && c._virtual === 'go-main') {
        setTownSplit(prev => ({
          ...prev,
          inner: false
        }));
        focusFirstButtonSoon();
        return;
      }
      if (c && c.id) {
        sendAction(c.id);
        clearUI();
      }
    }
    return (
      /*#__PURE__*/
      // Note: This is JSX and will be compiled by Babel to JS in app.js
      React.createElement("div", {
        className: "app-container",
        onClickCapture: flushNow,
        style: {
          touchAction: 'manipulation'
        }
      }, /*#__PURE__*/React.createElement("img", {
        className: "background-image background-current",
        src: background === '__RESET__' ? '' : `/static/images/${background}`,
        alt: "",
        style: {
          display: background === '__RESET__' ? 'none' : 'block',
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100dvh',
          maxWidth: '100vw',
          maxHeight: '100vh',
          objectFit: imgObjectFit,
          objectPosition: currentObjPos,
          zIndex: -2,
          opacity: isTransitioning && nextBackground ? 0 : 1,
          transition: isTransitioning ? `opacity ${fadeMs}ms ease` : 'none',
          willChange: 'opacity',
          pointerEvents: 'none',
          userSelect: 'none'
        }
      }), nextBackground && /*#__PURE__*/React.createElement("img", {
        className: "background-image background-next",
        src: `/static/images/${nextBackground}`,
        alt: "",
        style: {
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100dvh',
          maxWidth: '100vw',
          maxHeight: '100vh',
          objectFit: imgObjectFit,
          objectPosition: nextObjPos,
          zIndex: -1,
          opacity: isTransitioning ? 1 : 0,
          transition: `opacity ${fadeMs}ms ease`,
          willChange: 'opacity',
          pointerEvents: 'none',
          userSelect: 'none'
        }
      }), /*#__PURE__*/React.createElement("div", {
        className: "game-content",
        style: {
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
          zIndex: 1
        }
      }, showRotateHint ? /*#__PURE__*/React.createElement("div", {
        style: {
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          background: 'rgba(0,0,0,0.6)',
          zIndex: 10,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 20,
          boxSizing: 'border-box'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          background: '#111',
          border: '1px solid #333',
          borderRadius: 12,
          padding: 20,
          maxWidth: 520,
          width: '90%',
          color: '#fff',
          textAlign: 'center'
        }
      }, /*#__PURE__*/React.createElement("div", {
        style: {
          fontSize: 18,
          marginBottom: 12
        }
      }, "For best experience, rotate your device to landscape."), /*#__PURE__*/React.createElement("div", {
        style: {
          opacity: 0.85,
          marginBottom: 16
        }
      }, "Landscape mode shows the full scene and keeps all text and buttons visible."), /*#__PURE__*/React.createElement("div", {
        style: {
          display: 'flex',
          gap: 10,
          justifyContent: 'center',
          flexWrap: 'wrap'
        }
      }, /*#__PURE__*/React.createElement("button", {
        className: "option-btn",
        onClick: () => {
          rotateDismissedRef.current = true;
          setShowRotateHint(false);
        }
      }, "Continue in portrait")))) : null, hud.enabled && hud.stats && hud.stats.character ? /*#__PURE__*/React.createElement("div", {
        className: "hud"
      }, /*#__PURE__*/React.createElement("span", {
        className: "pill"
      }, "HP: ", hud.stats.character.hp, "/", hud.stats.character.max_hp), /*#__PURE__*/React.createElement("span", {
        className: "pill"
      }, "Gold: ", hud.stats.character.gold), /*#__PURE__*/React.createElement("span", {
        className: "pill"
      }, "XP: ", hud.stats.character.xp), /*#__PURE__*/React.createElement("span", {
        className: "pill"
      }, "Level: ", hud.stats.character.level), /*#__PURE__*/React.createElement("span", {
        className: "pill"
      }, "Depth: ", hud.stats.depth)) : null, /*#__PURE__*/React.createElement("div", {
        className: "content-area",
        style: {
          flex: '1 1 auto',
          display: 'flex',
          flexDirection: 'column'
        }
      }, /*#__PURE__*/React.createElement("div", {
        ref: overlayRef,
        className: "text-overlay",
        onClick: flushNow,
        style: {
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          height: textBoxHeight ? textBoxHeight : 'auto',
          transition: 'height 200ms ease',
          // Height is computed in JS to fit content and remain fully visible
          minHeight: 60,
          overflow: 'hidden',
          // never show internal scrollbars
          paddingTop: 8,
          paddingRight: 20,
          paddingBottom: 8,
          paddingLeft: 20,
          // Anchor at bottom with a tiny responsive gap; grow upward
          marginTop: 'auto',
          marginRight: 10,
          marginBottom: bottomGapPx,
          marginLeft: 10
        }
      }, /*#__PURE__*/React.createElement("div", {
        id: "output",
        ref: outputRef,
        style: {
          whiteSpace: 'pre-wrap'
        }
      }, log.map((ln, i) => /*#__PURE__*/React.createElement("div", {
        key: i
      }, ln))), /*#__PURE__*/React.createElement("div", {
        ref: bottomRef,
        style: {
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          marginTop: 8
        }
      }, prompt ? /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("input", {
        ref: inputRef,
        className: "text-input",
        placeholder: prompt.label || 'Enter',
        onKeyDown: e => {
          if (e.key === 'Enter') {
            const v = e.target.value;
            e.target.value = '';
            // Send first, then clear local UI so action is reliably emitted
            sendAction('prompt:submit', {
              id: prompt.id,
              value: v
            });
            clearUI();
          }
        }
      })) : null, /*#__PURE__*/React.createElement("div", {
        className: "options",
        style: {
          marginTop: 0
        }
      }, getRenderableChoices().map((c, i) => /*#__PURE__*/React.createElement("button", {
        key: i,
        className: "option-btn",
        onClick: () => handleChoiceClick(c),
        "aria-label": c.label
      }, c.label))))))))
    );
  }
  // (moved helper functions inside App; this outer block is now redundant and removed)
  ReactDOM.createRoot(document.getElementById('root')).render(/*#__PURE__*/React.createElement(App, null));
};
