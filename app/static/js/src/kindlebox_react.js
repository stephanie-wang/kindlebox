/** @jsx React.DOM */
var InstructionTable = React.createClass({
  getInitialState: function() {
    return {
      "kindleboxCsrfToken": this.props.kindleboxCsrfToken,
      "appUrl": this.props.appUrl,
      "addedBookmarklet": this.props.addedBookmarklet,
      "active": this.props.active,
      "emailer": this.props.emailer,
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
      'action': true,
      'action-inactive': this.props.loggedIn,
    });
    var loginInstruction = (
      <div className={instructionClasses}>
        <div className="instruction-num">
          1.
        </div>
        <a className="instruction button"
              href={ this.props.loginUrl }>
          <div className={ loginBtnClasses }>
            <div className="action-content">
              <div className="action-content-inner">
                <img className="dropbox-logo" src="static/img/dropbox.png"/>
                <div id="dropbox-caption">
                  Login with Dropbox
                </div>
              </div>
            </div>
          </div>
        </a>
      </div>
      );

    var emailerInstructions;
    if (this.props.loggedIn) {
      emailerInstructions = <EmailerInstructions
          kindleboxCsrfToken={this.state.kindleboxCsrfToken}
          appUrl={this.state.appUrl}
          addedBookmarklet={this.state.addedBookmarklet}
          addedBookmarkletHandler={this.addedBookmarkletHandler}
          emailer={this.state.emailer}
          deactivateHandler={this.deactivateHandler} />;
    }

    return (
      <div>
        {loginInstruction}
        {emailerInstructions}
      </div>
      );
  },
  addedBookmarkletHandler: function() {
    this.setState({
      "addedBookmarklet": true,
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
  },
});

var EmailerInstructions = React.createClass({
  render: function() {
    // TODO: Also wait for all the devices on site to load before adding modal.
    var bookmarklet = "javascript: (function() {" +
        "function addScript(source, callback) {" +
          "var script = document.createElement(\"script\");" +
          "script.className = \"kindlebox-source\";" +
          "script.type = \"text/javascript\";" +
          "script.src = source;" +
          "script.onload = callback;" +
          "document.getElementsByTagName(\"head\")[0].appendChild(script);" +
        "}" +
        "function addCSS(source, callback) {" +
          "var style = document.createElement('style');" +
          "style.className = \"kindlebox-source\";" +
          "style.textContent = '@import url(\"' + source + '\")';" +
          "var waitLoad = setInterval(function() {" +
            "try {" +
              "style.sheet.cssRules;" +
              "callback();" +
              "clearInterval(waitLoad);" +
            "} catch (e){}" +
          "}, 10);" +
          "document.getElementsByTagName(\"head\")[0].appendChild(style);" +
        "}" +
        "function addExternalSources(sources, callback) {" +
          "if (sources.length == 0) {" +
            "callback();" +
            "return;" +
          "}" +
          "var source = sources.shift();" +
          "var loadSource;" +
          "var suffix = \".js\";" +
          "if (source.indexOf(suffix, source.length - suffix.length) !== -1) {" +
            "loadSource = addScript;" +
          "} else {" +
            "loadSource = addCSS;" +
          "}" +
          "loadSource(source, function() {" +
            "addExternalSources(sources, callback);" +
          "});" +
        "}" +
        "var sources = [" +
          "\"https://fonts.googleapis.com/css?family=Arvo\"," +
          "\"https://kindlebox.me/static/css/lib/bootstrap.min.css\"," +
          "\"https://kindlebox.me/static/css/lib/font-awesome.min.css\"," +
          "\"https://kindlebox.me/static/css/bookmarklet.css\"," +
          "\"https://kindlebox.me/static/js/lib/jquery-1.11.1.min.js\"," +
          "\"https://kindlebox.me/static/js/lib/bootstrap.min.js\"," +
          "\"https://kindlebox.me/static/js/bookmarklet.js\"" +
        "];" +
        "if (document.getElementsByClassName(\"kindlebox-source\").length == sources.length) {" +
          "sources = [];" +
        "}" +
        "if (location.origin != 'https://www.amazon.com') {" +
          "return;" +
        "}" +
        "addExternalSources(sources, function() {" +
          "setDevice(1);" +
          "var waitDevices = setInterval(function() {" +
            "try {" +
              "document.getElementsByClassName('noDevicesFound_myx')[0].style.display;" +
              "addModal(\"<kindleboxCsrfToken>\", \"<appUrl>\", \"<emailer>\");" +
              "showModal();" +
              "clearInterval(waitDevices);" +
            "} catch(e) { " +
            "} " +
          "}, 10);" +
        "});" +
      "}())";


    var start = bookmarklet.search('<.*>');
    var stop;
    var key;
    while (start > -1) {
      stop = bookmarklet.substring(start).search('>');
      key = bookmarklet.substring(start + 1, start + stop);
      bookmarklet = bookmarklet.replace('<' + key + '>', this.props[key]);
      start = bookmarklet.search('<.*>');
    }

    var lastInstructionDisplay = {};
    if (!this.props.addedBookmarklet) {
      lastInstructionDisplay["display"] = "none";
    }

    return (
      <div>
        <div className="instruction-row">
          <div className="instruction-num">
            2.
          </div>
          <div className="instruction instruction-text">

            Drag this bookmarklet to your bookmarks bar (if you've added the
                bookmarklet previously, delete the old one and add again):

            <div id="bookmarklet-wrapper" onDragEnd={this.showInstruction}>
              <a id="bookmarklet" className="action" href={bookmarklet}
                  onMouseOver={this.showBookmarkletArrow}
                  onMouseLeave={this.hideBookmarkletArrow}>
                Activate Kindlebox
              </a>
              <img id="bookmarklet-arrow" ref="bookmarkletArrow" src="static/img/arrow.png" />
            </div>

          </div>
        </div>
        <div className="instruction-row" style={lastInstructionDisplay} ref="lastInstruction">
          <div className="instruction-num">
            3.
          </div>
          <div className="instruction instruction-text">

            Next, visit <a href="https://www.amazon.com/manageyourkindle"
            target="_blank">Manage Your Content and Devices</a> on Amazon.
            Click the bookmarklet on your bookmarks bar from step 2, pick your
            Kindle devices, and you're good to go!

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

    $.post("/added-bookmarklet", function(res) {
      if (res.success) {
        this.props.addedBookmarkletHandler();
      }
    }.bind(this));
  },
  showBookmarkletArrow: function() {
    var bookmarkletArrow = this.refs.bookmarkletArrow.getDOMNode();
    $(bookmarkletArrow).fadeTo(400, 1);
  },
  hideBookmarkletArrow: function() {
    var bookmarkletArrow = this.refs.bookmarkletArrow.getDOMNode();
    $(bookmarkletArrow).fadeTo(400, 0);
  },
});

var ActiveMessage = React.createClass({
  render: function() {
    return (
        <div>
          <h2>Success! Read the PDF below for final instructions.</h2>
          <iframe id="pdf-reader" src="static/kindlebox_welcome.pdf#view=fit"></iframe>
          <div className="tip">
            If you'd like to update your Kindle devices, or stop using
            Kindlebox completely, <a onClick={this.deactivateHandler}
            className="button">click here</a>.
          </div>
        </div>
      );
  },
  deactivateHandler: function() {
    this.props.deactivateHandler();
  },
});
