$(window).load(function(){
  'use strict';
  var player, src, vid, context, estimator, evname;
  var k;
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
        }
    });

    function genStatusFn(evName){
        return function(ev){
            var msg = new Date().toISOString()+': '+evName;
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

    function initPlayer() {
        var dest = $('#vid-window');
        var mimeType = dest.data("type");
        var source = dest.data("src");
        vid = document.createElement('video');
        if(vid.canPlayType(mimeType)){
            src = document.createElement('source');
            src.setAttribute('type', mimeType);
            src.setAttribute('src', source);
            $(src).on('error', function(ev){
                console.error('playback failed');
                console.dir(ev);
            });
            $(vid).on('canplay',function(){ this.play(); });
            vid.appendChild(src);
            dest.append(vid);
            vid.load();
        }
        else{
            /* fall-back to use Shaka JavaScript player */
            dest.append(vid);
            shaka.polyfill.installAll();
            player = new shaka.Player(vid);
            vid.shakaPlayer = player;
            player.addEventListener('error', function(ev){
                console.error('playback failed');
                console.dir(ev);
            });
            $(vid).on('canplay',function(){
                console.log("Starting playback");
                vid.play();
            });
            player.load(source);
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
    }

    initPlayer();
});
