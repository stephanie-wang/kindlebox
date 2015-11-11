var KINDLEBOX_MODAL_ID = 'kindlebox-device-picker';
var KINDLEBOX_FORM_ID = 'kindlebox-devices-form';
var KINDLEBOX_DEVICES_ID = 'kindlebox-devices-container';

var whitelistedEmailer = false;


function setDevice(deviceNum) {
  window.location.hash = '#/home/devices/' + deviceNum;
}

function gotoSettings() {
  window.location.hash = '#/home/settings/pdoc';
}

function htmlToString(html) {
  return html.textContent.trim();
}

function $getDevices() {
  gotoSettings();
  return $('[ng-repeat="item in devices"]');
}

function getNumDevices() {
  $devices = $getDevices();
  return $devices.length;
}

function getDevices() {
  var kindleboxDevices = [];
  var $devices = $getDevices();
  for (var i = 0; i < $devices.length; i++) {
    var deviceChildren = $($devices[i]).children();
    var device = {
      'tag': htmlToString(deviceChildren[0]),
      'email': htmlToString(deviceChildren[1]),
    }
    kindleboxDevices.push(device);
  }
  return kindleboxDevices;
}

function whitelistEmailer(emailer, successCallback) {
  // If we've already succesfully whitelisted the emailer in this load of the
  // bookmarklet, go straight to the callback.
  if (whitelistedEmailer) {
    successCallback();
    return;
  }

  $.post(document.location.origin + '/mn/dcw/myx/ajax-activity', {
    "data": '{"param":{"WhitelistEmail":{"newEmail":"' + emailer + '"}}}',
    "csrfToken": csrfToken,
  }, function(res) {
    try {
      if (res.WhitelistEmail.success || res.WhitelistEmail.error == 'DUPLICATE_ITEM') {
          //analytics.track('Whitelisted emailer');
          whitelistedEmailer = true;
          successCallback();
      } else {
        throw res.WhitelistEmail.error;
      }
    } catch (err) {
      analytics.track('Error whitelisting emailer');
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
      '      <h2>BookDrop</h2>' +
      '      </div>' +
      '      <div class="modal-body">' +
      '        <b id="kindlebox-devices-label">Select your Kindle device(s)!</b>' +
      '        <form id="' + KINDLEBOX_FORM_ID + '" action="' + appUrl + '/activate" method="POST">' +
      '          <input type="hidden" name="csrf_token" value="' + kindleboxCsrfToken + '">' +
      '          <input type="hidden" name="kindle_names" value="">' +
      '          <div id="' + KINDLEBOX_DEVICES_ID + '">' +
      '          <img id="kindlebox-devices-loading" src="https://getbookdrop.com/static/img/loader.gif" />' +
      '          </div>' +
      '        </form>' +
      '      </div>' +
      '      <div class="modal-footer">' +
      '        <div id="kindlebox-error" class="pull-left">' +
      '          <b>Oops, no devices were selected! Try again :)</b>' +
      '        </div>' +
      '        <button id="activate-kindlebox-btn" type="button" class="btn btn-primary">Activate BookDrop</button>' +
      '    </div>' +
      '  </div>' +
      '  </div>' +
      '</div>');

  $modalHtml.find('#kindlebox-error').hide();

  // Handler for submitting the picker form.
  function activateBookDrop() {
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
    //analytics.track('Clicked activate button');
    whitelistEmailer(emailer, activateBookDrop);
  });

  // Add a checkbox for each device eligible for BookDrop.
  gotoSettings();
  setTimeout(function() {
    $('#kindlebox-devices-loading').hide();
    var devices = getDevices();
    if (devices.length == 0) {
      $modalHtml.find('.modal-body').text('Oops, it seems you don\'t have any \
          devices eligible for BookDrop! Make sure to register a \
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
  }, 2000);

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

  !function(){var analytics=window.analytics=window.analytics||[];if(!analytics.initialize)if(analytics.invoked)window.console&&console.error&&console.error("Segment snippet included twice.");else{analytics.invoked=!0;analytics.methods=["trackSubmit","trackClick","trackLink","trackForm","pageview","identify","group","track","ready","alias","page","once","off","on"];analytics.factory=function(t){return function(){var e=Array.prototype.slice.call(arguments);e.unshift(t);analytics.push(e);return analytics}};for(var t=0;t<analytics.methods.length;t++){var e=analytics.methods[t];analytics[e]=analytics.factory(e)}analytics.load=function(t){var e=document.createElement("script");e.type="text/javascript";e.async=!0;e.src=("https:"===document.location.protocol?"https://":"http://")+"cdn.segment.com/analytics.js/v1/"+t+"/analytics.min.js";var n=document.getElementsByTagName("script")[0];n.parentNode.insertBefore(e,n)};analytics.SNIPPET_VERSION="3.0.1";
      analytics.load("lWJxozKgnYCAvQtWNks8rrWfoLjeNEJn");
            }}();
