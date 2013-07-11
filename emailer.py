# -*- coding: utf-8 -*-
import smtplib
import constants
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email import Encoders

EMAILER_ADDRESS = constants.EMAILER_ADDRESS
EMAILER_PASSWORD = constants.EMAILER_PASSWORD
KINDLE_USER = [constants.KINDLE_USER]

def send_mail(send_from, send_to, subject, text, files=[], server='localhost'):
	assert type(send_to)==list
	assert type(files)==list

	msg = MIMEMultipart()
	msg['From'] = send_from
	msg['To'] = COMMASPACE.join(send_to)
	msg['Date'] = formatdate(localtime=True)
	msg['Subject'] = subject

	msg.attach( MIMEText(text) )

	for f in files:
		part = MIMEBase('application', "octet-stream")
		part.set_payload( open(f,"rb").read() )
		Encoders.encode_base64(part)
		part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(f))
		msg.attach(part)

	if server == 'smtp.gmail.com':
		smtpserver = smtplib.SMTP(server,587)
		smtpserver.ehlo()
		smtpserver.starttls()
		smtpserver.ehlo
		smtpserver.login(EMAILER_ADDRESS, EMAILER_PASSWORD)
	else:
		smtpserver = smtplib.SMTP(server)
	smtpserver.sendmail(send_from, send_to, msg.as_string())
	smtpserver.close()

if __name__ == '__main__':
	send_mail(EMAILER_ADDRESS, KINDLE_USER, 'Hello world', 'hello world', [], 'smtp.gmail.com')