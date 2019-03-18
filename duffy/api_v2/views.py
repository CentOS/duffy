# -*- coding: utf-8 -*-

from flask import Blueprint, request, jsonify, abort, current_app

blueprint = Blueprint('api_v2', __name__, url_prefix='/v2')

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

@blueprint.route('/users', methods=['GET','POST'])
def users:
    pass
