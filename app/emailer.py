# -*- coding: utf-8 -*-
import os.path
import codecs

import requests

from app import app


SENDGRID_API_URL = 'https://api.sendgrid.com/api/mail.send.json'
MAILGUN_API_URL = 'https://api.mailgun.net/v2/{0}/messages'.format(app.config.get('MAILGUN_DOMAIN'))


def send_mail(send_from, send_to, files=None, use_mailgun=False):
    if files is None:
        files = []
    assert type(files)==list

    data = {
             'from': send_from,
             'to[]': send_to,
             'subject': 'convert',
             'text': 'convert',
             }

    if not use_mailgun:
        data['api_user'] = app.config['SENDGRID_USERNAME']
        data['api_key'] = app.config['SENDGRID_PASSWORD']

    post_files = {}

    if use_mailgun:
        for i, _file in enumerate(files):
            # `_file` is unicode, so encode to ASCII.
            filename = os.path.basename(_file).encode('ascii', 'ignore')
            post_files['attachment[{0}]'.format(i)] = (filename, open(_file, 'rb'))

        response = requests.post(MAILGUN_API_URL,
                                 auth=('api', app.config.get('MAILGUN_API_KEY')),
                                 data=data,
                                 files=post_files)
    else:
        for _file in files:
            # `_file` is unicode, so encode to ASCII.
            filename = os.path.basename(_file).encode('ascii', 'ignore')
            _file_key = 'files[{filename}]'.format(filename=filename)
            post_files[_file_key] = open(_file, 'rb')

        # If SendGrid fails, try Mailgun.
        response = requests.post(SENDGRID_API_URL, data=data, files=post_files)
        if response.status_code != 200:
            return send_mail(send_from, send_to, files, use_mailgun=True)

    return response.status_code, response.text
