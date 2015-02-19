# -*- coding: utf-8 -*-
import os.path

import sendgrid

from app import app


sg = sendgrid.SendGridClient(app.config['SENDGRID_USERNAME'], app.config['SENDGRID_PASSWORD'])

def send_mail(send_from, send_to, files=[]):
    assert type(files)==list

    message = sendgrid.Mail()
    for to_email in send_to:
        message.add_to(to_email)
    message.set_subject('convert')
    message.set_text('convert')

    for f in files:
        message.add_attachment(os.path.basename(f), f)

    message.set_from(send_from)
    return sg.send(message)
