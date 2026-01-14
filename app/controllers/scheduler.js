import scheduler from 'node-schedule';
import http from 'http';
import fs from 'fs/promises'; // Using promises version for modern async/await
import path from 'path';
import config from '../../config/config.js';
import fsSync from 'fs';

let dayScheduler;

const serverFile = path.join(config.releasesDir, "server-package.json");
const serverFile_p2 = path.join(config.releasesDir, "server-package-p2.json");
const packageJsonFile_p2 = path.join(config.releasesDir, "package-p2.json");
const packageJsonFile = path.join(config.releasesDir, "package.json");

const download = (url, dest) => {
    return new Promise((resolve, reject) => {
        const file = fsSync.createWriteStream(dest);
        
        http.get(url, (response) => {
            console.log(`Downloading ${url}`);
            
            response.on('data', () => {
                process.stdout.write("#");
            }).pipe(file);
            
            file.on('finish', () => {
                console.log("Done");
                file.close(resolve);
            });
        }).on('error', async (err) => {
            // Delete the file on error
            await fs.unlink(dest).catch(() => {});
            reject(new Error(err.message));
        });
    });
};


const checkAndDownloadImage = async () => {
    let serverVersion, localVersion, serverVersion_p2, localVersion_p2;
    let update = false;

    try {
        // Phase 1: Download version files (parallel for speed)
        console.log('Checking for updates...');
        await Promise.all([
            download("http://pisignage.com/releases/package.json", serverFile),
            download("http://pisignage.com/releases/package-p2.json", serverFile_p2)
        ]);

        // Phase 2: Parse server versions
        try {
            const serverdata = await fs.readFile(serverFile, 'utf-8');
            serverVersion = JSON.parse(serverdata).version;
            
            const serverdata_p2 = await fs.readFile(serverFile_p2, 'utf-8');
            serverVersion_p2 = JSON.parse(serverdata_p2).version;
        } catch (e) {
            console.error('Failed to parse server version files:', e);
            return;
        }

        // Phase 3: Check if local package files exist
        try {
            await fs.stat(packageJsonFile);
            await fs.stat(packageJsonFile_p2);
        } catch (err) {
            update = true;
        }

        // Phase 4: Compare with local versions (if files exist)
        if (!update) {
            try {
                const localData = await fs.readFile(packageJsonFile, 'utf-8');
                localVersion = JSON.parse(localData).version;
                
                const localData_p2 = await fs.readFile(packageJsonFile_p2, 'utf-8');
                localVersion_p2 = JSON.parse(localData_p2).version;

                if (serverVersion !== localVersion || serverVersion_p2 !== localVersion_p2) {
                    update = true;
                }
            } catch (e) {
                update = true;
            }
        }

        // Phase 5: Check if image files exist
        if (!update) {
            try {
                await fs.access(
                    path.join(config.releasesDir, `piimage${serverVersion}-v14.zip`),
                    fs.constants.F_OK
                );
                await fs.access(
                    path.join(config.releasesDir, `piimage${serverVersion_p2}-p2-v20.zip`),
                    fs.constants.F_OK
                );
            } catch (err) {
                update = true;
                console.log('Image files missing, will download');
            }
        }

        // Early exit if no update needed
        if (!update) {
            console.log('Already up to date');
            return;
        }

        // Phase 6: Download and install updates
        console.log(`New version is available: ${serverVersion}`);
        
        // Define all file paths
        const serverLink = `http://pisignage.com/releases/piimage${serverVersion}.zip`;
        const imageFile = path.join(config.releasesDir, `piimage${serverVersion}.zip`);
        
        const serverLinkV6 = `http://pisignage.com/releases/piimage${serverVersion}-v6.zip`;
        const imageFileV6 = path.join(config.releasesDir, `piimage${serverVersion}-v6.zip`);
        const linkFileV6 = path.join(config.releasesDir, "pi-image-v6.zip");
        const linkFileV6_2 = path.join(
            config.releasesDir,
            `piimage${serverVersion}`.slice(0, `piimage${serverVersion}`.indexOf(".")) + "-v6.zip"
        );
        
        const serverLinkV14 = `http://pisignage.com/releases/piimage${serverVersion}-v14.zip`;
        const imageFileV14 = path.join(config.releasesDir, `piimage${serverVersion}-v14.zip`);
        const linkFileV14 = path.join(config.releasesDir, "pi-image-v14.zip");
        const linkFile = path.join(config.releasesDir, "pi-image.zip");
        
        const serverLink_p2 = `http://pisignage.com/releases/piimage${serverVersion_p2}-p2-v14.zip`;
        const imageFile_p2 = path.join(config.releasesDir, `piimage${serverVersion_p2}-p2-v14.zip`);
        const linkFile_p2 = path.join(config.releasesDir, "pi-image-p2-v14.zip");
        
        const serverLink_p2_v20 = `http://pisignage.com/releases/piimage${serverVersion_p2}-p2-v20.zip`;
        const imageFile_p2_v20 = path.join(config.releasesDir, `piimage${serverVersion_p2}-p2-v20.zip`);
        const linkFile_p2_v20 = path.join(config.releasesDir, "pi-image-p2-v20.zip");

        // Download all images sequentially (they're large files)
        await download(serverLink, imageFile);
        await download(serverLinkV6, imageFileV6);
        await download(serverLinkV14, imageFileV14);
        await download(serverLink_p2, imageFile_p2);
        await download(serverLink_p2_v20, imageFile_p2_v20);

        // Helper function to safely create symlink
        const createSymlink = async (target, link) => {
            try {
                await fs.unlink(link).catch(() => {}); // Remove old link if exists
                await fs.symlink(target, link);
            } catch (err) {
                console.error(`Failed to create symlink ${link}:`, err);
            }
        };

        // Create all symbolic links (can run in parallel)
        await Promise.all([
            createSymlink(imageFile, linkFile),
            createSymlink(imageFileV6, linkFileV6),
            createSymlink(imageFileV6, linkFileV6_2),
            createSymlink(imageFileV14, linkFileV14),
            createSymlink(imageFile_p2, linkFile_p2),
            createSymlink(imageFile_p2_v20, linkFile_p2_v20)
        ]);

        // Update local package.json files
        await fs.unlink(packageJsonFile).catch(() => {});
        await fs.rename(serverFile, packageJsonFile);
        console.log(`piSignage image updated to ${serverVersion}`);

        await fs.unlink(packageJsonFile_p2).catch(() => {});
        await fs.rename(serverFile_p2, packageJsonFile_p2);
        console.log(`player 2 image updated to ${serverVersion_p2}`);

    } catch (err) {
        console.error('Update failed:', err);
    }
};

// Schedule to run daily at midnight (00:00)
dayScheduler = scheduler.scheduleJob({ hour: 0, minute: 0 }, checkAndDownloadImage);

// Run immediately on startup
checkAndDownloadImage();

