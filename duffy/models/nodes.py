# -*- coding: utf-8 -*-
import datetime
import uuid

from duffy.database import db, Duffyv1Model
from duffy.extensions import marshmallow
from duffy.models.baremetal_nodes import Host
from duffy.models.opennebula_nodes import OpennebulaHost
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
    """
    Class representing the session model.

    Attributes:
      id (str): Unique identifier of the session
      delivered_at (db.DateTime): Time of the session creation
      dropped_at (db.DateTime): Time when the session was dropped
      apikey (str): API key used with the request that created the session
      state (str): State of the session
      jobid (str): Identifier of the worker job
      type (str): Type of the machines linked to this session.
      hosts (db.relationship): Relationship to Host table
    """
    __tablename__ = 'sessions'
    id = db.Column(db.String(37), default=lambda: str(uuid.uuid4())[:8], primary_key=True)
    delivered_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    dropped_at = db.Column(db.DateTime)
    apikey = db.Column(db.String(37))
    state = db.Column(db.String(15), default='Prod')
    jobid = db.Column(db.String(200))
    type = db.Column(db.String(15))
    hosts = db.relationship('Host', lazy='joined')

    # Let's define some constants for the type values
    TYPE_BARE_METAL = "bare_metal"
    TYPE_OPEN_NEBULA = "open_nebula"


class SessionSchema(marshmallow.Schema):
    id = ma.fields.String(dump_to='ssid')
    hosts = ma.fields.Nested("HostSchema", only='hostname', many=True)

class HostSchema(marshmallow.Schema):
    session_id = ma.fields.String(dump_to='comment')

    class Meta:
        model = Host

class OpenNebulaHostSchema(marshmallow.Schema):
    session_id = ma.fields.String(dump_to='comment')

    class Meta:
        model = OpennebulaHost
