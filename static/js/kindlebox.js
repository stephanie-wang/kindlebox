// Show the emailer instruction
function showEmailer(emailer) {
  var instructionHtml = ' \
      <div id="emailer-instruction" class="instruction-row"> \
        <div class="instruction-num"> \
          3. \
        </div> \
        <div id="emailer-text" class="instruction"> \
          Kindlebox works by emailing the books in your Dropbox folder to your Kindle. Here\'s your Kindlebox emailer: \
          <pre class="instruction-action">' + emailer + '</pre> \
          <p>To start receiving books through Kindlebox, visit <a href="https://www.amazon.com/manageyourkindle">Manage Your Content and Devices</a> at amazon.com. Go to the <b>Settings</b> tab, scroll down to <b>Personal Document Settings</b>, and add the above email address to your <b>Approved Personal Document E-mail List</b>.</p> \
          <p>Finally, <a href="/activate" method="post">activate Kindlebox</a>.</p> \
        </div> \
      </div> \
      ';
  if ($('#emailer-instruction').length == 0) {
    $('#content').append(instructionHtml);
  }
}

$(function() {
  var kindleComWidth = $('#kindle-com').outerWidth();
  var formWidth = $('#user-info-form').innerWidth();
  $('#kindle-name').width(formWidth - kindleComWidth - 40);
  // Show the emailer instruction after successfully submitting a Kindle
  // username.
  $('#user-info-form').submit(function(evt) {
    evt.preventDefault();
    var kindleName = $('#kindle-name').val();
    if (kindleName.length == 0) {
      return;
    }
    $.post('/set-user-info', {
      'kindle_name': kindleName
    }, function(data) {
      if (data.success) {
        showEmailer(data.emailer);
        $(':focus').blur();
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
  }).blur(function() {
    $('#kindle-name-instruction').addClass('instruction-completed');
  });
});
