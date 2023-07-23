import urllib.parse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from . import model


def make_session(
    host: str, port: int, user: str, password: str, schema: str, echo: bool = False
) -> Session:
    encoded_password = urllib.parse.quote_plus(password)
    engine = create_engine(
        f"mysql+mysqldb://{user}:{encoded_password}@{host}:{port}/{schema}",
        echo=echo,
    )
    model.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()
