export const sendSuccess = (res, msg, data) => {
    if (!res) return;

    const out = {
        stat_message: msg,
        data,
        success: true
    };

    res.contentType('json');
    return res.json(out);
};

export const sendError = (res, msg, err) => {
    if (!res) return;

    const errmsg = err ? err.toString() : '';
    const out = {
        stat_message: `${msg} ${errmsg}`,
        success: false
    };

    res.contentType('json');
    return res.json(out);
};