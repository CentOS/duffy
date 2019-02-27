from sys import argv

from flask_sqlalchemy import SQLAlchemy
from duffy import APP
from duffy.models.nodes import Host
DB = SQLAlchemy(APP)

APP.app_context().push()
with APP.app_context():
    DB.init_app(APP)


def count(status):
    '''
    returns number of VMs in given state
    '''
    return(Host.query.filter_by(state=status).count())


def display_status():
    '''
    prints number of VMs in given state, state are provided in list states
    '''
    states = ['Active', 'Failed',  'Ready', 'Reserved', 'Deployed', 'Provisioning']
    for state in states:
        print("{} \t: {}".format(state, count(state)))


def reset_failed_nodes():
    '''
    Query all the failed nodes -> Change state to 'Active' -> add & commit
    '''
    failed_nodes = Host.query.filter_by(state='Failed').all()
    print("CHANGING FAILED NODE STATUS TO ACTIVE\n")
    print(failed_nodes)
    for single_node in failed_nodes:
        single_node.state = 'Active'
        session = DB.object_session(single_node)
        session.add(single_node)

    session.commit()


def main():
    try:
        if argv[1] == '-r' or argv[1] == 'reset':
            if count('Failed'):
                display_status()
                reset_failed_nodes()
            else:
                print("No failed nodes")
    except:
        pass

    display_status()


if __name__ == '__main__':
    main()

