$('#show-donations').click(function() {
  $('#donations-modal').modal();
});
$(".btn-group > .btn").click(function(){
    $(this).addClass("active").siblings().removeClass("active");
});

window.setTimeout(function() {
  $('#donations-button').animate({'margin-left': '-25px'});
}, 1000);

// This identifies your website in the createToken call below
Stripe.setPublishableKey(STRIPE_PUBLIC_KEY);

jQuery(function($) {
  $('#donations-form').submit(function(event) {
    var $form = $(this);

    // Disable the submit button to prevent repeated clicks
    $form.find('button').prop('disabled', true);

    Stripe.card.createToken($form, stripeResponseHandler);

    // Prevent the form from submitting with the default action
    return false;
  });
});

function stripeResponseHandler(status, response) {
  var $form = $('#donations-form');

  if (response.error) {
    // Show the errors on the form
    $form.find('.payment-errors').text(response.error.message);
    $form.find('button').prop('disabled', false);
  } else {
    // response contains id and card, which contains additional card details
    var token = response.id;
    // Insert the token into the form so it gets submitted to the server
    $form.append($('<input type="hidden" name="stripeToken" />').val(token));

    var $email = $form.find('[name="emailAddress"]');
    if (!$email.val()) {
      $form.find('.payment-errors').text('Enter an email for a receipt.');
      $form.find('button').prop('disabled', false);
      return;
    }

    var $amount = $form.find('.amount-btn.active');
    var amount_string = $amount.attr('amount');
    if (!amount_string) {
      amount_string = $amount.find('#other-amount').val();
    }
    var amount = parseFloat(amount_string);
    if (!(amount > 0)) {
      $form.find('.payment-errors').text('Oops, you must donate a positive amount!');
      $form.find('button').prop('disabled', false);
      return;
    }

    $form.find('[name="amount"]').val(amount);
    $.post('/donate', $form.serialize(), function(data) {
      if (data.success) {
        $('#donations-modal').find('.modal-body').text(
          "You're awesome :) " +
          "You should receive an email shortly with a receipt.");
      } else {
        $form.find('.payment-errors').text(data.message);
        $form.find('button').prop('disabled', false);
      }
    });
  }
};
