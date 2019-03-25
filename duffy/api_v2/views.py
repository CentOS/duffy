# -*- coding: utf-8 -*-
import time
import base64
import ConfigParser
import openstack
from duffy.database import db
from urlparse import urlparse
from functools import wraps
from flask import Blueprint, request, jsonify, abort, current_app
from duffy.models import openstack_host, HostSchema, Session, SessionSchema,
Project

blueprint = Blueprint('api_v1', __name__)


def duffy_key_required(fn):
    '''
    duffy key validator
    '''
    @wraps(fn)
    def decorated(*args, **kwargs):
        duffy_key = request.args.get('key', None)
        if not duffy_key:
            return jsonify({'msg': 'Invalid duffy key'}), 403
        return fn(*args, **kwargs)
    return decorated


def ssid_required(fn):
    '''
    confirms ssid
    '''
    @wraps(fn)
    def decorated(*args, **kwargs):
        ssid = request.args.get('ssid')
        if not ssid:
            return jsonify({'msg': 'Invalid session ID'}), 403

        sess = Session.query.get(ssid)
        if not sess:
            return jsonify({'msg': 'Invalid session ID'}), 403
        return fn(*args, **kwargs)
    return decorated


def connection():
    '''
    Reads file from a location (default: /etc/duffy.ini) and returns
    connection object
    '''
    config = ConfigParser()
    try:
        config.read('/etc/duffy.ini')
        return openstack.connect(
                auth_url=config.get('openstackrc', 'OS_AUTH_URL'),
                project_name=config.get('openstackrc', 'OS_PROJECT_NAME'),
                username=config.get('openstackrc', 'OS_USERNAME'),
                password=config.get('openstackrc', 'OS_PASSWORD'),
                region_name=config.get('openstackrc', 'OS_REGION_NAME'),
                domain_name=config.get('openstackrc', 'OS_PROJECT_DOMAIN_NAME')
                )
    except Exception as e:
        current_app.logger.info('Error in connection: {}'.format(e))


def upload_image(image_name, uri, disk_format='qcow2', conn=connection()):
    '''
    takes an image_name, url to qcow2 image and uploads it to be used
    later
    '''
    try:
        conn.image.upload_image(name=image_name, disk_format=disk_format,
                                container_format='bare', visibility='public',
                                method='web-download', uri=uri)
    except Exception as e:
        current_app.logger.info('Error while uploading the image: {}'.format(e))


def create_server(image, flavor, keypair_name='duffy-key-rsa',
                  number_of_server=1, user_data='/etc/cloud-init.yml',
                  conn=connection()):
    '''
    takes image name, flavor name and number of servers to be created, and
    returns a dictionary with servers' data
    '''
    servers = dict()
    image_info = conn.compute.find_image(image)
    flavor_info = conn.compute.find_flavor(flavor)
    keypair = conn.compute.find_keypair(keypair_name)
    with open(user_data, "rb") as file:
        script = base64.b64encode(file.read())

    for i in range(number_of_server):
        servers[i] = dict()
        server_name = image+'_'+str(int(time.time()))
        try:
            instance = conn.compute.create_server(name=server_name,
                                                  image_id=image_info.id,
                                                  flavor_id=flavor_info.id,
                                                  key_name=keypair.name,
                                                  user_data=script)
            instance = conn.compute.wait_for_server(instance)
            time.sleep(5)
            servers[i]['id'] = instance.id
            # servers[i]['hypervisor_hostname'] = instance.hypervisor_hostname
            # Hostname empty since server doesn't vm's return it yet.
            servers[i]['hostname'] = ''
            servers[i]['flavor'] = flavor
            servers[i]['ip'] = instance.addresses['ci_network'][0]['addr']
            servers[i]['image_id'] = instance.image['id']
            servers[i]['server_name'] = server_name
            servers[i]['status'] = instance.status
        except Exception as e:
            current_app.logger.info('Error in openstack connection: {}'.format(e))
    return servers


def delete(server_name, conn=connection()):
    '''
    deletes a server with server name
    '''
    try:
        server = conn.compute.find_server(server_name)
        conn.compute.delete_server(server)
    except Exception as e:
        current_app.logger.info('Error in openstack connection: {}'.format(e))


def delete_image(image_name, conn=connection()):
    '''
    deletes image when provided an imaga name
    '''
    image = conn.image.find_image(image_name)
    if image:
        try:
            conn.image.delete_image(image, ignore_missing=False)
        except:
            print("Unable to delete image {}".format(image_name))



def image_name_not_taken(image_name, conn=connection()):
    '''
    checks if image name exists, returns True or False
    '''
    try:
        image = conn.compute.image_find(image_name)
        return True if image is None else False
    except Exception as e:
        current_app.logger.info('Error in uploading image: {}'.format(e))


@blueprint.route('/Node/get')
@duffy_key_required
def nodeget():
    '''
    Request image, key, flavor and type of node. Serve by provisioning a node
    and assigning it to the requester.
    '''
    allowed_urls = ['artifacts.ci.centos.org', 'cloud.centos.org']

    get_image = request.args.get('image')
    get_url = request.args.get('url')
    get_key = request.args.get('key')
    get_flavor = request.args.get('flavor')
    get_type = request.args.get('type')
    get_count = request.args.get('count')

    project = Project.query.get(get_key)

    if not project:
        return 'Invalid duffy key'

    if not get_image:
        get_image = 'centos_7_x86_64'

    if not get_flavor:
        get_flavor = 'tiny'

    if not get_type or get_type.lower() != 'vm':
        return 'Type error'

    if not get_count:
        get_count = 1

    if get_url:
        if urlparse(get_url).netloc in allowed_urls:
            if image_name_not_taken(get_image):
                try:
                    upload_image(get_image, get_url)
                except:
                    return 'Error in uploading image'
            else:
                return 'Image with this name already exists, please provide
            unique image name'
        else:
            return 'Images provided is from unaccepted source'
    else:
        get_url = None

    server_list = create_server(image=get_image, flavor=get_flavor,
                                keypair_name='duffy-key-rsa',
                                number_of_server=get_count,
                                user_data='/etc/cloud-init.yml')
    if len(server_list) == get_count:
        for server in server_list:
            try:
                db_obj = openstack_host()
                db_obj.id = server_list[server]['id']
                db_obj.name = server_list[server]['server_name']
                db_obj.hostname = ''
                db_obj.ip = server_list[server]['ip']
                db_obj.state = 'Contextualizing'
                db_obj.next_state = ''
                db_obj.comment = ''
                db_obj.image_source = get_url
                db_obj.flavor = get_flavor
                db_obj.save()
            except Exception as e:
                current_app.logger.info('Error while adding session to
                                        inventory: {}'.format(e))
                return 'failed to allocate node to the user'

        sess = Session()
        sess.apikey = get_key
        sess.save()

        for server in server_list:
            name = server_list[server]['name']
            server = openstack_host.query.filter(openstack_host.name=name)
            if openstack_host.contextualize(project):
                sess.hosts.append(server)
                server.state = 'Active'
                server.save()
            else:
                for server in server_list:
                    name = server_list[server]['name']
                    server =
                    openstack_host.query.filter(openstack_host.name=name)
                    server.state = 'Failed'
                    return jsonify('Failed to allocate nodes')

        sess.save()
        if get_url:
            delete_image(get_image)


@blueprint.route('/Node/done')
@duffy_key_required
@ssid_required
def nodedone():
    get_key = request.args.get('key')
    get_ssid = request.args.get('ssid')

    session = Session.query.get(get_ssid)

    if session.apikey != get_key:
        return jsonify({'msg': 'Invalid duffy key'}), 403

    if session.state not in ('Prod', 'Fail'):
        return jsonify({'msg': 'Session not in Prod'})

    for host in session.hosts:
        host.state = 'deleting'
        host.session = None
        host.session_id = ''
        host.save()
        server_name = host.name
        delete(server_name)

    session.state = 'Done'
    session.save()
    return 'Done'


@blueprint.route('/Node/fail')
@duffy_key_required
@ssid_required
def nodefail():
    get_key = request.args.get('key')
    get_ssid = request.args.get('ssid')

    session = Session.query.get(get_ssid)

    if session.apikey != get_key:
        return jsonify({'msg': 'Invalid duffy key'}), 403

    for host in session.hosts:
        pass
    session.state = 'Fail'
    session.save()

    return jsonify('Done')


@blueprint.route('/Inventory')
def inventory():
    get_key = request.args.get('key')
    if get_key:
        # Return a list of active sessions for the user whose key we have
        sessions = Session.query.filter(Session.apikey == get_key)
        rtn_sessions = []
        for session in sessions:
            for host in session.hosts:
                sch = HostSchema().dump(host)
                rtn_sessions.append([sch.data['hostname'],
                                     sch.data['session']])
        return jsonify(rtn_sessions)
    else:
        # No key, return a list of all hosts
        hosts = openstack_host.query.all()
        rtn_hosts = []

        for host in hosts:
            sch = HostSchema().dump(host)
            ordered_host = [sch.data['name'],
                            sch.data['hostname'],
                            sch.data['ip'],
                            sch.data['state'],
                            sch.data['image_source'],
                            sch.data['flavor'],
                            ]
            rtn_hosts.append(ordered_host)

        return jsonify(rtn_hosts)
