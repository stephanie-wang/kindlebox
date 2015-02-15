Kindlebox
=================================

Send books and personal documents to your Kindle device by adding them to your Dropbox folder. Check it out at [kindlebox.me](https://kindlebox.me).

If you'd like to run your own Kindlebox, here are the minimum system components that you'll need:
* Dropbox app
* Database supported by SQLAlchemy (e.g. PostgreSQL or SQLite)

Other components that might be helpful:
* At least one [celery worker]
* A message broker for [celery workers](http://www.celeryproject.org/) (e.g. RabbitMQ)
* A Redis instance

To get started...[TODO]
