import mongoose from 'mongoose';
const { Schema } = mongoose;

const GroupSchema = new Schema({
    name:                   {type: String, index: true, required: true, minlength: 1},
    description:            String,

    playlists:              [],
    playlistToSchedule:      String,
    defaultCustomTemplate:  String,
    combineDefaultPlaylist: {type: Boolean , default: false},
    playAllEligiblePlaylists: {type: Boolean , default: false},
    shuffleContent:         {type: Boolean , default: false},
    alternateContent:         {type: Boolean , default: false},
    timeToStopVideo:        {type: Number , default: 0 },
    
    assets:                 [],
    assetsValidity:         [],
    ticker:                 {},

    deployedPlaylists:      [],
    deployedAssets:         [],
    deployedTicker:         {},

    lastDeployed:           String,

    enableMpv:              {type: Boolean, default: false},
    mpvAudioDelay:          {type: String, default: '0'},
    selectedVideoPlayer:    {type: String, default: 'default'},
    disableWebUi:           {type: Boolean, default: false},
    disableWarnings:        {type: Boolean, default: false},
    enablePio:              {type: Boolean, default: false},
    disableAp:              {type: Boolean, default: false},

    orientation:            {type: String,default: 'landscape'},
    animationEnable:        {type: Boolean, default: false},
    animationType:          {type: String, default: null},
    resizeAssets:           {type: Boolean, default: true},
    videoKeepAspect:        {type: Boolean, default: false},
    videoShowSubtitles:     {type: Boolean, default: false},
    imageLetterboxed:       {type: Boolean, default: false},
    signageBackgroundColor: {type: String, default: "#000"},
    urlReloadDisable:       {type: Boolean, default: true},
    keepWeblinksInMemory:   {type: Boolean, default: false},
    loadPlaylistOnCompletion:{type: Boolean, default: false},
    resolution:             {type: String,default: 'auto'},
    sleep:                  {   enable: {type: Boolean,default: false},
                            ontime: {type: String},
                                offtime: {type: String}
    },
    reboot:                 {   enable: {type: Boolean,default: false},
                                time: { type: String},
                                absoluteTime: { type: String}
                            },
    kioskUi:                {   enable: {type: Boolean,default: false},
                                url:        {type: String},
                                timeout:    {type: Number}
                            },
    omxVolume:              {type: Number , default: 100 },

    logo:                   {type: String,default: null},
    logox:                  {type: Number,default: 10},
    logoy:                  {type: Number,default: 10},
    showClock:              {
                                enable: {type: Boolean, default: false},
                                format: {type: String, default: "12"},
                                position: {type: String, default: "bottom"}
                            },
    monitorArrangement:   {
                                mode: {type: String, default: "mirror"},
                                reverse: {type: Boolean, default: false}
                            },
    emergencyMessage:       {
                                enable: {type: Boolean, default: false},
                                msg: {type: String, default: ""},
                                hPos: {type: String, default: "middle"},
                                vPos: {type: String, default: "middle"}
                            },
    createdAt:              {type: Date, default: Date.now},
    createdBy:              {_id: {type: Schema.ObjectId, ref: 'User'}, name: String}
}
);




GroupSchema.statics = {

    async load(id) {
        return await this.findById(id);
    },

    async list(options) {
        const criteria = options.criteria || {};
        if (!(criteria.all || criteria.name)) {
            criteria.name = {"$not": /__player__/};
        }
        delete criteria.all;
        return await this.find(criteria)
            .sort({ name: 1 })
            .skip(options.perPage * options.page)
            .limit(options.perPage)
            .exec(); 

    }
}

export const Group = mongoose.model('Group', GroupSchema); 