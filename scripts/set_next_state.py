'''
sets next_state
'''
import argparse

from flask_sqlalchemy import SQLAlchemy
from duffy import APP
from duffy.models.nodes import Host

DB = SQLAlchemy(APP)

APP.app_context().push()
with APP.app_context():
    DB.init_app(APP)

def return_error(hostname):
    '''
    error handeling function, <TODO> Elegant ways
    '''
    print("{} doesn't exist".format(hostname))


def next_state(hostname_var, state):
    ''' sets next state
    '''
    session_query = Host.query.filter_by(hostname=hostname_var).first()
    if not session_query:
        return_error(hostname_var)
    else:
        session_query.next_state = state
        current_session = DB.object_session(session_query)
        current_session.add(session_query)
        current_session.commit()


def main():
    '''
    takes state and hostname and calls next_state function that changes the
    state.
    '''
    state_help = 'next state'
    hostname_help = 'hostname that is to be sent in $state state'

    parser = argparse.ArgumentParser(description='sets next state for a node')
    parser.add_argument('-s', '--state', type=str, help=state_help)
    parser.add_argument('-n', '--hostname', type=str, help=hostname_help)
    args = parser.parse_args()
    state = args.state
    hostname = args.hostname

    next_state(hostname, state)


if __name__ == '__main__':
    main()
