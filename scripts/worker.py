'''
Worker executes ansible playbooks as per beansalkc request to
provision/poweroff nodes.
'''

import json
import subprocess
from flask_sqlalchemy import SQLAlchemy
from duffy import APP
from duffy.models.nodes import Host

import beanstalkc
BS = beanstalkc.Connection(host='127.0.0.1', parse_yaml=False)
BS.watch('requests')
BS.ignore('default')

DB = SQLAlchemy(APP)

APP.app_context().push()
with APP.app_context():
    DB.init_app(APP)


def provision(json_jobs):
    '''
    This function executes ansible playbook local-ci-deploy.yml && updates db
    accordingly
    '''
    cmd_line = "date ; cd /srv/code/ansible  ; /usr/bin/ansible-playbook \
            playbooks/local-ci-deploy.yml --limit %s.ci.centos.org \
            --extra-vars 'centos_dist=%s centos_arch=%s'"\
            % (json_jobs['hostname'], json_jobs['ver'], json_jobs['arch'])
    return_code = subprocess.call(cmd_line, shell=True)
    print(cmd_line)
    print('Returned : ', return_code)
    hostname_var = json_jobs['hostname']
    print(hostname_var)
    session_query = Host.query.filter_by(hostname=hostname_var).first()
    if return_code == 0:
        session_query.state = 'Ready'
        session_query.next_state = 'Deployed'
    else:
        session_query.state = 'Failed'
        session_query.next_state = 'Active'
        session_query.comment = 'ansible exit {}'.format(return_code)
        session_query.pool = 0

    current_session = DB.object_session(session_query)
    current_session.add(session_query)
    current_session.commit()


def poweroff(json_jobs):
    '''
    This function executes ansible playbook local-ci-poweroff.yml && updates db
    accordingly
    '''
    cmd_line = "cd /srv/code/ansible ; ansible-playbook \
            playbooks/local-ci-poweroff.yml --limit %s.ci.centos.org"\
            % json_jobs['hostname']
    return_code = subprocess.call(cmd_line, shell=True)
    hostname_var = json_jobs['hostname']
    session_query = Host.query.filter_by(hostname=hostname_var).first()
    if return_code == 0:
        session_query.state = 'Active'
        session_query.next_state = 'Ready'
        session_query.pool = 0
    else:
        session_query.state = 'Failed'
        session_query.next_state = 'Active'
        session_query.comment = 'Failed to poweroff'
        session_query.pool = 0

    current_session = DB.object_session(session_query)
    current_session.add(session_query)
    current_session.commit()


def task():
    '''
    This finction checks beanstalkc pool and calls function as per requirement.
    '''
    job = BS.reserve()
    json_jobs = json.loads(job.body)
    if json_jobs['request'] == 'Provision':
        provision(json_jobs)

    if json_jobs['request'] == 'Poweroff':
        poweroff(json_jobs)

    job.delete()


while True:
    task()
