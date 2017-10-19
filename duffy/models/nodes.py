# -*- coding: utf-8 -*-
import datetime
import uuid

from duffy.database import db, Duffyv1Model
from duffy.extensions import marshmallow
from marshmallow import post_dump
import marshmallow as ma

class Project(Duffyv1Model):
    """"""
    __tablename__ = 'users'
    apikey = db.Column(db.String, primary_key=True)
    projectname = db.Column(db.String)
    jobname = db.Column(db.String)
    createdat = db.Column(db.DateTime)
    limitnodes = db.Column(db.Integer)

class Session(Duffyv1Model):
    __tablename__ = 'sessions'
    id = db.Column(db.String, default=lambda: str(uuid.uuid4())[:8], primary_key=True)
    delivered_at = db.Column(db.DateTime, default=datetime.datetime.now())
    dropped_at = db.Column(db.DateTime)
    apikey = db.Column(db.String)
    state = db.Column(db.String, default='Deployed')
    jobid = db.Column(db.String)
    hosts = db.relationship('Host', lazy='joined')

class Host(Duffyv1Model):
    __tablename__ = 'stock'
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String)
    ip = db.Column(db.String)
    chassis = db.Column(db.String)
    used_count = db.Column(db.Integer)
    state = db.Column(db.String)
    comment = db.Column(db.String)
    distro = db.Column(db.String)
    rel = db.Column(db.String)
    ver = db.Column(db.String)
    arch = db.Column(db.String)
    pool = db.Column(db.Integer)
    console_port = db.Column(db.Integer)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'))
    session = db.relationship('Session', lazy='joined')

class SessionSchema(marshmallow.Schema):
    id = ma.fields.String(dump_to='ssid')
    hosts = ma.fields.Nested("HostSchema", only='hostname', many=True)

class HostSchema(marshmallow.ModelSchema):
    session_id = ma.fields.String(dump_to='comment')
    class Meta:
        model = Host
