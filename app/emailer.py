# -*- coding: utf-8 -*-
import os.path
import codecs

import requests

from app import app


SENDGRID_API_URL = 'https://api.sendgrid.com/api/mail.send.json'

def send_mail(send_from, send_to, files=None):
    if files is None:
        files = []
    assert type(files)==list

    data = {
             'api_user': app.config['SENDGRID_USERNAME'],
             'api_key': app.config['SENDGRID_PASSWORD'],
             'from': send_from,
             'to[]': send_to,
             'subject': 'convert',
             'text': 'convert',
             }

    post_files = {}

    for _file in files:
        filename = os.path.basename(_file)#.decode('utf-8', 'ignore').encode('ascii', 'ignore'))
        _file_key = 'files[{filename}]'.format(filename=filename).decode('utf-8').encode('ascii', 'ignore')
        post_files[_file_key] = open(_file.decode('utf-8'), 'rb')

    response = requests.post(SENDGRID_API_URL, data=data, files=post_files)

    return response.status_code, response.text
