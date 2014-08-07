$(function() {
  function animate(i, delay) {
    if (i > $('.icon').length) {
      return;
    }
    $($('.icon')[i]).animate({
      'top': 0,
      'opacity': 1,
    });
    window.setTimeout(function() {
      animate(i + 1, delay / 2)
    }, delay);
  }
  animate(0, 128);
});
