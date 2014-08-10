import pickle
from uuid import uuid4

from app import app

import redis


redis = redis.from_url(app.config['REDIS_URI'])


class DelayedResult(object):
    def __init__(self, key):
        self.key = key
        self._rv = None

    @property
    def return_value(self):
        if self._rv is None:
            rv = redis.get(self.key)
            if rv is not None:
                self._rv = pickle.loads(rv)
        return self._rv


def queuefunc(f):
    def delay(*args, **kwargs):
        qkey = app.config['REDIS_QUEUE_KEY']
        key = '%s:result:%s' % (qkey, str(uuid4()))
        s = pickle.dumps((f, key, args, kwargs))
        redis.rpush(app.config['REDIS_QUEUE_KEY'], s)
        return DelayedResult(key)
    f.delay = delay
    return f
