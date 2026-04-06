'use strict';

var express = require('express'),
    path = require('path'),
    fs = require('fs'),
    config = require('./config'),
    serveIndex = require('serve-index');

var favicon = require('serve-favicon'),             //express middleware
    errorHandler = require('errorhandler'),
    logger = require('morgan'),
    methodOverride = require('method-override'),
    bodyParser = require('body-parser'),
    cookieParser = require('cookie-parser'),
    helmet = require('helmet'),
    rateLimit = require('express-rate-limit');



// CORS middleware — restrict to allowlisted origins
var allowedOrigins = process.env.CORS_ALLOWED_ORIGINS
    ? process.env.CORS_ALLOWED_ORIGINS.split(',').map(function(s) { return s.trim(); })
    : [];

var allowCrossDomain = function (req, res, next) {
    var origin = req.headers.origin;
    if (origin && allowedOrigins.indexOf(origin) !== -1) {
        res.header('Access-Control-Allow-Origin', origin);
        res.header('Access-Control-Allow-Credentials', 'true');
        res.header('Vary', 'Origin');
        res.header('Access-Control-Expose-Headers', 'Content-Length');
        res.header('Access-Control-Allow-Methods', 'HEAD,GET,PUT,POST,DELETE,OPTIONS');
        res.header('Access-Control-Allow-Headers', 'Content-Type,Content-Length,Response-Type,X-Requested-With,origin,accept,Authorization,x-access-token,Last-Modified');
    }

    if (req.method === 'OPTIONS') {
        if (origin && allowedOrigins.indexOf(origin) !== -1) {
            res.sendStatus(200);
        } else {
            res.sendStatus(403);
        }
        return;
    }
    next();
}

// Settings cache for auth (avoids hitting MongoDB on every request)
var _settingsCache = null;
var _settingsCacheTime = 0;
var SETTINGS_CACHE_TTL = 60000; // 60 seconds

function getCachedSettings(callback) {
    var now = Date.now();
    if (_settingsCache && (now - _settingsCacheTime) < SETTINGS_CACHE_TTL) {
        return callback(null, _settingsCache);
    }
    require('../app/controllers/licenses').getSettingsModel(function(err, settings) {
        if (!err && settings) {
            _settingsCache = settings;
            _settingsCacheTime = now;
        }
        callback(err, settings);
    });
}

var basicHttpAuth = function(req, res, next) {
    // Bypass auth for health check endpoint
    if (req.path === '/api/health') {
        return next();
    }

    var auth = req.headers['authorization'];

    if (!auth) {
        res.statusCode = 401;
        res.setHeader('WWW-Authenticate', 'Basic realm="Secure Area"');
        res.end('<html><body>Authentication required to access this path</body></html>');
    } else {
        var tmp = auth.split(' ');
        var buf = Buffer.from(tmp[1], 'base64');
        var plain_auth = buf.toString();
        var creds = plain_auth.split(':');
        var username = creds[0];
        var password = creds[1];

        // Environment variable override takes precedence over DB settings
        var envUser = process.env.AUTH_USER;
        var envPassword = process.env.AUTH_PASSWORD;

        if (envUser && envPassword) {
            if (username === envUser && password === envPassword) {
                return next();
            }
            console.log("http request rejected for " + req.path);
            res.statusCode = 401;
            res.setHeader('WWW-Authenticate', 'Basic realm="Secure Area"');
            return res.end('<html><body>Authentication required to access this path</body></html>');
        }

        getCachedSettings(function(err, settings) {
            if (!settings || !settings.authCredentials) {
                return next();
            }

            var validUser = !settings.authCredentials.user || username === settings.authCredentials.user;
            var validPass = !settings.authCredentials.password || password === settings.authCredentials.password;

            if (validUser && validPass) {
                next();
            } else {
                console.log("http request rejected for " + req.path);
                res.statusCode = 401;
                res.setHeader('WWW-Authenticate', 'Basic realm="Secure Area"');
                res.end('<html><body>Authentication required to access this path</body></html>');
            }
        });
    }
}

module.exports = function (app) {

    // Security headers
    app.use(helmet({
        contentSecurityPolicy: false // piSignage dashboard uses inline scripts
    }));

    // Rate limiting on API routes
    app.use('/api/', rateLimit({
        windowMs: 15 * 60 * 1000, // 15 minutes
        max: 500, // limit each IP to 500 requests per window
        standardHeaders: true,
        legacyHeaders: false,
        skip: function(req) { return req.path === '/health'; }
    }));

    //CORS related  http://stackoverflow.com/questions/7067966/how-to-allow-cors-in-express-nodejs
    app.use(allowCrossDomain);

    if (process.env.NODE_ENV == 'development') {

        // Disable caching of scripts for easier testing
        app.use(function noCache(req, res, next) {
            if (req.url.indexOf('/scripts/') === 0) {
                res.header('Cache-Control', 'no-cache, no-store, must-revalidate');
                res.header('Pragma', 'no-cache');
                res.header('Expires', 0);
            }
            next();
        });
        app.use(errorHandler());
        app.locals.pretty = true;
        app.locals.compileDebug = true;
    }

    if (process.env.NODE_ENV == 'production') {
        app.use(favicon(path.join(config.root, 'public/app/img', 'favicon.ico')));
    };

    //app.use(auth.connect(digest));      //can specify specific routes for auth also
    app.use(basicHttpAuth);

    //app.use('/sync_folders',serveIndex(config.syncDir));
    app.use('/sync_folders',function(req, res, next){
            // Player uses --no-cache header in wget to download assets. The --no-cache flag sends the following headers
            // Cache-Control: no-cache , Pragma: no-cache
            // This causes 200 OK response for all requests. Hence remove this header to minimise data-transfer costs.
            delete req.headers['cache-control'];  // delete header
            delete req.headers['pragma'];  // delete header
            fs.stat(path.join(config.syncDir,req.path), function(err, stat){
                if (!err && stat.isDirectory()) {
                    res.setHeader('Last-Modified', (new Date()).toUTCString());
                }
                next();
            })
        },
        serveIndex(config.syncDir)
    );
    app.use('/sync_folders',express.static(config.syncDir));
    app.use('/releases',express.static(config.releasesDir));
    app.use('/licenses',express.static(config.licenseDir));

    app.use('/media', express.static(path.join(config.mediaDir)));
    app.use(express.static(path.join(config.root, 'public')));

    app.set('view engine', 'pug');
    app.locals.basedir = config.viewDir; //for jade root

    app.set('views', config.viewDir);

    //app.use(logger('dev'));
    app.use(bodyParser.json());
    app.use(bodyParser.urlencoded({ extended: true }));
    app.use(methodOverride());

    app.use(cookieParser());

    app.use(require('./routes'));

    // custom error handler
    app.use(function (err, req, res, next) {
        if (err.message.indexOf('not found') >= 0)
            return next();
        //ignore range error as well
        if (err.message.indexOf('Range Not Satisfiable') >=0 )
            return res.send();
        console.error(err.stack)
        res.status(500).render('500')
    })

    app.use(function (req, res, next) {
        //res.redirect('/');
        res.status(404).render('404', {url: req.originalUrl})
    })
};
