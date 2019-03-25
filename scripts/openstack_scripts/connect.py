import openstack
from ConfigParser import ConfigParser


def connection():
    '''
    Returns connection object
    '''
    config = ConfigParser()
    config.read('/etc/duffy.ini')
    return openstack.connect(
            auth_url=config.get('openstackrc', 'OS_AUTH_URL'),
            project_name=config.get('openstackrc', 'OS_PROJECT_NAME'),
            username=config.get('openstackrc', 'OS_USERNAME'),
            password=config.get('openstackrc', 'OS_PASSWORD'),
            region_name=config.get('openstackrc', 'OS_REGION_NAME'),
            domain_name=config.get('openstackrc', 'OS_PROJECT_DOMAIN_NAME')
            )
