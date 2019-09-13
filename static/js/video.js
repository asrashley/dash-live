$(window).load(function(){
  'use strict';
  var statusEvents=['stalled','loadedmetadata', 'error', 'canplay', 'canplaythrough',
                    'playing', 'ended', 'pause', 'resize', 'loadstart', 'seeking', 'seeked'];

    $('body').on('keydown', function(ev){
        switch(ev.which){
        case 32: /* space */
            $('#vid-window').toggleClass('paused');
            $('video').each(function(){
                if(this.paused)
                    this.play();
                else
                    this.pause();
            });
            break;
        case 49: /* 1 key */
            window.open('','_self');
            window.close();
            break;
        case 27: /* ESC key */
        case 413: /* stop RCU key */
            $('#vid-window').addClass('stopped');
            $('video').each(function(){
                this.pause();
                if(this.shakaPlayer){
                    this.shakaPlayer.destroy();
                    delete this.shakaPlayer;
                }
                this.src='';
                try{
                    delete this.src;
                }
                catch(e){
                }
                this.load();
                $(this).remove();
            });
            break;
        case 415: /* 'play' RCU key */
            $('#vid-window').removeClass('paused');
            $('video').each(function(){
                this.play();
            });
            break;
        case 19: /* 'pause' RCU key */
            $('#vid-window').addClass('paused');
            $('video').each(function(){
                this.pause();
            });
            break;
        case 37: /* left cursor key */
        case 424: /* prev RCU key */
            $('#vid-window').addClass('skip-backward');
            $('video').each(function(){
                this.currentTime = Math.max(0, this.currentTime-30);
            });
            break;
        case 39: /* right cursor key */
        case 425: /* next RCU key */
            $('#vid-window').addClass('skip-forward');
            $('video').each(function(){
                this.currentTime += 30;
            });
            break;
        case 461: /* 'back' RCU key */
            if (typeof(window.history) !== "undefined") {
                history.back();
            } else {
                document.location = "/";
            }
            break;
        }
    });

    function genStatusFn(evName){
        return function(ev){
            var msg = new Date().toISOString()+': '+evName;
            if (evName=="error"){
                console.dir(ev);
                if(ev.detail) {
                    ev = ev.detail;
                }
                if(ev.code) {
                    msg += " " + ev.code + ":";
                }
                if(ev.message) {
                    msg += ' '+ev.message;
                }
            }
            $('#status').append('<p>'+msg+'</p>');
            console.log(msg);
            while($('#status > p').length>5){
                $('#status > p').first().remove();
            }
        };
    }

    function formatTimecode(secs, asString){
        var rv, hrs, mins;
        if(typeof(secs)==='object'){
            hrs = secs.hours;
            mins = secs.minutes;
            secs = secs.seconds;
        }
        else{
            hrs = Math.floor(secs/3600);
            mins = Math.floor(secs/60) % 60;
            secs = Math.floor(secs) % 60;
        }
        if(asString===false){
            return {hours:hrs, minutes:mins, seconds:secs};
        }
        rv = (('00'+mins).slice(-2))+':'+(('00'+secs).slice(-2));
        rv = (('00'+hrs).slice(-2))+':'+rv;
        return rv;
    }

    function setupNativeVideo(vid, source, mimeType) {
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
    }

    function setupShakaPlayer(vid, source, mimeType) {
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
        player.addEventListener('error', genStatusFn('error'));
        player.load(source).then(genStatusFn("loaded")).catch(genStatusFn('error'));
        $(vid).on('canplay',function(){
            vid.play();
        });
    }

    function initPlayer() {
        var evname, vid, k;
        var dest = $('#vid-window');
        var mimeType = dest.data("type");
        var source = dest.data("src");

        vid = document.createElement('video');
        dest.append(vid);
        if (vid.canPlayType(mimeType) && !/mse=[12]/.test(document.location.href)) {
            setupNativeVideo(vid, source, mimeType);
        }
        else{
            /* fall-back to use Shaka JavaScript player */
            setupShakaPlayer(vid, source, mimeType);
        }
        for(k=0; k<statusEvents.length; ++k){
            evname = statusEvents[k];
            $(vid).on(evname, genStatusFn(evname));
        }
        $(vid).on('seeked', function(){
            $('#vid-window').removeClass('skip-forward skip-backward');
        });
        $(vid).on('timeupdate', function(){
            $('#vid-window .timecode').text(formatTimecode(this.currentTime, true));
        });
        $(vid).on('canplay',function(){
            console.log("Starting playback");
            vid.play();
        });
    }

    initPlayer();
});
