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
    var loginAnchorClasses = React.addons.classSet({
      'button-inactive': this.props.loggedIn,
      'instruction': true,
      'button': false,
    });
    var loginBtnClasses = React.addons.classSet({
      'instruction': true,
      'dropbox-action': true,
      'action': true,
    });

    var loginInstruction = (
      <div className={instructionClasses}>
        <div className="instruction-num">
          1.
        </div>
        <a id="login-button" className={loginAnchorClasses} href={ this.props.loginUrl }>
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
          userId={this.props.userId}
          username={this.props.username}
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
    //analytics.track('Added bookmarklet');
  },
  deactivateHandler: function() {
    $.post('/deactivate', function(res) {
      if (res.success) {
        this.setState({
          'active': false,
        });
      }
      analytics.track('Clicked deactivate button', {
        success: res.success,
      });
    }.bind(this))
      .fail(function() {
        analytics.track('Clicked deactivate button', {
          success: false
        });
      });
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
          "\"https://getbookdrop.com/static/css/lib/bootstrap.min.css\"," +
          "\"https://getbookdrop.com/static/css/lib/font-awesome.min.css\"," +
          "\"https://getbookdrop.com/static/css/bookmarklet.css\"," +
          "\"https://getbookdrop.com/static/js/lib/jquery-1.11.1.min.js\"," +
          "\"https://getbookdrop.com/static/js/lib/bootstrap.min.js\"," +
          "\"https://getbookdrop.com/static/js/bookmarklet.js\"" +
        "];" +
        "if (document.getElementsByClassName(\"kindlebox-source\").length == sources.length) {" +
          "sources = [];" +
        "}" +
        "addExternalSources(sources, function() {" +
          "setDevice(1);" +
          "var waitDevices = setInterval(function() {" +
            "try {" +
              "addModal(\"<kindleboxCsrfToken>\", \"<appUrl>\", \"<emailer>\");" +
              "showModal();" +
              "clearInterval(waitDevices);" +
            "} catch(e) { " +
            "} " +
          "}, 10);" +
        "});" +
        "!function(){var analytics=window.analytics=window.analytics||[];if(!analytics.initialize)if(analytics.invoked)window.console&&console.error&&console.error(\"Segment snippet included twice.\");else{analytics.invoked=!0;analytics.methods=[\"trackSubmit\",\"trackClick\",\"trackLink\",\"trackForm\",\"pageview\",\"identify\",\"group\",\"track\",\"ready\",\"alias\",\"page\",\"once\",\"off\",\"on\"];analytics.factory=function(t){return function(){var e=Array.prototype.slice.call(arguments);e.unshift(t);analytics.push(e);return analytics}};for(var t=0;t<analytics.methods.length;t++){var e=analytics.methods[t];analytics[e]=analytics.factory(e)}analytics.load=function(t){var e=document.createElement(\"script\");e.type=\"text/javascript\";e.async=!0;e.src=(\"https:\"===document.location.protocol?\"https://\":\"http://\")+\"cdn.segment.com/analytics.js/v1/\"+t+\"/analytics.min.js\";var n=document.getElementsByTagName(\"script\")[0];n.parentNode.insertBefore(e,n)};analytics.SNIPPET_VERSION=\"3.0.1\";" +
      "analytics.load(\"2afEcXvTS827n9aLqcisLOjJH1XF83uB\");" +
      "analytics.identify(\"" + this.props.userId + "\", {name: \"" + this.props.username + "\"});" +
      "}}();" +
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
            1a.
          </div>
          <div className="instruction instruction-text instruction-bold">
            If this is not your first time activating Bookdrop, make sure
            your books are in the right folder! Move your books to the
            folder <code>Dropbox/my-bookdrop</code>.

          </div>
        </div>
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
                Activate BookDrop
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

            Next, visit <a id="amazon-link" href="https://www.amazon.com/manageyourkindle"
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
          <p className="tip">
            BookDrop is free for everyone, but it costs us to keep it that
            way. <a ref="donateLink">Help us keep BookDrop
            going</a>!
          </p>
          <iframe id="pdf-reader" src="static/bookdrop_welcome.pdf#view=fit"></iframe>
          <p className="tip">
            If you'd like to update your Kindle devices, or stop using
            BookDrop completely, <a onClick={this.deactivateHandler}>click
            here</a>.
          </p>
        </div>
      );
  },
  deactivateHandler: function() {
    this.props.deactivateHandler();
  },
  componentDidMount: function() {
    $donateLink = $(this.refs.donateLink.getDOMNode());
    $donateLink.click(function() {
      $('#donations-modal').modal();
    });
  },
});
