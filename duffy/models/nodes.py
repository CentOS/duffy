# -*- coding: utf-8 -*-
import datetime
import uuid

from duffy.database import db, Duffyv1Model
from duffy.extensions import marshmallow
import marshmallow as ma


class Project(Duffyv1Model):
    """"""
    __tablename__ = 'users'
    apikey = db.Column(db.String(37), primary_key=True)
    projectname = db.Column(db.String(50))
    jobname = db.Column(db.String(50))
    createdat = db.Column(db.DateTime)
    limitnodes = db.Column(db.Integer)
    sshkeys = db.relationship("SSHKey", backref="project")

class SSHKey(Duffyv1Model):
    __tablename__ = 'userkeys'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(37), db.ForeignKey('users.apikey'))
    key = db.Column(db.String(8192))


class Session(Duffyv1Model):
    __tablename__ = 'sessions'
    id = db.Column(db.String(37), default=lambda: str(uuid.uuid4())[:8], primary_key=True)
    delivered_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    dropped_at = db.Column(db.DateTime)
    apikey = db.Column(db.String(37))
    state = db.Column(db.String(15), default='Prod')
    jobid = db.Column(db.String(200))
    hosts = db.relationship('Host', lazy='joined')


class SessionSchema(marshmallow.Schema):
    id = ma.fields.String(dump_to='ssid')
    hosts = ma.fields.Nested("HostSchema", only='hostname', many=True)

class HostSchema(marshmallow.ModelSchema):
    session_id = ma.fields.String(dump_to='comment')

    class Meta:
        model = Host
