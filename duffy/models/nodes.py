# -*- coding: utf-8 -*-
import datetime
import uuid

from duffy.database import db, Duffyv1Model
from duffy.extensions import marshmallow
import marshmallow as ma


class Project(Duffyv1Model):
    """"""
    __tablename__ = 'users'
    apikey = db.Column(db.String, primary_key=True)
    projectname = db.Column(db.String)
    jobname = db.Column(db.String)
    createdat = db.Column(db.DateTime)
    limitnodes = db.Column(db.Integer)
    sshkeys = db.relationship("SSHKey", backref="project")

class SSHKey(Duffyv1Model):
    __tablename__ = 'userkeys'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('users.apikey'))
    key = db.Column(db.String)

class Session(Duffyv1Model):
    __tablename__ = 'sessions'
    id = db.Column(db.String, default=lambda: str(uuid.uuid4())[:8], primary_key=True)
    delivered_at = db.Column(db.DateTime, default=datetime.datetime.now())
    dropped_at = db.Column(db.DateTime)
    apikey = db.Column(db.String)
    state = db.Column(db.String, default='Prod')
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

    def contextualize(self, project):
        self.state = 'Contextualizing'
        self.save()
        # Sync all of the keys to the root user on the remote host
        import paramiko
        import os
        ssh = paramiko.SSHClient()
        # TODO: Make this configurable
        key = paramiko.DSSKey.from_private_key_file(os.path.expanduser('~/.ssh/id_dsa'))
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ssh.connect(self.hostname, username='root', pkey=key)
        sftp = ssh.open_sftp()
        file_handle = sftp.file('/root/.ssh/id_rsa.pub', mode='a', bufsize=-1)
        for sshkey in project.sshkeys:
            file_handle.write(sshkey + '\n')
        file_handle.flush()
        file_handle.close()
        ssh.close()

class SessionSchema(marshmallow.Schema):
    id = ma.fields.String(dump_to='ssid')
    hosts = ma.fields.Nested("HostSchema", only='hostname', many=True)


class HostSchema(marshmallow.ModelSchema):
    session_id = ma.fields.String(dump_to='comment')

    class Meta:
        model = Host
