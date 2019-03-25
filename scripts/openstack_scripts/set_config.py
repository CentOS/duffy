from ConfigParser import ConfigParser

config = ConfigParser()

config.add_section('openstackrc')
config.set('openstackrc', 'OS_NO_CACHE', 'true')
config.set('openstackrc', 'OS_PROJECT_NAME', 'centos_ci')
config.set('openstackrc', 'OS_USERNAME', 'xxxxx')
config.set('openstackrc', 'OS_PASSWORD', 'xxxxxx')
config.set('openstackrc', 'OS_AUTH_URL', 'xxxxxxx')
config.set('openstackrc', 'OS_AUTH_STRATEGY', 'keystone')
config.set('openstackrc', 'OS_REGION_NAME', 'RegionOne')
config.set('openstackrc', 'OS_PROJECT_DOMAIN_NAME', 'default')
config.set('openstackrc', 'OS_USER_DOMAIN_NAME', 'default')
config.set('openstackrc', 'CINDER_ENDPOINT_TYPE', 'publicURL')
config.set('openstackrc', 'GLANCE_ENDPOINT_TYPE', 'publicURL')
config.set('openstackrc', 'KEYSTONE_ENDPOINT_TYPE', 'publicURL')
config.set('openstackrc', 'NOVA_ENDPOINT_TYPE', 'publicURL')
config.set('openstackrc', 'NEUTRON_ENDPOINT_TYPE', 'publicURL')
config.set('openstackrc', 'OS_IDENTITY_API_VERSION', '3')

with open('/etc/duffy.ini', 'a+') as f:
    config.write(f)
