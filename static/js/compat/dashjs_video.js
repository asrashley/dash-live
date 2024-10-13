/* jshint esversion: 5, varstmt: false */
/* globals $, console, dashjs */

(function(){
    'use strict';
    var dashlive = window.dashlive;

    if (window.dashlive === undefined) {
        window.dashlive = dashlive = {};
    }

    dashlive.setupDashjsPlayer = function(vid, source) {
	var $vid, player;

	$vid = $(vid);
	$vid.attr('controls', '');
        player = dashjs.MediaPlayer().create();
        player.initialize(vid, source, true);
        $(vid).on('canplay',function(){
	    console.log('start playback');
            vid.play();
        });
    };

    if (dashlive.setupVideoPlayer === undefined) {
        dashlive.setupVideoPlayer = dashlive.setupDashjsPlayer;
    }
})(window);
