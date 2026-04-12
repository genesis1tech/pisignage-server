'use strict';

var mongoose = require('mongoose'),
    Player = mongoose.model('Player'),
    rest = require('../others/restware'),
    _ = require('lodash');

var oldSocketio = require('./server-socket'),
    newSocketio = require('./server-socket-new'),
    webSocket = require('./server-socket-ws');

// Valid overlay states matching the OverlayState enum from kiosk Python code
var VALID_STATES = [
    'idle', 'processing', 'deposit_waiting', 'product_display',
    'recycle_failure', 'no_match', 'qr_not_allowed'
];

// Auto-hide durations (seconds) for states that should auto-return to idle
var STATE_DURATIONS = {
    no_match: 5,
    qr_not_allowed: 5,
    product_display: 10,
    recycle_failure: 5
};

// In-memory timers for auto-hide per player
var autoHideTimers = {};

/**
 * Emit overlay_cmd to a connected player via the correct socket transport
 */
function emitOverlayCmd(player, state, data) {
    if (!player.socket || !player.isConnected) return;

    var socketio = player.webSocket ? webSocket :
                   (player.newSocketIo ? newSocketio : oldSocketio);
    socketio.emitMessage(player.socket, 'overlay_cmd', {
        state: state,
        data: data || {}
    });
}

/**
 * Schedule auto-hide for a player (returns to idle after duration)
 */
function scheduleAutoHide(playerId, duration) {
    clearAutoHide(playerId);
    autoHideTimers[playerId] = setTimeout(function() {
        delete autoHideTimers[playerId];
        Player.findById(playerId, function(err, player) {
            if (!err && player && player.overlayState !== 'idle') {
                player.overlayState = 'idle';
                player.overlayData = {};
                player.overlayLastUpdated = Date.now();
                player.save();
                emitOverlayCmd(player, 'idle', {});
            }
        });
    }, duration * 1000);
}

function clearAutoHide(playerId) {
    if (autoHideTimers[playerId]) {
        clearTimeout(autoHideTimers[playerId]);
        delete autoHideTimers[playerId];
    }
}

/**
 * GET /api/overlay/:playerid
 * Get the current overlay state for a player
 */
exports.getState = function(req, res) {
    var player = req.object;
    if (!player)
        return rest.sendError(res, 'Player not found');

    return rest.sendSuccess(res, 'Overlay state', {
        state: player.overlayState || 'idle',
        data: player.overlayData || {},
        lastUpdated: player.overlayLastUpdated
    });
};

/**
 * POST /api/overlay/:playerid
 * Set overlay state for a player and push to player via socket
 *
 * Body: { state: 'processing', data: { productImage: '...', productName: '...' } }
 */
exports.setState = function(req, res) {
    var player = req.object;
    if (!player)
        return rest.sendError(res, 'Player not found');

    var state = req.body.state;
    var data = req.body.data || {};

    if (!state || VALID_STATES.indexOf(state) === -1)
        return rest.sendError(res, 'Invalid overlay state. Valid states: ' + VALID_STATES.join(', '));

    var playerId = player._id.toString();

    // Clear any existing auto-hide timer
    clearAutoHide(playerId);

    player.overlayState = state;
    player.overlayData = data;
    player.overlayLastUpdated = Date.now();

    player.save(function(err) {
        if (err)
            return rest.sendError(res, 'Error saving overlay state', err);

        // Push to player via socket
        emitOverlayCmd(player, state, data);

        // Schedule auto-hide for states with durations
        if (STATE_DURATIONS[state]) {
            var duration = data.duration || STATE_DURATIONS[state];
            scheduleAutoHide(playerId, duration);
        }

        return rest.sendSuccess(res, 'Overlay state updated', {
            state: state,
            data: data,
            lastUpdated: player.overlayLastUpdated
        });
    });
};

/**
 * POST /api/overlay/:playerid/scan
 * Convenience endpoint: trigger a scan action flow
 *
 * Body: { barcode: '...', type: 'ean13' }
 * This sets state to 'processing' immediately.
 * The kiosk bridge or AWS IoT will call setState for subsequent state transitions.
 */
exports.triggerScan = function(req, res) {
    var player = req.object;
    if (!player)
        return rest.sendError(res, 'Player not found');

    var barcode = req.body.barcode;
    if (!barcode)
        return rest.sendError(res, 'Barcode data required');

    var playerId = player._id.toString();
    clearAutoHide(playerId);

    var data = {
        barcode: barcode,
        type: req.body.type || 'unknown',
        timestamp: Date.now()
    };

    player.overlayState = 'processing';
    player.overlayData = data;
    player.overlayLastUpdated = Date.now();

    player.save(function(err) {
        if (err)
            return rest.sendError(res, 'Error triggering scan', err);

        emitOverlayCmd(player, 'processing', data);

        return rest.sendSuccess(res, 'Scan triggered', {
            state: 'processing',
            data: data
        });
    });
};

/**
 * Handle overlay_state events from the custom layout WebSocket
 * Called from socket handlers when a player reports its overlay state
 */
exports.handleOverlayStateReport = function(socketId, state, data) {
    if (!state || VALID_STATES.indexOf(state) === -1) return;

    Player.findOne({socket: socketId}, function(err, player) {
        if (!err && player) {
            player.overlayState = state;
            player.overlayData = data || {};
            player.overlayLastUpdated = Date.now();
            player.save();
        }
    });
};
