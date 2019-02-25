# -*- coding: utf-8 -*-
import datetime
import uuid

from duffy.database import db, Duffyv1Model
from duffy.extensions import marshmallow
from nodes import *


class Host(Duffyv1Model):
    __tablename__ = 'stock'
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(20))
    ip = db.Column(db.String(15))
    chassis = db.Column(db.String(20))
    used_count = db.Column(db.Integer)
    state = db.Column(db.String(20))
    next_state = db.Column(db.String(20))
    comment = db.Column(db.String(255))
    distro = db.Column(db.String(20))
    rel = db.Column(db.String(10))
    ver = db.Column(db.String(10))
    arch = db.Column(db.String(10))
    image = db.Column(db.String(255)) # provide path to local image to be used
    # by glance <feature request - TBD>
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

            ssh.connect(self.ip, username='root', pkey=key)
            sftp = ssh.open_sftp()
            file_handle = sftp.file('/root/.ssh/authorized_keys', mode='a', bufsize=-1)
        except Exception as e:
            self.state = 'Active'
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
        return True
