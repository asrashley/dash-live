/* jshint esversion: 5, varstmt: false */
/* globals $, console, dashlive */
$(document).ready(function(){
  'use strict';
    var statusEvents=[
	'stalled','loadedmetadata', 'error', 'canplay', 'canplaythrough',
	'playing', 'ended', 'pause', 'resize', 'loadstart', 'seeking', 'seeked',];
    var hideMenuTimer = null;

    $('body').on('keydown', function(ev){
	switch(ev.which){
	case 32: /* space */
	    $('#vid-window').toggleClass('paused');
	    $('video').each(function(){
		if(this.paused) {
		    this.play();
		} else {
		    this.pause();
                }
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

    function hideMenu() {
	hideMenuTimer = null;
	$('header').addClass('rollup');
    }

    function showMenu() {
	if (hideMenuTimer) {
	    clearTimeout(hideMenuTimer);
	    hideMenuTimer = null;
	}
	$('header').removeClass('rollup');
    }

    function initPlayer() {
	var evname, vid, k;
	var dest = $('#vid-window');
	var mimeType = dest.data("type");
	var source = dest.data("src");

	vid = document.createElement('video');
	dest.append(vid);
	window.dashlive.setupVideoPlayer(vid, source, mimeType);
	for(k=0; k<statusEvents.length; ++k){
	    evname = statusEvents[k];
	    $(vid).on(evname, dashlive.genStatusFn(evname));
	}
	$(vid).on('seeked', function(){
	    $('#vid-window').removeClass('skip-forward skip-backward');
	});
	$(vid).on('timeupdate', function(){
	    $('#vid-window .timecode').text(dashlive.formatTimecode(this.currentTime, true));
	});
	$(vid).on('canplay',function(){
	    console.log("Starting playback");
	    vid.play();
	    hideMenuTimer = setTimeout(hideMenu, 2000);
	});
    }

    function startHideMenu() {
	if (hideMenuTimer) {
	    clearTimeout(hideMenuTimer);
	}
	hideMenuTimer = setTimeout(hideMenu, 1000);
    }

    $('header').hover(showMenu, startHideMenu);

    initPlayer();
});
