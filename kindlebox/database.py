from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

import constants

# TODO(sxwang): switch to postgres :(
engine = create_engine('postgresql://%s:%s@localhost/kindlebox' %
        (constants.POSTGRES_USER, constants.POSTGRES_PASSWORD),
        convert_unicode=True)
db = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db.query_property()

def init_db():
    import kindlebox.models
    Base.metadata.create_all(bind=engine)
