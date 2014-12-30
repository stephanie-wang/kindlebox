var MODAL_ID = 'kindle-device-picker';
var MODAL_FORM_ID = 'kindle-devices';


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

function getDevices() {
  var numDevices = $('.deviceName_myx.a-size-base').length;
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
  return devices;
}

function whitelistEmailer(emailer, $activateForm) {
  $.post('https://www.amazon.com/mn/dcw/myx/ajax-activity', {
    "data": '{"param":{"WhitelistEmail":{"newEmail":"' + emailer + '"}}}',
    "csrfToken": csrfToken,
  }, function(res) {
    try {
      if (res.WhitelistEmail.success || res.WhitelistEmail.error == 'DUPLICATE_ITEM') {
        $activateForm.submit();
      } else {
        throw res.WhitelistEmail.error;
      }
    } catch (err) {
      console.log(err);
    }
  }, "json");
}

function addModal(kindleboxCsrfToken, appUrl, emailer) {
  if ($('#' + MODAL_ID).length > 0) {
    return;
  }
  var $modalHtml = $('<div class="modal fade" id="' + MODAL_ID + '" tabindex="-1" role="dialog" aria-labelledby="' + MODAL_ID + '" aria-hidden="true">' +
      '  <div class="modal-dialog">' +
      '    <div class="modal-content">' +
      '      <div class="modal-header">' +
      '      <button type="button" class="close" data-dismiss="modal" aria-hidden="true">&times;</button>' +
      '      <h3 class="modal-title">Kindlebox</h3>' +
      '      </div>' +
      '      <div class="modal-body">' +
      '        Pick your Kindle(s)!' +
      '        <form id="' + MODAL_FORM_ID + '" action="' + appUrl + '/activate" method="POST">' +
      '          <input type="hidden" name="csrf_token" value="' + kindleboxCsrfToken + '">' +
      '        </form>' +
      '      </div>' +
      '      <div class="modal-footer">' +
      '        <button id="activate-kindlebox-btn" type="button" class="btn btn-primary">Activate Kindlebox</button>' +
      '    </div>' +
      '  </div>' +
      '  </div>' +
      '</div>');

  var $modalForm = $modalHtml.find('#' + MODAL_FORM_ID);
  var devices = getDevices();
  for (var i = 0; i < devices.length; i++) {
    var label = devices[i].tag;
    if (devices[i].type) {
      label += ' (' + devices[i].type + ')';
    }
    $modalForm.append('<div class="checkbox">' +
      '  <label><input type="checkbox" value="">' +
        label +
      '</label>' +
      '</div>');
  }

  $modalHtml.find("#activate-kindlebox-btn").click(function() {
    whitelistEmailer(emailer, $modalForm);
  });

  $('body').append($modalHtml);
}

function showModal() {
  $('#' + MODAL_ID).modal();
}
