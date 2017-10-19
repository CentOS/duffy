# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from duffy.models import Host, HostSchema, Session, SessionSchema
from duffy.database import db

blueprint = Blueprint('api_v1', __name__)


@blueprint.route('/Node/get')
def nodeget():
    get_ver = request.args.get('ver', 7)
    get_arch = request.args.get('arch', 'x86_64')
    get_count = int(request.args.get('count', 1))

    hosts = Host.query.filter(Host.pool == 1,
                              Host.state == 'Ready',
                              Host.ver == get_ver,
                              Host.arch == get_arch
                              ).order_by(db.asc(Host.used_count)).limit(get_count).all()

    if len(hosts) != get_count:
        return 'Insufficient Nodes in READY State'

    sess = Session()
    sess.save()
    for host in hosts:
        host.state = 'Deployed'
        sess.hosts.append(host)
        host.save()
    sess.save()

    rtn = SessionSchema().dump(sess)
    return jsonify(rtn.data)
