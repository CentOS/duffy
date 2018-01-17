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


class Host(Duffyv1Model):
    __tablename__ = 'stock'
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(20))
    ip = db.Column(db.String(15))
    chassis = db.Column(db.String(20))
    used_count = db.Column(db.Integer)
    state = db.Column(db.String(20))
    comment = db.Column(db.String(255))
    distro = db.Column(db.String(20))
    rel = db.Column(db.String(10))
    ver = db.Column(db.String(10))
    arch = db.Column(db.String(10))
    pool = db.Column(db.Integer)
    console_port = db.Column(db.Integer)
    flavor = db.Column(db.String(20))
    session_id = db.Column(db.String(37), db.ForeignKey('sessions.id'))
    session = db.relationship('Session', lazy='joined')

    def contextualize(self, project):
        self.state = 'Contextualizing'
        self.save()
        # Sync all of the keys to the root user on the remote host
        import paramiko
        import os
        try:
            ssh = paramiko.SSHClient()
            # TODO: Make this configurable
            key = paramiko.DSSKey.from_private_key_file(os.path.expanduser('~/.ssh/id_dsa'))
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(self.hostname, username='root', pkey=key)
            sftp = ssh.open_sftp()
            file_handle = sftp.file('/root/.ssh/authorized_keys', mode='a', bufsize=-1)
        except Exception as e:
            self.state = 'Ready'
            self.save()
            return False

        try:
            for sshkey in project.sshkeys:
                file_handle.write(sshkey.key + '\n')
            file_handle.flush()
            file_handle.close()
            ssh.close()
        except Exception as e:
            self.state = 'Failed'
            self.save()
            return False
        return True         # If all went well, we made it here

class SessionSchema(marshmallow.Schema):
    id = ma.fields.String(dump_to='ssid')
    hosts = ma.fields.Nested("HostSchema", only='hostname', many=True)

class HostSchema(marshmallow.ModelSchema):
    session_id = ma.fields.String(dump_to='comment')

    class Meta:
        model = Host
