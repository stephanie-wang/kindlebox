#!/usr/bin/env python
from pickle import loads, dumps
from redis import Redis

from app import app
from kindlebox.kindleboxer import process_user

redis = Redis()

def queue_daemon(app, rv_ttl=500):
    while 1:
        msg = redis.blpop(app.config['REDIS_QUEUE_KEY'])
        func, key, args, kwargs = loads(msg[1])
        print func
        try:
            rv = func(*args, **kwargs)
        except Exception, e:
            rv = e
        if rv is not None:
            redis.set(key, dumps(rv))
            redis.expire(key, rv_ttl)


queue_daemon(app)
