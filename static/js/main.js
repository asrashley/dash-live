$(document).ready(function(){
	'use strict';
	function changePage(anchor){
		var $a = $(anchor);
		var title = [$(anchor.parentNode.parentNode).find('th').text(), $a.text().substring(2)];
		title = title.join(': ');
		document.location.assign('/video?url='+encodeURI($a.attr('href'))+'&title='+encodeURI(title));
	}
	
	$('body').on('keydown', function(ev){
		console.dir(ev);
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
		if(ev.target.classList.hasClass('prev') || ev.target.classList.hasClass('prev')){
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