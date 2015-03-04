from flask import Flask
from flask.ext.migrate import Migrate, MigrateCommand
from flask.ext.mobility import Mobility
from flask.ext.script import Manager
from flask.ext.sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CsrfProtect

import analytics
from celery import Celery
from redis import StrictRedis


def make_celery(app):
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    celery.conf.BROKER_POOL_LIMIT = 0
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery


app = Flask(__name__)
app.config.from_object('config')
csrf = CsrfProtect(app)
db = SQLAlchemy(app)
celery = make_celery(app)

migrate = Migrate(app, db)
manager = Manager(app)
manager.add_command('db', MigrateCommand)

Mobility(app)

redis = StrictRedis(host=app.config.get('REDIS_HOST'),
                    port=app.config.get('REDIS_PORT'),
                    password=app.config.get('REDIS_PASSWORD'))

analytics.write_key = '2afEcXvTS827n9aLqcisLOjJH1XF83uB'


from app import models
from app import views


from commands import CeleryTasksCommand
from commands import ResetUserCommand
from commands import StatsCommand
from commands import SeedEmailsCommand
manager.add_command('tasks', CeleryTasksCommand)
manager.add_command('reset-user', ResetUserCommand)
manager.add_command('stats', StatsCommand)
manager.add_command('seed-emails', SeedEmailsCommand)
