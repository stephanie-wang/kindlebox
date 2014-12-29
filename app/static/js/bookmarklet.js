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

function addModal() {
  var $modalHtml = $('<div class="modal fade" id="' + MODAL_ID + '" tabindex="-1" role="dialog" aria-labelledby="' + MODAL_ID + '" aria-hidden="true">' +
      '  <div class="modal-dialog">' +
      '    <div class="modal-content">' +
      '      <div class="modal-header">' +
      '      <button type="button" class="close" data-dismiss="modal" aria-hidden="true">&times;</button>' +
      '      <h3 class="modal-title">Kindlebox</h3>' +
      '      </div>' +
      '      <div class="modal-body">' +
      '        Pick your Kindle(s)!' +
      '        <form id="' + MODAL_FORM_ID + '">' +
      '        </form>' +
      '      </div>' +
      '      <div class="modal-footer">' +
      '        <button type="button" class="btn btn-primary">Activate Kindlebox</button>' +
      '    </div>' +
      '  </div>' +
      '  </div>' +
      '</div>');

  var devices = getDevices();
  for (var i = 0; i < devices.length; i++) {
    var label = devices[i].tag;
    if (devices[i].type) {
      label += ' (' + devices[i].type + ')';
    }
    $modalHtml.find('#' + MODAL_FORM_ID).append('<div class="checkbox">' +
      '  <label><input type="checkbox" value="">' +
        label +
      '</label>' +
      '</div>');
  }
  $('body').append($modalHtml);
}

function showModal() {
  if ($('#' + MODAL_ID).length == 0) {
    addModal();
  }
  $('#' + MODAL_ID).modal();
}

function whitelistEmailer() {
  var xhr = new XMLHttpRequest();
  xhr.open('POST', 'https://www.amazon.com/mn/dcw/myx/ajax-activity', true);
  xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  xhr.onload = function () {
    var res = JSON.parse(this.responseText);
    try {
      if (res.WhitelistEmail.success) {
        var activate_xhr = new XMLHttpRequest();
        activate_xhr.open('POST', "{{ url_for('activate_user') }}", true);
        activate_xhr.onload = function() {
          var res = JSON.parse(this.responseText);
          console.log(res);
        };
        var data = JSON.stringify({'active': true});
        activate_xhr.send(data);
      } else {
        throw res.WhitelistEmail.error;
      }
    } catch (err) {
      console.log(err);
    }
  };
  var data = '{"param":{"WhitelistEmail":{"newEmail":"{{ emailer }}"}}}';
  var dataString = 'data=' + encodeURIComponent(data) + '&csrfToken=' + encodeURIComponent(csrfToken);
  xhr.send(dataString);
}
