/* jshint esversion: 5, varstmt: false */
/* globals $ */

$(document).ready(function(){
  'use strict';
  var link;
  if (typeof(document.body.style.grid) === undefined ||
      /legacy/.test(document.location.search)) {
    link = document.createElement('link');
    link.setAttribute('rel', 'stylesheet');
    link.setAttribute('href', '/static/css/legacy.css');
    document.head.appendChild(link);
  }
});

