#!/usr/bin/env python
import pickle

from app import app

import redis


redis = redis.from_url(app.config['REDIS_URI'])


def queue_daemon(app, rv_ttl=500):
    while 1:
        msg = redis.blpop(app.config['REDIS_QUEUE_KEY'])
        func, key, args, kwargs = pickle.loads(msg[1])
        try:
            rv = func(*args, **kwargs)
        except Exception, e:
            rv = e
        if rv is not None:
            redis.set(key, pickle.dumps(rv))
            redis.expire(key, rv_ttl)


if __name__ == '__main__':
    queue_daemon(app)
