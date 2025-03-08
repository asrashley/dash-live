/* jshint esversion: 5, varstmt: false */
/* globals $, console */

(function () {
  "use strict";
  var dashlive = window.dashlive;

  if (dashlive === undefined) {
    window.dashlive = dashlive = {};
  }

  dashlive.setupVideoPlayer = function (vid, source, mimeType) {
    var src;
    src = document.createElement("source");
    src.setAttribute("type", mimeType);
    src.setAttribute("src", source);
    $(src).on("error", function (ev) {
      var error = ev.target.parentElement.error;
      if (error) {
        console.error("playback failed", error.code, error.message);
        $("#status").prepend(
          "<p>error: " + error.code + ":" + error.message + "</p>"
        );
      } else {
        $("#status").prepend("<p>Playback error</p>");
      }
    });
    $(vid).on("canplay", function () {
      this.play();
    });
    vid.appendChild(src);
    vid.load();
  };
})();
