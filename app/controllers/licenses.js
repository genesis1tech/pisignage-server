import fs from 'fs/promises';
import path from 'path';
import { exec } from 'child_process';
import mongoose from 'mongoose';
import config from '../../config/config.js';
import rest from '../others/restware.js';
import ip from 'ip';

const serverIp = ip.address();
const Settings = mongoose.model('Settings');

let settingsModel = null;

let licenseDir = config.licenseDirPath;


const getTxtFiles = async () => {
    try {
        const files = await fs.readdir(licenseDir);
        const txtOnly = files.filter(file => /\.txt$/i.test(file));
        return txtOnly;
    } catch (err) {
        throw err;
    }
};

export const index = async (req, res) => {
    try {
        const files = await getTxtFiles();
        return rest.sendSuccess(res, 'total license list', files);
    } catch (err) {
        return rest.sendError(res, 'error in reading license directory', err);
    }
};


export const saveLicense = async (req, res) => {
    try {
        const uploadedFiles = req.files["assets"];
        const savedFiles = [];
        
        // Process each file sequentially
        for (const file of uploadedFiles) {
            try {
                await fs.rename(file.path, path.join(licenseDir, file.originalname));
                savedFiles.push({ name: file.originalname, size: file.size });
            } catch (err) {
                return rest.sendError(res, 'Error in saving license', err);
            }
        }
        
        return rest.sendSuccess(res, 'License saved successfully', savedFiles);
        
    } catch (err) {
        return rest.sendError(res, 'Error processing license files', err);
    }
};

export const deleteLicense = async (req, res) => {
    try {
        const filename = req.params['filename'];
        const filePath = path.join(licenseDir, filename);
        await fs.unlink(filePath);
        const files = await getTxtFiles();
        return rest.sendSuccess(res, 'License deleted successfully', files);
    } catch (err) {
        const filename = req.params['filename'] || 'unknown';
        return rest.sendError(res, `Error deleting license "${filename}"`, err);
    }
}

exports.getSettingsModel = function(cb) {
    Settings.findOne(function (err, settings) {
        if (err || !settings) {
            if (settingsModel) {
                cb(null, settingsModel)
            } else {
                settingsModel = new Settings();
                settingsModel.save(cb);
            }
        } else {
            cb(null,settings);
        }
    })
}

exports.getSettings = function(req,res) {
    exports.getSettingsModel(function (err, data) {
        if (err) {
            return rest.sendError(res, 'Unable to access Settings', err);
        } else {
            var obj = data.toObject()
            obj.serverIp = serverIp;
            exec('git log -1 --format="%cd" && git log -1 --format="%H"',function(err,stdout,stderr){
                if(err || stderr){
                    obj.date = 'N/A';
                    obj.version = 'N/A';
                    console.log('There was an error obtaining the current server version from git:');
                    console.log(stderr);
                }else{
                    stdout = stdout.trim().split('\n');
                    obj.date = [stdout[0].split(' ')[1],stdout[0].split(' ')[2],stdout[0].split(' ')[4]].join(' '); 
                    obj.version = stdout[1].slice(0,6);
                }
                return rest.sendSuccess(res, 'Settings', obj);
            });
        }
    })
}

exports.updateSettings = function(req,res) {
    var restart;
    Settings.findOne(function (err, settings) {
        if (err)
            return rest.sendError(res, 'Unable to update Settings', err);

        //if (settings.installation != req.body.installation)
        restart = true;
        if (settings)
            settings = _.extend(settings, req.body)
        else
            settings = new Settings(req.body);
        settings.save(function (err, data) {
            if (err) {
                rest.sendError(res, 'Unable to update Settings', err);
            } else {
                rest.sendSuccess(res, 'Settings Saved', data);
            }
            if (restart)  {
                console.log("restarting server")
                require('child_process').fork(require.main.filename);
                process.exit(0);
            }
        });
    })
}

exports.getSettingsModel(function(err,settings){
    licenseDir = config.licenseDirPath+(settings.installation || "local")
})

