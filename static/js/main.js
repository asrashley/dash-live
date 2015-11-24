$(document).ready(function(){
  'use strict';
  function changePage(anchor){
    var tc, $a = $(anchor);
    tc = $a.data('testcase');
    if(tc!==undefined){
        document.location.assign('/video/'+tc);
    }
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
    var anchor = ev.target;
    while(anchor.tagName!='A' && anchor.tagName!='TR'){
        anchor = anchor.parentNode;
    }
    if(anchor.classList.contains('prev') || anchor.classList.contains('next')){
      /* follow the link for prev/next page links */
      return(true);
    }
    changePage(anchor);
    ev.preventDefault();
    return(false);
  });
  /*$('.btn p').on('mouseenter', function(ev){

  }); */
  $('.tooltip').tooltipster();
});