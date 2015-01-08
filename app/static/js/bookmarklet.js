var KINDLEBOX_MODAL_ID = 'kindlebox-device-picker';
var KINDLEBOX_FORM_ID = 'kindlebox-devices-form';
var KINDLEBOX_DEVICES_ID = 'kindlebox-devices-container';

var kindleboxDevices = [];
var whitelistedEmailer = false;


function setDevice(deviceNum) {
  window.location.hash = '#/home/devices/' + deviceNum;
}

function htmlToString($html) {
  var text = '';
  try {
    text = $html[0].childNodes[0].textContent.trim();
  } catch(error) {
  }
  return text;
}

function getNumDevices() {
  return $('.deviceName_myx.a-size-base').length;
}

function getDevices() {
  if (kindleboxDevices.length > 0) {
    return kindleboxDevices;
  }

  var numDevices = getNumDevices();
  var devices = [];
  for (var i = 1; i <= numDevices; i++) {
    setDevice(i);
    var emailContainer = $('#dv_dt_email_value');
    if (emailContainer.length > 0) {
      var device = {
        'tag': htmlToString($('#dv_dt_name_value')),
        'email': htmlToString(emailContainer),
        'type': htmlToString($('#deviceDetail_type_myx_value')),
      };
      devices.push(device);
    }
  }
  kindleboxDevices = devices;
  return devices;
}

function whitelistEmailer(emailer, successCallback) {
  // If we've already succesfully whitelisted the emailer in this load of the
  // bookmarklet, go straight to the callback.
  if (whitelistedEmailer) {
    successCallback();
    return;
  }

  $.post('https://www.amazon.com/mn/dcw/myx/ajax-activity', {
    "data": '{"param":{"WhitelistEmail":{"newEmail":"' + emailer + '"}}}',
    "csrfToken": csrfToken,
  }, function(res) {
    try {
      if (res.WhitelistEmail.success || res.WhitelistEmail.error == 'DUPLICATE_ITEM') {
          whitelistedEmailer = true;
          successCallback();
      } else {
        throw res.WhitelistEmail.error;
      }
    } catch (err) {
      console.log(err);
    }
  }, "json");
}

function addModal(kindleboxCsrfToken, appUrl, emailer) {
  // If the modal has already been added and it has the right number of
  // devices, don't do anything.
  if ($("#" + KINDLEBOX_MODAL_ID).length > 0) {
    return;
  }

  var $modalHtml = $('<div class="modal fade" id="' + KINDLEBOX_MODAL_ID + '" tabindex="-1" role="dialog" aria-labelledby="' + KINDLEBOX_MODAL_ID + '" aria-hidden="true">' +
      '  <div class="modal-dialog">' +
      '    <div class="modal-content">' +
      '      <div class="modal-header">' +
      '      <button type="button" class="close" data-dismiss="modal" aria-hidden="true">&times;</button>' +
      '      <h2>Kindlebox</h2>' +
      '      </div>' +
      '      <div class="modal-body">' +
      '        <b id="kindlebox-devices-label">Select your Kindle device(s)!</b>' +
      '        <form id="' + KINDLEBOX_FORM_ID + '" action="' + appUrl + '/activate" method="POST">' +
      '          <input type="hidden" name="csrf_token" value="' + kindleboxCsrfToken + '">' +
      '          <input type="hidden" name="kindle_names" value="">' +
      '          <div id="' + KINDLEBOX_DEVICES_ID + '">' +
      '          </div>' +
      '        </form>' +
      '      </div>' +
      '      <div class="modal-footer">' +
      '        <div id="kindlebox-error" class="pull-left">' +
      '          <b>Oops, no devices were selected! Try again :)</b>' +
      '        </div>' +
      '        <button id="activate-kindlebox-btn" type="button" class="btn btn-primary">Activate Kindlebox</button>' +
      '    </div>' +
      '  </div>' +
      '  </div>' +
      '</div>');

  $modalHtml.find('#kindlebox-error').hide();

  // Handler for submitting the picker form.
  function activateKindlebox() {
    var devices = $.makeArray($("#" + KINDLEBOX_FORM_ID).find(".kindlebox-device-checkbox:checked"));
    if (devices.length == 0) {
      $('#kindlebox-error').clearQueue().fadeIn().delay(3000).fadeOut();
      return;
    }
    var kindleNames = devices.map(function(device) {
      return device.name;
    });
    $("[name='kindle_names']").val(JSON.stringify(kindleNames));
    $("#" + KINDLEBOX_FORM_ID).submit();
  }
  $modalHtml.find("#activate-kindlebox-btn").click(function() {
    whitelistEmailer(emailer, activateKindlebox);
  });

  // Add a checkbox for each device eligible for Kindlebox.
  var devices = getDevices();
  if (devices.length == 0) {
    $modalHtml.find('.modal-body').text('Oops, it seems you don\'t have any \
        devices eligible for Kindlebox! Make sure to register a \
        Kindle with this Amazon account before trying again :)')
    $modalHtml.find('#activate-kindlebox-btn').attr('disabled', 'disabled');
  } else {
    for (var i = 0; i < devices.length; i++) {
      var label = devices[i].tag;
      if (devices[i].type) {
        label += ' (' + devices[i].type + ')';
      }
      $modalHtml.find("#" + KINDLEBOX_DEVICES_ID).append('<div class="checkbox">' +
        '  <input type="checkbox" id="kindlebox-device-' + i + '" class="kindlebox-device-checkbox" name="' + devices[i].email + '">' +
        '  <label for="kindlebox-device-' + i + '" class="kindlebox-device-label" style="">' +
           label +
         '</label>' +
        '</div>');
    }
  }

  $('body').append($modalHtml);
}

function showModal() {
  $('#' + KINDLEBOX_MODAL_ID).modal();
}

function submitKindleName(kindleName) {
  $.post('/set-user-info', {
    'kindle_name': kindleName
  }, function(data) {
    if (data.success) {
      this.props.kindleNameHandler(kindleName, data.emailer);
      $(':focus').blur();
      this.handleBlur();
    }
  }.bind(this));
}
