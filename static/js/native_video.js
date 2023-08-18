(function () {
    'use strict';
    var dashlive = window.dashlive;

    if (dashlive === undefined) {
        window.dashlive = dashlive = {};
    }

    dashlive.setupNativeVideoPlayer = function(vid, source, mimeType) {
        var src;
        src = document.createElement('source');
        src.setAttribute('type', mimeType);
        src.setAttribute('src', source);
        $(src).on('error', function(ev){
            console.error('playback failed');
            console.dir(ev);
        });
        $(vid).on('canplay',function(){ this.play(); });
        vid.appendChild(src);
        vid.load();
    };

    dashlive.setupVideoPlayer = function(vid, source, mimeType) {
        if (vid.canPlayType(mimeType)) {
            return dashlive.setupNativeVideoPlayer(vid, source, mimeType);
        }
        console.log('mimeType ' + mimeType +
            ' not supported by <video> element, trying to fall-back to MSE/EME');
        if (dashlive.setupShakaPlayer) {
            console.log('Using Shaka video player');
            return dashlive.setupShakaPlayer(vid, source, mimeType);
        }
        if (dashlive.setupDashjsPlayer) {
            console.log('Using dash.js video player');
            return dashlive.setupDashjsPlayer(vid, source, mimeType);
        }
        console.error('No MSE/EME video player has been configured');
    };
})();
