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

            Drag this bookmarklet to your bookmarks bar:
            <div id="bookmarklet-wrapper" onDragEnd={this.showInstruction}>
              <a id="bookmarklet" className="instruction-action" href={bookmarklet}>Activate Kindlebox</a>
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
});

var ActiveMessage = React.createClass({
  render: function() {
    return (
        <div>
          <div>
            <h2>
              Success! Any books you add to <code>Dropbox/Apps/kindle-box</code> will now be
              sent to your Kindle.
            </h2>
          </div>
          <div className="tip">
            Tip: It may take a few minutes for your Kindle to download a book
            after adding it to your Dropbox. Sit tight :)
          </div>
          <div className="tip">
            If you'd like to update your Kindle devices, or stop using
            Kindlebox completely, click <a onClick={this.deactivateHandler}
            className="instruction-btn">here</a>.
          </div>
        </div>
      );
  },
  deactivateHandler: function() {
    this.props.deactivateHandler();
  },
});
