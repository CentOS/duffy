'''
<TODO>
This is a [WIP] python file to update worker from v1.
'''

from config import ProdConfig
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import json
import subprocess

import beanstalkc
bs_obj = beanstalkc.Connection(host='127.0.0.1', parse_yaml=False)
bs_obj.watch('requests')
bs_obj.ignore('default')

app = Flask(__name__)
app.config['DEBUG'] = ProdConfig.DEBUG
app.config['DEBUG_TB_ENABLED'] = ProdConfig.DEBUG_TB_ENABLED
app.config['ENV'] = ProdConfig.ENV
app.config['SQLALCHEMY_DATABASE_URI'] = ProdConfig.SQLALCHEMY_DATABASE_URI

db_obj = SQLAlchemy(app)

def connection_check():
    '''
    This function checks and establishes sqllite Connection.
    '''
    try:
        dummy_data = stock.query.first()
    except:
        global db_obj
        global app
        db_obj = SQLAlchemy(app)


def provision(json_jobs):
    '''
    This function executes ansible playbook local-ci-deploy.yml && updates db
    accordingly
    '''
    cmd_line = "date ; cd /srv/code/ansible  ; /usr/bin/ansible-playbook playbooks/local-ci-deploy.yml --limit %s.ci.centos.org --extra-vars 'centos_dist=%s centos_arch=%s'" % (json_jobs['hostname'], json_jobs['ver'], json_jobs['arch'])
    return_code = subprocess.call(cmd_line, shell=True)
    print(cmd_line)
    print('Returned : ', return_code)
    hostname_var = json_jobs['hostname']
    connection_check()
    session = stock.query.filter_by(hostname=hostname_var)
    if return_code == 0:
        session.state = 'Ready'
    else:
        session.state = 'Failed'
        session.comment = 'ansible exit {}'.format(return_code)
        session.pool = 0

    db_obj.session.commit()


def poweroff(json_jobs):
    '''
    This function executes ansible playbook local-ci-poweroff.yml && updates db
    accordingly
    '''
    cmd_line="cd /srv/code/ansible ; ansible-playbook playbooks/local-ci-poweroff.yml --limit %s.ci.centos.org" % j['hostname']
    return_code = subprocess.call(cmd_line, shell=True)
    connection_check()
    hostname_var = json_jobs['hostname']
    session = stock.query.filter_by(hostname=hostname_var)
    if return_code == 0:
        session.state = 'Active'
        session.pool = 0
    else:
        session.state = 'Failed'
        session.comment = 'Failed to poweroff'
        session.pool = 0

    db_obj.session.commit()

def task():
    '''
    This finction checks beanstalkc pool and calls function as per requirement.
    '''
    job = bs_obj.reserve()
    json_jobs = json.loads(job.body)
    if json_jobs['request'] == 'Provision':
        provision(json_jobs)

    if json_jobs['request'] == 'Poweroff':
        poweroff(json_jobs)

    job.delete()

while True:
    task()
