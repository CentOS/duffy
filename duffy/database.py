from .extensions import db


class Duffyv1Model(db.Model):
    __abstract__ = 'True'

    def save(self):
        db.session.add(self)
