function activate(active) {
  if (!(active === true || active == false)) {
    return;
  }
  $.post('/activate', {
    'active': JSON.stringify(active),
  }, function(res) {
    console.log(res);
    if (res.success) {
      if (active) {
        showActivated();
      } else {
        window.location.reload();
      }
    }
  });
}

function showActivated() {
  var activatedHtml = ' \
      <h1> \
        Success! Your Kindlebox is active. \
      </h1> \
      <div> \
        Any books you add to <code>Dropbox/kindlebox</code> will be sent to your Kindle. \
      </div> \
      <a href="javascript: activate(false)" class="instruction-btn"> \
        <div class="instruction instruction-action start-stop"> \
          <div class="instruction-action-content"> \
            Stop Kindlebox \
          </div> \
        </div> \
      </a> \
      ';
  $('#content').empty().append(activatedHtml);
}

// Show the emailer instruction
function showEmailer(emailer) {
  var instructionHtml = ' \
      <div id="emailer-instruction" class="instruction-row"> \
        <div class="instruction-num"> \
          3. \
        </div> \
        <div id="emailer-text" class="instruction"> \
          Kindlebox works by emailing the books in your Dropbox folder to your Kindle. Here\'s your Kindlebox emailer: \
          <pre id="emailer" class="instruction-action">' + emailer + '</pre> \
          <p>To start receiving books through Kindlebox:</p> \
          <ul> \
            <li>Visit <a href="https://www.amazon.com/manageyourkindle" target="_blank">Manage Your Content and Devices</a> at amazon.com</li> \
            <li>Go to the <b>Settings</b> tab</li> \
            <li>Scroll down to <b>Personal Document Settings</b></li> \
            <li>Add the above email address to your <b>Approved Personal Document E-mail List</b></li> \
          </ul> \
          <p>And finally...</p> \
        </div> \
      </div> \
      <div class="instruction-row"> \
        <div class="instruction-num"> \
          4. \
        </div> \
        <a href="javascript: activate(true)" class="instruction-btn"> \
          <div class="instruction uncentered-action instruction-action"> \
            <div class="instruction-action-content"> \
              Activate Kindlebox! \
            </div> \
          </div> \
        </a> \
      </div> \
      ';
  if ($('#emailer-instruction').length == 0) {
    $('#content').append(instructionHtml);
  }
}

$(function() {
  var kindleComWidth = $('#kindle-com').outerWidth();
  var formWidth = $('#user-info-form').innerWidth();
  $('#kindle-name').width(formWidth - kindleComWidth - 45);
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
        $('#kindle-name').attr('saved_value', $('#kindle-name').val());
        $(':focus').blur();
      }
    });
  });

  // Effects for the Kindle username form.
  $('#kindle-name').attr('saved_value', $('#kindle-name').val());
  $('#kindle-name').hover(function() {
    $('#kindle-name-instruction').removeClass('instruction-completed');
  }, function() {
    var saved = $(this).val() == $(this).attr('saved_value');
    if ($(':focus').attr('id') != 'kindle-name' && saved) {
      $('#kindle-name-instruction').addClass('instruction-completed');
    }
  }).focus(function() {
    $('#kindle-name-instruction').removeClass('instruction-completed');
  }).blur(function() {
    var saved = $(this).val() == $(this).attr('saved_value');
    if (saved) {
      $('#kindle-name-instruction').addClass('instruction-completed');
    }
  });

  $('#emailer').click(function() {
      $(this).selectText();
  });
});
