$(document).ready(function(){
  'use strict';
  function changePage(anchor){
    var $a = $(anchor);
    document.location.assign('/video/'+$a.data('testcase'));
  }

  $('body').on('keydown', function(ev){
    var btn=null;

    if(ev.keyCode>=48 && ev.keyCode<=57){
      btn = $('#btn'+String.fromCharCode(ev.keyCode));
      switch(ev.keyCode){
      case 48: // 0
        if(btn && btn.length && btn.hasClass('prev')){
          document.location.assign(btn.find('a').attr('href'));
          return;
        }
        break;
      case 57: // 9
        if(btn && btn.length && btn.hasClass('next')){
          document.location.assign(btn.find('a').attr('href'));
          return;
        }
        break;
      }
      if(btn && btn.length){
        changePage(btn.find('a')[0]);
      }
    }
  });
  $('.btn-grid a').on('click', function(ev){
    if(ev.target.classList.contains('prev') || ev.target.classList.contains('prev')){
      /* follow the link for prev/next page links */
      return(true);
    }
    changePage(ev.target);
    ev.preventDefault();
    return(false);
  });
  /*$('.btn p').on('mouseenter', function(ev){

  }); */
  $('.tooltip').tooltipster();
});