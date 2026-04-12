/**
 * piSignage Overlay Client
 *
 * Runs inside the piSignage player's Chromium browser as part of a custom layout.
 * Connects to the piSignage server via socket.io to receive real-time overlay
 * commands for kiosk scan actions.
 *
 * State machine:
 *   IDLE -> PROCESSING -> DEPOSIT_WAITING -> PRODUCT_DISPLAY -> IDLE
 *   IDLE -> PROCESSING -> NO_MATCH -> IDLE
 *   IDLE -> PROCESSING -> QR_NOT_ALLOWED -> IDLE
 *   IDLE -> PROCESSING -> RECYCLE_FAILURE -> IDLE
 */
(function() {
    'use strict';

    // -- Configuration --
    var RECONNECT_INTERVAL = 5000;      // ms between reconnect attempts
    var HEARTBEAT_INTERVAL = 30000;     // ms between heartbeats
    var PRELOAD_TIMEOUT = 10000;        // ms timeout for image preloading

    // Auto-hide durations (ms) - fallback if server doesn't specify
    var STATE_DURATIONS = {
        no_match: 5000,
        qr_not_allowed: 5000,
        product_display: 10000,
        recycle_failure: 5000
    };

    // -- State --
    var currentState = 'idle';
    var socket = null;
    var hideTimer = null;
    var heartbeatTimer = null;
    var reconnectTimer = null;
    var preloadedImages = {};

    // -- DOM references --
    var overlayEl = document.getElementById('overlay');
    var contentEl = document.getElementById('overlay-content');
    var statusEl = document.getElementById('overlay-status');
    var productImageEl = document.getElementById('product-image');
    var productNameEl = document.getElementById('product-name');
    var stateElements = {};

    // Cache state element references
    var STATES = [
        'processing', 'deposit_waiting', 'product_display',
        'no_match', 'qr_not_allowed', 'recycle_failure'
    ];
    STATES.forEach(function(state) {
        stateElements[state] = document.getElementById('state-' + state);
    });

    // ----------------------------------------------------------------
    // Socket.io Connection
    // ----------------------------------------------------------------

    function getServerUrl() {
        // When running inside piSignage player, the server is the same host
        // that served this layout file
        return window.location.protocol + '//' + window.location.host;
    }

    function connect() {
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }

        var serverUrl = getServerUrl();

        // Try socket.io 2.x path first (matches server-socket-new.js)
        // The piSignage player may already have socket.io loaded;
        // we load our own connection on the overlay namespace
        if (typeof io === 'undefined') {
            // socket.io client not available - load it dynamically
            var script = document.createElement('script');
            script.src = serverUrl + '/newsocket.io/socket.io.js';
            script.onload = function() { initSocket(serverUrl); };
            script.onerror = function() {
                console.error('[Overlay] Failed to load socket.io client');
                scheduleReconnect();
            };
            document.head.appendChild(script);
        } else {
            initSocket(serverUrl);
        }
    }

    function initSocket(serverUrl) {
        try {
            socket = io(serverUrl, {
                path: '/newsocket.io',
                transports: ['websocket', 'polling'],
                reconnection: false  // we handle reconnection ourselves
            });
        } catch(e) {
            console.error('[Overlay] Socket init error:', e);
            scheduleReconnect();
            return;
        }

        socket.on('connect', function() {
            console.log('[Overlay] Connected to server');
            setStatus('connected');
            startHeartbeat();
        });

        socket.on('overlay_cmd', function(msg) {
            console.log('[Overlay] Received command:', msg.state, msg.data);
            handleOverlayCommand(msg.state, msg.data || {});
        });

        socket.on('disconnect', function(reason) {
            console.log('[Overlay] Disconnected:', reason);
            setStatus('disconnected');
            stopHeartbeat();
            scheduleReconnect();
        });

        socket.on('connect_error', function(err) {
            console.error('[Overlay] Connection error:', err.message);
            setStatus('error');
            scheduleReconnect();
        });
    }

    function scheduleReconnect() {
        if (reconnectTimer) return;
        reconnectTimer = setTimeout(function() {
            reconnectTimer = null;
            connect();
        }, RECONNECT_INTERVAL);
    }

    function startHeartbeat() {
        stopHeartbeat();
        heartbeatTimer = setInterval(function() {
            if (socket && socket.connected) {
                // Report current overlay state back to server
                socket.emit('overlay_state', currentState, {});
            }
        }, HEARTBEAT_INTERVAL);
    }

    function stopHeartbeat() {
        if (heartbeatTimer) {
            clearInterval(heartbeatTimer);
            heartbeatTimer = null;
        }
    }

    // ----------------------------------------------------------------
    // Overlay State Machine
    // ----------------------------------------------------------------

    function handleOverlayCommand(state, data) {
        if (state === 'idle') {
            hideOverlay();
            return;
        }

        if (STATES.indexOf(state) === -1) {
            console.warn('[Overlay] Unknown state:', state);
            return;
        }

        // Cancel any pending auto-hide
        cancelHideTimer();

        // Handle product_display specially - needs image loading
        if (state === 'product_display' && data.productImage) {
            showProductDisplay(data);
        } else {
            showState(state);
        }

        // Schedule auto-hide
        var duration = data.duration ? (data.duration * 1000) : STATE_DURATIONS[state];
        if (duration) {
            scheduleHide(duration);
        }

        // Report state change back to server
        if (socket && socket.connected) {
            socket.emit('overlay_state', state, data);
        }
    }

    function showState(state) {
        currentState = state;

        // Hide all state elements
        STATES.forEach(function(s) {
            if (stateElements[s]) {
                stateElements[s].style.display = 'none';
            }
        });

        // Show the target state
        if (stateElements[state]) {
            stateElements[state].style.display = 'flex';
        }

        // Show the overlay
        overlayEl.classList.add('overlay-visible');

        // Mute audio during overlay
        muteAudio(true);
    }

    function showProductDisplay(data) {
        var imageUrl = data.productImage;
        var name = data.productName || '';

        // Set product name
        productNameEl.textContent = name;

        // Check if image is preloaded
        if (preloadedImages[imageUrl]) {
            productImageEl.src = preloadedImages[imageUrl].src;
            showState('product_display');
        } else {
            // Load image then show
            var img = new Image();
            img.onload = function() {
                productImageEl.src = img.src;
                preloadedImages[imageUrl] = img;
                showState('product_display');
            };
            img.onerror = function() {
                console.error('[Overlay] Failed to load product image:', imageUrl);
                // Show product display anyway with broken image
                productImageEl.src = '';
                showState('product_display');
            };
            img.src = imageUrl;
        }
    }

    function hideOverlay() {
        cancelHideTimer();
        currentState = 'idle';

        overlayEl.classList.remove('overlay-visible');

        // Unmute audio
        muteAudio(false);

        // Report idle state
        if (socket && socket.connected) {
            socket.emit('overlay_state', 'idle', {});
        }
    }

    function scheduleHide(duration) {
        cancelHideTimer();
        hideTimer = setTimeout(hideOverlay, duration);
    }

    function cancelHideTimer() {
        if (hideTimer) {
            clearTimeout(hideTimer);
            hideTimer = null;
        }
    }

    // ----------------------------------------------------------------
    // Audio Control
    // ----------------------------------------------------------------

    function muteAudio(mute) {
        // Try to mute/unmute any playing video/audio elements in the main zone
        try {
            var mainZone = document.getElementById('main');
            if (mainZone) {
                var mediaElements = mainZone.querySelectorAll('video, audio');
                for (var i = 0; i < mediaElements.length; i++) {
                    mediaElements[i].muted = mute;
                }
            }
        } catch(e) {
            // Ignore - media elements may not exist
        }
    }

    // ----------------------------------------------------------------
    // Status indicator
    // ----------------------------------------------------------------

    function setStatus(status) {
        if (!statusEl) return;
        statusEl.className = 'overlay-status overlay-status-' + status;
    }

    // ----------------------------------------------------------------
    // Image Preloading
    // ----------------------------------------------------------------

    function preloadEventImages() {
        // Preload static event images for instant display
        var images = [
            '/overlay/assets/image_verify.jpg',
            '/overlay/assets/cannot_accept.jpg',
            '/overlay/assets/barcode_not_qr.jpg',
            '/overlay/assets/deposit_waiting.jpg',
            '/overlay/assets/item_not_detected.jpg'
        ];

        images.forEach(function(url) {
            var img = new Image();
            img.onload = function() {
                preloadedImages[url] = img;
                console.log('[Overlay] Preloaded:', url);
            };
            img.src = url;
        });
    }

    // ----------------------------------------------------------------
    // Initialize
    // ----------------------------------------------------------------

    function init() {
        console.log('[Overlay] Initializing overlay client');

        // Start hidden
        overlayEl.classList.remove('overlay-visible');

        // Preload event images
        preloadEventImages();

        // Connect to server
        connect();

        console.log('[Overlay] Overlay client ready');
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
