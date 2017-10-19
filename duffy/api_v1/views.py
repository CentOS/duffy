# -*- coding: utf-8 -*-
from flask import Blueprint, request
from duffy.models import Host, HostSchema, Session
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

    s = Session()
    s.save()
    for host in hosts:
        host.comment = s.id
        host.state = 'Deployed'
        host.save()
        s.hosts.append(host)
    s.save()

    return HostSchema(many=True).jsonify(hosts)
