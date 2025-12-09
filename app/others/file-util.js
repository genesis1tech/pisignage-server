import fs from 'fs/promises';
import sanitizeHtml from 'sanitize-html';
import path from 'path';

const library = '\n<script src="../piSignagePro/templates/screen.min.js"></script>\n';


// In old code sanitized data was not written back to the file, hence adding only library to the file. Need to check 
// In server2 no sanitization is done.

export const modifyHTML = async (assetsDir, templateName) => {
    if (!templateName) {
        return;
    }

    const templatePath = path.join(assetsDir, templateName);

    try {
        // Read the HTML file
        const data = await fs.readFile(templatePath, 'utf8');

        // Optional: Apply sanitization if needed
        /* const sanitizedData = sanitizeHtml(data, {
            allowedTags: [
                '!DOCTYPE', 'html', 'head', 'meta', 'title', 'body', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                'blockquote', 'p', 'a', 'ul', 'ol', 'nl', 'li', 'b', 'i', 'strong', 'em', 'strike', 'code',
                'hr', 'br', 'div', 'table', 'thead', 'caption', 'tbody', 'tr', 'th', 'td', 'pre',
                'marquee', 'style', 'iframe', 'link', 'script', 'img'
            ],
            allowedAttributes: false
        }); */

        // Find </body> tag
        const closingBodyIndex = data.lastIndexOf('</body>');
        
        if (closingBodyIndex === -1) {
            console.warn(`No </body> tag found in ${templateName}, skipping modification`);
            return;
        }

        // Inject library before </body>
        const modifiedData = data.slice(0, closingBodyIndex) + library + data.slice(closingBodyIndex);

        // Write back to file
        await fs.writeFile(templatePath, modifiedData, 'utf8');
        console.log(`Successfully modified ${templateName}`);
    } catch (err) {
        console.error(`Error modifying HTML template ${templateName}:`, err);
        throw err;
    }
};