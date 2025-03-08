/* jshint esversion: 5, varstmt: false */
/* globals $ */
(function(){
    'use strict';
    var dashlive = window.dashlive;

    if (dashlive === undefined) {
	window.dashlive = dashlive = {};
    }
    dashlive.genStatusFn = function(evName){
        return function(ev){
            var error, target, msg = new Date().toISOString()+': '+evName;
            if (evName=="error"){
                target = ev.target;
                if (target && target.nodeName === "SOURCE") {
                    target = target.parentElement;
                }
                if (target && target.error) {
                    error = target.error;
                    msg += " "+error.code+":"+error.message;
                } else if(ev.detail) {
                    ev = ev.detail;
                }
            }
            $('#status').prepend('<p>'+msg+'</p>');
            while($('#status > p').length > 10){
                $('#status > p').last().remove();
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
