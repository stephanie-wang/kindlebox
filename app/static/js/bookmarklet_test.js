function addScript(source) {
  var script = document.createElement("script");
  script.type = "text/javascript";
  script.src = source;
  document.getElementsByTagName('head')[0].appendChild(script);
}

function addCSS(source) {
  var cssLink = document.createElement("link");
  cssLink.href = source;
  cssLink.type = "text/css";
  cssLink.rel = "stylesheet";
  document.getElementsByTagName("head")[0].appendChild(cssLink);
}

addScript("https://getbookdrop.com/static/js/lib/jquery-1.11.1.min.js");
addScript("https://getbookdrop.com/static/js/lib/bootstrap.min.js");
addScript("https://getbookdrop.com/static/js/bookmarklet.js");
addCSS("https://getbookdrop.com/static/css/lib/bootstrap.min.css");

setDevice(1);
setTimeout(function() {
  showModal();
}, 0);
