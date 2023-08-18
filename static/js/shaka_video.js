(function(){
    'use strict';
    var dashlive = window.dashlive;

    if (dashlive === undefined) {
	window.dashlive = dashlive = {};
    }

    dashlive.setupShakaPlayer = function(vid, source, mimeType) {
        var player, laURL, laParams, parm, kid, shakaConfig;

        shakaConfig = {
            drm: {
                servers: {}
            }
        };
        shaka.polyfill.installAll();
        if (shaka.log && shaka.log.setLevel) {
            shaka.log.setLevel(shaka.log.Level.V1);
        }
        if (dashParameters.encrypted===true) {
            if (typeof(dashParameters.DRM.playready) !== "undefined") {
                laURL = 'https://test.playready.microsoft.com/service/rightsmanager.asmx?cfg=';
                laParams = []
                for (kid in dashParameters.keys) {
                    parm = '(kid:'+dashParameters.keys[kid].guidKid;
                    if (dashParameters.keys[kid].computed !== true) {
                        parm += ',contentkey:'+dashParameters.keys[kid].b64Key;
                    }
                    parm += ')';
                    laParams.push(parm);
                }
                laURL += laParams.join(',');
                shakaConfig.drm.servers['com.microsoft.playready'] = laURL;
            }
            if (typeof(dashParameters.DRM.clearkey) !== "undefined") {
                shakaConfig.drm.servers['org.w3.clearkey'] = dashParameters.DRM.clearkey.laurl;
            }
            if (/mse=2/.test(document.location.href)) {
                shakaConfig.drm.clearKeys = {};
                for (kid in dashParameters.keys) {
                    shakaConfig.drm.clearKeys[kid] = dashParameters.keys[kid].key;
                }
            }
        }
        player = new shaka.Player(vid);
        console.log(JSON.stringify(shakaConfig));
        player.configure(shakaConfig);
        vid.shakaPlayer = player;
        player.addEventListener('error', dashlive.genStatusFn('error'));
        player.load(source)
            .then(dashlive.genStatusFn("loaded"))
            .catch(dashlive.genStatusFn('error'));
        $(vid).on('canplay',function(){
            vid.play();
        });
    }
    if (dashlive.setupVideoPlayer === undefined) {
	dashlive.setupVideoPlayer = dashlive.setupShakaPlayer;
    }
})(window);

