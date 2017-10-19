# -*- coding: utf-8 -*-

import unittest

from duffy.app import create_app
from duffy.database import db
from duffy.config import DevConfig as CONFIG
from duffy.models import Host, Session
import json


def _populate_test_data(db):
    # If more C7 x86_64 hosts are added make sure n1.hufty has the lowest
    # used_count.
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
                   used_count=6,
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
                   used_count=6,
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
        self.testapp = create_app(CONFIG)
        self.client = self.testapp.test_client()
        with self.testapp.app_context():
            db.create_all()
            _populate_test_data(db)

    def tearDown(self):
        with self.testapp.app_context():
            db.drop_all()

    def test_api_returns_host_with_the_lowest_used_count(self):
        # n1.hufty should be the one with the lowest used_count, see
        # _populate_test_data() for the definition
        with self.testapp.app_context():
            assert Host.query.filter(Host.hostname=='n1.hufty').one().state == 'Ready'
        r = self.client.get('/Node/get')
        data = json.loads(r.data)
        for hostname in data['hosts']:
            with self.testapp.app_context():
                h = Host.query.filter(Host.hostname == hostname).one()
                assert h.ver == '7'
                assert h.hostname == 'n1.hufty'
                assert h.arch == 'x86_64'
                assert h.distro is None
                assert h.state == 'Deployed'

    def test_api_returns_host_with_correct_ver(self):
        with self.testapp.app_context():
            assert Host.query.filter(Host.hostname=='n1.hufty').one().state == 'Ready'
        r = self.client.get('/Node/get?ver=6')
        data = json.loads(r.data)

        for hostname in data['hosts']:
            with self.testapp.app_context():
                h = Host.query.filter(Host.hostname == hostname).one()
                assert h.ver == '6'
                assert h.arch == 'x86_64'
                assert h.distro is None
                assert h.state == 'Deployed'

    def test_api_returns_multiple_hosts(self):
        r = self.client.get('/Node/get?count=2')
        data = json.loads(r.data)
        for hostname in data['hosts']:
            with self.testapp.app_context():
                h = Host.query.filter(Host.hostname == hostname).one()
                assert h.ver == '7'
                assert h.arch == 'x86_64'
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

    def test_host_has_ssid(self):
        r = self.client.get('/Node/get')
        data = json.loads(r.data)

        assert len(data['ssid']) == 8

    def test_different_ssids_per_session(self):
        r1 = self.client.get('/Node/get')
        r1data = json.loads(r1.data)

        r2 = self.client.get('/Node/get')
        r2data = json.loads(r2.data)

        assert r1data['ssid'] != r2data['ssid']

    def test_session_has_hosts(self):
        r1 = self.client.get('/Node/get?count=2')
        r1data = json.loads(r1.data)

        with self.testapp.app_context():
            s = Session.query.get(r1data['ssid'])
            assert len(s.hosts) == 2
