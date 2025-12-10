import FeedParser from 'feedparser';
import axios from 'axios';
import { sendError, sendSuccess } from '../others/restware.js';

export const getFeeds = async (req, res) => {
    const { link: encodedLink = '', feedlimit = 100 } = req.query;
    const feedLimit = parseInt(feedlimit);
    
    if (!encodedLink) {
        return sendError(res, 'Please provide a link to fetch RSS as query parameter link=<link>');
    }
    
    // Check if link has any protocol, if not add http://
    let link = decodeURIComponent(encodedLink);
    if (link.indexOf('://') === -1) {
        link = 'http://' + link;
    }
    
    const news = [];
    res.replySent = false;
    
    try {
        const response = await axios({
            method: 'GET',
            url: link,
            responseType: 'stream',
            timeout: 60000
        });
        
        const stream = response.data;
        const status = response.status;
        
        if (status !== 200) {
            return sendError(res, 'Bad status code, can\'t fetch feeds from given URL');
        }
        
        const feedparser = new FeedParser({ feedUrl: link });
        
        stream.setEncoding('utf8');
        stream.pipe(feedparser);
        
        feedparser.on('error', function (error) {
            if (!res.replySent) {
                res.replySent = true;
                return sendError(res, 'Feedparser error, please check RSS feed URL', error);
            }
        });
        
        feedparser.on('readable', function () {
            const feedStream = this;
            let item;
            
            while ((item = feedStream.read())) {
                if (item.title) {
                    item.title = item.title.replace(/'/g, '`');
                }
                if (item.description) {
                    item.description = item.description.replace(/'/g, '`');
                }
                
                if (news.length < feedLimit) {
                    news.push(item);
                } else {
                    break;
                }
            }
        });
        
        feedparser.on('end', function () {
            if (!res.replySent) {
                res.replySent = true;
                return sendSuccess(res, 'RSS feeds', news);
            }
        });
        
    } catch (error) {
        if (!res.replySent) {
            res.replySent = true;
            return sendError(res, 'Request error, please check RSS feed URL', error.message);
        }
    }
};