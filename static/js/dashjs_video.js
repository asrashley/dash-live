(function(){
    'use strict';
    var dashlive = window.dashlive;

    if (dashlive === undefined) {
        window.dashlive = dashlive = {};
    }

    dashlive.setupDashjsPlayer = function(vid, source, mimeType) {
        var player = dashjs.MediaPlayer().create();
        player.initialize(vid, source, true);
    };

    if (dashlive.setupVideoPlayer === undefined) {
        dashlive.setupVideoPlayer = dashlive.setupDashjsPlayer;
    }
})(window);
