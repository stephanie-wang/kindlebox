// Show the emailer instruction
function showEmailer(emailer) {
  var instructionHtml = ' \
      <div id="emailer-instruction" class="instruction-row"> \
        <div class="instruction-num"> \
          3. \
        </div> \
        <div class="instruction"> \
          Your Kindlebox emailer is:  \
          <pre class="instruction-action">' + emailer + '</pre> \
        </div> \
      </div> \
      ';
  if ($('#emailer-instruction').length == 0) {
    $('#content').append(instructionHtml);
  }
}

$(function() {
  // Show the emailer instruction after successfully submitting a Kindle
  // username.
  $('#user-info-form').submit(function(evt) {
    evt.preventDefault();
    var kindleName = $('#kindle-name').val();
    $.post('/set-user-info', {
      'kindle_name': kindleName
    }, function(data) {
      if (data.success) {
        showEmailer(data.emailer);
        $(':focus').blur();
        $('#kindle-name-instruction').addClass('instruction-completed');
      }
    });
  });

  // Effects for the Kindle username form.
  $('#kindle-name').hover(function() {
    $('#kindle-name-instruction').removeClass('instruction-completed');
  }, function() {
    if ($(':focus').attr('id') != 'kindle-name') {
      $('#kindle-name-instruction').addClass('instruction-completed');
    }
  }).focus(function() {
    $('#kindle-name-instruction').removeClass('instruction-completed');
  });
});
