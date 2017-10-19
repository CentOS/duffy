# -*- coding: utf-8 -*-

import unittest

from duffy.app import create_app
from duffy.database import db
from duffy.config import DevConfig
from duffy.models import Host
import json


def _populate_test_data(db):
    n1hufty = Host(hostname='n1.hufty',
                   ip='127.0.0.1',
                   chassis='hufty',
                   used_count=4,
                   state='Ready',
                   comment='-',
                   distro=None,
                   rel=None,
                   ver=7,
                   arch='x86_64',
                   pool=1,
                   console_port=123)

    n2hufty = Host(hostname='n2.hufty',
                   ip='127.0.0.2',
                   chassis='hufty',
                   used_count=5,
                   state='Ready',
                   comment='-',
                   distro=None,
                   rel=None,
                   ver=6,
                   arch='x86_64',
                   pool=1,
                   console_port=123)

    n3hufty = Host(hostname='n3.hufty',
                   ip='127.0.0.3',
                   chassis='hufty',
                   used_count=5,
                   state='Ready',
                   comment='-',
                   distro=None,
                   rel=None,
                   ver=6,
                   arch='x86_64',
                   pool=1,
                   console_port=123)

    n4hufty = Host(hostname='n4.hufty',
                   ip='127.0.0.4',
                   chassis='hufty',
                   used_count=4,
                   state='Ready',
                   comment='-',
                   distro=None,
                   rel=None,
                   ver=7,
                   arch='x86_64',
                   pool=1,
                   console_port=123)

    n5hufty = Host(hostname='n5.hufty',
                   ip='127.0.0.5',
                   chassis='hufty',
                   used_count=4,
                   state='Ready',
                   comment='-',
                   distro=None,
                   rel=None,
                   ver=7,
                   arch='x86_64',
                   pool=1,
                   console_port=123)

    db.session.add(n1hufty)
    db.session.add(n2hufty)
    db.session.add(n3hufty)
    db.session.add(n4hufty)
    db.session.commit()


class DuffyV1ApiTests(unittest.TestCase):
    def setUp(self):
        self.testapp = create_app(DevConfig)
        self.client = self.testapp.test_client()
        with self.testapp.app_context():
            db.create_all()
            _populate_test_data(db)

    def tearDown(self):
        with self.testapp.app_context():
            db.drop_all()

    def test_api_returns_something(self):
        r = self.client.get('/Node/get')
        data = json.loads(r.data)
        assert data['hosts'][0]['ver'] == '7'
        assert data['hosts'][0]['arch'] == 'x86_64'
        assert data['hosts'][0]['distro'] is None
        assert data['hosts'][0]['state'] == 'Deployed'

    def test_api_returns_host_with_correct_ver(self):
        r = self.client.get('/Node/get?ver=6')
        data = json.loads(r.data)
        assert data['hosts'][0]['ver'] == '6'
        assert data['hosts'][0]['arch'] == 'x86_64'
        assert data['hosts'][0]['distro'] is None
        assert data['hosts'][0]['state'] == 'Deployed'

    def test_api_returns_multiple_hosts(self):
        r = self.client.get('/Node/get?count=2')
        data = json.loads(r.data)
        assert data['hosts'][0]['ver'] == '7'
        assert data['hosts'][0]['arch'] == 'x86_64'
        assert len(data['hosts']) == 2

    def test_api_doesnt_return_unless_it_fills_the_request(self):
        r = self.client.get('/Node/get?count=100')
        try:
            data = json.loads(r.data)
        except:
            assert 'Insufficient Nodes in READY State' in r.data

    def test_exhausting_the_pool(self):
        for poolsize in range(4):
            try:
                r = self.client.get('/Node/get')
                data = json.loads(r.data)
            except:
                assert 'Insufficient Nodes in READY State' in r.data
