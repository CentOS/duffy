# -*- coding: utf-8 -*-
import datetime

from flask import Blueprint, request, jsonify, abort, current_app
from functools import wraps
from duffy.models import Host, HostSchema, Session, SessionSchema, Project
from duffy.database import db

blueprint = Blueprint('api_v1', __name__)


def duffy_key_required(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        duffy_key = request.args.get('key', None)
        if not duffy_key:
            return jsonify({'msg': 'Invalid duffy key'}), 403
        return fn(*args, **kwargs)
    return decorated

def ssid_required(fn):
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


@blueprint.route('/Node/get')
@duffy_key_required
def nodeget():
    get_ver = request.args.get('ver', 7)
    get_arch = request.args.get('arch', 'x86_64')
    get_count = int(request.args.get('count', 1))
    get_key = request.args.get('key')
    get_flavor = request.args.get('flavor')

    project = Project.query.get(get_key)

    if not project:
        return 'Invalid duffy key'

    if get_arch in ('aarch64','ppc64le'):
        if not get_flavor:
            get_flavor = 'tiny'

    five_minutes_ago = datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
    recent_sessions_count = Session.query.filter(Session.apikey==get_key, Session.delivered_at > five_minutes_ago, (Session.state == 'Prod') | (Session.state == 'Fail')).count()
    current_app.logger.info("Activity Rate: {} - {}".format(get_key, recent_sessions_count))

    if recent_sessions_count > 5:
        return jsonify('Failed to allocate nodes: Rate limit exceeded: {} sessions '
                       'in the last 5 minutes'.format(recent_sessions_count)
                       ), 429

    hosts = Host.query.filter(Host.pool == 1,
                              Host.state == 'Ready',
                              Host.ver == get_ver,
                              Host.arch == get_arch,
                              Host.flavor == get_flavor
                              ).order_by(db.asc(Host.used_count)).limit(get_count).all()

    if len(hosts) != get_count:
        return 'Insufficient Nodes in READY State'

    sess = Session()
    sess.apikey = get_key
    sess.save()
    for host in hosts:
        host.state = 'Contextualizing'
        host.save()
        if host.contextualize(project):
            sess.hosts.append(host)
            host.state = 'Deployed'
            host.save()
        else:
            # if any of the hosts fail we should return any in-progress hosts
            # to the pool for reclamation
            for host in sess.hosts:
                host.state = 'Active'
                host.save()
            sess.state = 'Failed'
            sess.save()
            return jsonify('Failed to allocate nodes')
    sess.save()

    rtn = SessionSchema().dump(sess)
    return jsonify(rtn.data)

@blueprint.route('/Node/done')
@duffy_key_required
@ssid_required
def nodedone():
    get_key = request.args.get('key')
    get_ssid = request.args.get('ssid')

    session = Session.query.get(get_ssid)

    if session.apikey != get_key:
        return jsonify({'msg': 'Invalid duffy key'}), 403

    for host in session.hosts:
        host.state = "Deprovision"
        host.session = None
        host.session_id = ''
        host.save()
    session.state = 'Done'
    session.save()
    return jsonify("Done")

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
        host.state = 'Fail'
        host.save()
    session.state = 'Fail'
    session.save()

    return jsonify("Done")

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
                rtn_sessions.append([sch.data['hostname'],sch.data['session']])
        return jsonify(rtn_sessions)
    else:
        # No key, return a list of all hosts
        hosts = Host.query.all()
        rtn_hosts = []

        for host in hosts:
            sch = HostSchema().dump(host)
            ordered_host = [sch.data['id'],
                            sch.data['hostname'],
                            sch.data['ip'],
                            sch.data['chassis'],
                            sch.data['used_count'],
                            sch.data['state'],
                            sch.data['comment'],
                            sch.data['distro'],
                            sch.data['rel'],
                            sch.data['ver'],
                            sch.data['arch'],
                            sch.data['pool'],
                            sch.data['console_port'],
                            sch.data['flavor'],
                            ]
            rtn_hosts.append(ordered_host)

        return jsonify(rtn_hosts)
