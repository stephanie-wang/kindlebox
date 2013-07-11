from dropbox import client, rest, session

APP_KEY = 'pbxn93iu6zgnjph'
APP_SECRET = 'n12nugx1no97a3f'

ACCESS_TYPE = 'dropbox'
sess = session.DropboxSession(APP_KEY, APP_SECRET, ACCESS_TYPE)

request_token = sess.obtain_request_token()

url = sess.build_authorize_url(request_token, oauth_callback="http://www.dropbox.com")
print "url:", url
print "Please visit this website and press the 'Allow' button, then hit 'Enter' here."
raw_input()

access_token = sess.obtain_access_token(request_token)

client = client.DropboxClient(sess)
print "linked account:", client.account_info()
