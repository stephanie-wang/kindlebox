/** @jsx React.DOM */
var InstructionTable = React.createClass({
  getInitialState: function() {
    return {
      'active': this.props.active,
      'kindleName': this.props.kindleName,
      'emailer': this.props.emailer,
    }
  },
  render: function() {
    if (this.state.active) {
      return <ActiveMessage activeHandler={this.activeHandler} />;
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
          emailer={this.state.emailer}
          activeHandler={this.activeHandler} />;
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
  activeHandler: function(active) {
    if (!(active === true || active == false)) {
      return;
    }
    $.post('/activate', {
      'data': JSON.stringify({
        'active': active,
        'dropbox_id': dropbox_id,
      })
    }, function(res) {
      if (res.success) {
        this.setState({
          'active': active,
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
    var saved = this.props.kindleName ? true : false;
    return {
      'saved': saved,
      'focused': !saved,
    }
  },
  render: function() {
    var kindleNameClasses = React.addons.classSet({
      'instruction-row': true,
      'instruction-completed': !this.state.focused && this.state.saved,
    });
    var defaultValue = this.props.kindleName ? this.props.kindleName : 'kindle username';
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
                  onBlur={this.handleBlur}
                  onFocus={this.handleFocus} />
            <div id="kindle-com" className="pull-right">
              @kindle.com
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
  },
  getValue: function() {
    var inputNode = this.refs.kindleName.getDOMNode();
    return inputNode.value;
  },
  handleSubmit: function() {
    var kindleName = this.getValue();
    if (kindleName.length == 0) {
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
  handleFocus: function() {
    this.setState({
      'focused': true,
    });
  },
  handleBlur: function() {
    var kindleName = this.getValue();
    this.setState({
      'saved': kindleName === this.props.kindleName,
      'focused': false,
    });
  },
});

var EmailerInstructions = React.createClass({
  render: function() {
    return (
      <div id="emailer-instructions">
        <div id="emailer-instruction" className="instruction-row">
          <div className="instruction-num">
            3.
          </div>
          <div id="emailer-text" className="instruction">
            Kindlebox works by emailing the books in your Dropbox folder to your Kindle. Here's your Kindlebox emailer:
            <div id="emailer-wrapper">
            <pre id="emailer">{this.props.emailer}</pre>
            <button id="copy-emailer" className="btn instruction-action" data-clipboard-target="emailer" data-toggle="tooltip" title="Copy" data-placement="right">
              <i className="fa fa-clipboard"></i>
            </button>
            </div>
            <p>To start receiving books through Kindlebox:</p>
            <ul>
              <li>Visit <a href="https://www.amazon.com/manageyourkindle" target="_blank">Manage Your Content and Devices</a> at amazon.com</li>
              <li>Go to the <b>Settings</b> tab</li>
              <li>Scroll down to <b>Personal Document Settings</b></li>
              <li>Add the above email address to your <b>Approved Personal Document E-mail List</b></li>
            </ul>
            <p>And finally...</p>
          </div>
        </div>
        <div className="instruction-row">
          <div className="instruction-num">
            4.
          </div>
          <a onClick={this.activeHandler} className="instruction-btn">
            <div className="instruction uncentered-action instruction-action">
              <div className="instruction-action-content">
                Activate Kindlebox!
              </div>
            </div>
          </a>
        </div>
      </div>
    );
  },
  activeHandler: function() {
    this.props.activeHandler(true);
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
            Any books you add to <code>Dropbox/kindlebox</code> will be sent to your Kindle.
          </div>
          <a onClick={this.activeHandler} className="instruction-btn">
            <div className="instruction instruction-action start-stop">
              <div className="instruction-action-content">
                Stop Kindlebox
              </div>
            </div>
          </a>
        </div>
      );
  },
  activeHandler: function() {
    this.props.activeHandler(false);
  },
});
