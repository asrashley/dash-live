(function() {
    if (typeof(document.body.style.grid) === undefined ||
	/legacy/.test(document.location.search)) {
	const link = document.createElement('link');
	link.setAttribute('rel', 'stylesheet');
	link.setAttribute('href', '/static/css/legacy.css');
	document.head.appendChild(link);
    }
})();
