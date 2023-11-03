/* jshint esversion: 5, varstmt: false */
/* globals $, console */
(function(){
    'use strict';
    var dashlive = window.dashlive;

    if (dashlive === undefined) {
	window.dashlive = dashlive = {};
    }
    dashlive.genStatusFn = function(evName){
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
            while($('#status > p').length>5){
                $('#status > p').first().remove();
            }
        };
    };

    dashlive.formatTimecode = function(secs, asString){
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
            return {hours:hrs, minutes:mins, seconds:secs,};
        }
        rv = (('00'+mins).slice(-2))+':'+(('00'+secs).slice(-2));
        rv = (('00'+hrs).slice(-2))+':'+rv;
        return rv;
    };

})(window);
