# -*- coding: utf-8 -*-
"""
Implementation of OpenNebula node model.

https://opennebula.io/
"""
from duffy.database import db, Duffyv1Model


class OpennebulaHost(Duffyv1Model):
    """
    Open Nebula node model.

    Attributes:
      id (int): Unique identifier of the node
      name (str): Open Nebula VM name
      hostname (str): Node hostname
      ip (str): Node IP address
      state (str): Current state of the node
      comment (str): Comment for this node. For example output of the failed test.
      template_id (str): Identifier of the template used for VM creation
      flavor (str): Type of the VM based on the resources
      session_id (str): Id of the session linked to this machine
      session (`db.relationship`): Relationship to `Session` table
    """
    __tablename__ = 'opennebula_nodes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30))
    hostname = db.Column(db.String(20))
    ip = db.Column(db.String(15))
    state = db.Column(db.String(20))
    comment = db.Column(db.String(255))
    template_id = db.Column(db.String(30))
    flavor = db.Column(db.String(20))
    session_id = db.Column(db.String(37), db.ForeignKey('sessions.id'))
    session = db.relationship('Session', lazy='joined')

    def contextualize(self, project):
        """
        Add the project SSH keys to authorized keys on the node.
        """
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
