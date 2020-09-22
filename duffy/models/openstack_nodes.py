# -*- coding: utf-8 -*-
from duffy.database import db, Duffyv1Model
from .nodes import *


class openstack_host(Duffyv1Model):
    __tablename__ = 'openstack_nodes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30))
    hostname = db.Column(db.String(20))
    ip = db.Column(db.String(15))
    state = db.Column(db.String(20))
    next_state = db.Column(db.String(20))
    comment = db.Column(db.String(255))
    image_source = db.Column(db.String(30))
    flavor = db.Column(db.Sting(20))
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
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            key = paramiko.RSAKey.from_private_key_file(os.path.expanduser('~/.ssh/id_rsa'))
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
