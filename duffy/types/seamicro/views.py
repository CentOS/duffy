# -*- coding: utf-8 -*-
from flask import Blueprint, render_template

from duffy.models import Host

blueprint = Blueprint('seamicro', __name__, url_prefix='/seamicro',
                      template_folder='templates')


@blueprint.route('/kickstarts/<hostname>')
def kickstart(hostname):
    h = Host.query.filter(Host.hostname == hostname).first_or_404()
    return render_template('seamicro-centos-7-ks.j2', host=h),\
        {'Content-Type': 'text/plain; charset=utf-8'}
