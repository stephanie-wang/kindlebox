/** @jsx React.DOM */
var DEFAULT_KINDLENAME = 'kindle_username';
var InstructionTable = React.createClass({
  getInitialState: function() {
    return {
      'kindleboxCsrfToken': this.props.kindleboxCsrfToken,
      'appUrl': this.props.appUrl,
      'active': this.props.active,
      'kindleName': this.props.kindleName,
      'emailer': this.props.emailer,
    }
  },
  render: function() {
    if (this.state.active) {
      return <ActiveMessage deactivateHandler={this.deactivateHandler} />;
    }

    var instructionClasses = React.addons.classSet({
      'instruction-row': true,
      'instruction-completed': this.props.loggedIn,
    });
    var loginBtnClasses = React.addons.classSet({
      'instruction': true,
      'dropbox-action': true,
      'instruction-action': true,
      'instruction-action-inactive': this.props.loggedIn,
    });
    var loginInstruction = (
      <div className={instructionClasses}>
        <div className="instruction-num">
          1.
        </div>
        <a className="instruction-btn"
              href={ this.props.loginUrl }>
          <div className={ loginBtnClasses }>
            <div className="instruction-action-content">
              <img className="dropbox-logo" src="static/img/dropbox.png"/>
                Login with Dropbox
            </div>
          </div>
        </a>
      </div>
      );

    var kindleNameInstruction;
    if (this.props.loggedIn) {
      kindleNameInstruction = <KindleNameInstruction
          kindleName={this.state.kindleName}
          kindleNameHandler={this.kindleNameHandler} />;
    }

    var emailerInstructions;
    if (this.props.loggedIn && this.state.kindleName) {
      emailerInstructions = <EmailerInstructions
          kindleboxCsrfToken={this.state.kindleboxCsrfToken}
          appUrl={this.state.appUrl}
          emailer={this.state.emailer}
          deactivateHandler={this.deactivateHandler} />;
    }

    return (
      <div>
        {loginInstruction}
        {kindleNameInstruction}
        {emailerInstructions}
      </div>
      );
  },
  kindleNameHandler: function(kindleName, emailer) {
    this.setState({
      'kindleName': kindleName,
      'emailer': emailer,
    });
  },
  deactivateHandler: function() {
    $.post('/deactivate', function(res) {
      if (res.success) {
        this.setState({
          'active': false,
        });
      }
    }.bind(this));
  }
});

var KindleNameInstruction = React.createClass({
  // State:
  //  - saved is whether the current form value is saved.
  //  - focused is whether the form element is focused.
  getInitialState: function() {
    var first_login = this.props.kindleName ? false : true;
    return {
      'focused': first_login,
    }
  },
  render: function() {
    var kindleNameClasses = React.addons.classSet({
      'instruction-row': true,
      'instruction-completed': !this.state.focused,
    });
    var defaultValue = this.props.kindleName ? this.props.kindleName : DEFAULT_KINDLENAME;
    return (
      <div id="kindle-name-instruction" className={kindleNameClasses}>
        <div className="instruction-num">
          2.
        </div>
        <div className="instruction">
          <form id="user-info-form" onSubmit={this.handleSubmit}>
              <input type="text" id="kindle-name" name="kindle_name"
                  className="form-control form-input instruction-action"
                  defaultValue={defaultValue} ref="kindleName"
                  onBlur={this.handleSubmit}
                  onFocus={this.handleFocus} />
            <div id="kindle-com" className="pull-right">
              @kindle.com
            </div>
            <div id="kindle-com-help">
            Don't know your Kindle username? Navigate to <a href="https://www.amazon.com/manageyourkindle" target="_blank">Manage Your Content and Devices</a> and go to the <b>Your Devices</b> tab. There, find your device and copy the <b>Email</b> listed.
            </div>
          </form>
        </div>
      </div>
    );
  },
  componentDidMount: function() {
    // Set kindle form widths.
    var $container = $(this.getDOMNode())
    var kindleComWidth = $container.find('#kindle-com').outerWidth();
    var formWidth = $container.find('#user-info-form').innerWidth();
    $container.find('#kindle-name').width(formWidth - kindleComWidth - 45);
    if (this.state.focused) {
      $container.find('#kindle-com-help').hide();
      setTimeout(function() {
        $container.find('#kindle-com-help').fadeIn();
      }, 1000);
    }
  },
  getValue: function() {
    var inputNode = this.refs.kindleName.getDOMNode();
    return inputNode.value;
  },
  handleSubmit: function() {
    var kindleName = this.getValue();
    if (kindleName.length == 0 || kindleName.trim() == DEFAULT_KINDLENAME) {
      return false;
    }
    $.post('/set-user-info', {
      'kindle_name': kindleName
    }, function(data) {
      if (data.success) {
        this.props.kindleNameHandler(kindleName, data.emailer);
        $(':focus').blur();
        this.handleBlur();
      }
    }.bind(this));
    return false;
  },
  handleFocus: function(evt) {
    this.setState({
      'focused': true,
    });
    var target = evt.target;
    setTimeout(function() {
      target.select();
    }, 0);
  },
  handleBlur: function() {
    this.setState({
      'focused': false,
    });
  },
});

var EmailerInstructions = React.createClass({
  render: function() {

    var bookmarklet = "javascript: (function() {" +
        "var xhr = new XMLHttpRequest();" +
        "xhr.open('POST', 'https://www.amazon.com/mn/dcw/myx/ajax-activity', true);" +
        "xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');" +
        "xhr.onload = function () {" +
          "var res = JSON.parse(this.responseText);" +
          "try {" +
            "if (res.WhitelistEmail.success || res.WhitelistEmail.error == 'DUPLICATE_ITEM') {" +
              "var form = document.createElement('form');" +
              "form.setAttribute('method', 'post');" +
              "form.setAttribute('action', '<appUrl>/activate');" +
              "var csrfInput = document.createElement('input');" +
              "csrfInput.setAttribute('type', 'hidden');" +
              "csrfInput.setAttribute('name', 'csrf_token');" +
              "csrfInput.setAttribute('value', '<kindleboxCsrfToken>');" +
              "form.appendChild(csrfInput);" +
              "form.submit()" +
            "} else {" +
              "throw res.WhitelistEmail.error;" +
            "}" +
          "} catch (err) {" +
            "console.log(err);" +
          "}" +
        "};" +
        "var data = '{\"param\":{\"WhitelistEmail\":{\"newEmail\":\"<emailer>\"}}}';" +
        "var dataString = 'data=' + encodeURIComponent(data) + '&csrfToken=' + encodeURIComponent(csrfToken);" +
        "xhr.send(dataString);" +
      "}());";
    var start = bookmarklet.search('<.*>');
    var stop;
    var key;
    while (start > -1) {
      stop = bookmarklet.substring(start).search('>');
      key = bookmarklet.substring(start + 1, start + stop);
      bookmarklet = bookmarklet.replace('<' + key + '>', this.props[key]);
      start = bookmarklet.search('<.*>');
    }

    var lastInstructionDisplay = {
      'display': 'none',
    };

    return (
      <div>
        <div className="instruction-row">
          <div className="instruction-num">
            3.
          </div>
          <div className="instruction instruction-text">

            Drag this bookmarklet to your bookmarks bar:
            <div id="bookmarklet-wrapper" onDragEnd={this.showInstruction}>
              <a id="bookmarklet" className="instruction-action" href={bookmarklet}>Allow Kindlebox</a>
            </div>

          </div>
        </div>
        <div className="instruction-row" style={lastInstructionDisplay} ref="lastInstruction">
          <div className="instruction-num">
            4.
          </div>
          <div className="instruction instruction-text">

            Next, visit <a href="https://www.amazon.com/manageyourkindle"
            target="_blank">Manage Your Content and Devices</a>. Click the
            bookmarklet on your bookmarks bar from step 3, and you're good to
            go!

          </div>
        </div>
      </div>
    );
  },
  showInstruction: function() {
    var lastInstruction = this.refs.lastInstruction.getDOMNode();
    setTimeout(function() {
      $(lastInstruction).fadeIn();
    }, 500);
  },
});

var ActiveMessage = React.createClass({
  render: function() {
    return (
        <div>
          <h1>
            Success! Your Kindlebox is active.
          </h1>
          <div>
            Any books you add to <code>Dropbox/Apps/kindle-box</code> will be sent to your Kindle.
          </div>
          <a onClick={this.deactivateHandler} className="instruction-btn">
            <div className="instruction instruction-action start-stop">
              <div className="instruction-action-content">
                Stop Kindlebox
              </div>
            </div>
          </a>
        </div>
      );
  },
  deactivateHandler: function() {
    this.props.deactivateHandler();
  },
});
