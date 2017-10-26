# -*- coding: utf-8 -*-

import datetime
import unittest

from duffy.app import create_app
from duffy.database import db
from duffy.config import TestConfig as CONFIG
from duffy.models import Host, Session, Project
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

    n1p8h1 = Host(hostname='n1.p8h1',
                  ip='127.0.0.6',
                  chassis='p8h1',
                  used_count=6,
                  state='Ready',
                  comment='-',
                  distro=None,
                  rel=None,
                  ver=7,
                  arch='ppc64le',
                  pool=1,
                  console_port=123)

    testproject = Project(apikey='asdf-1234',
                          projectname='uniitest-proj',
                          jobname='asdf123',
                          createdat=datetime.datetime(1970, 1, 1, 1, 0),
                          limitnodes=2)

    db.session.add(n1hufty)
    db.session.add(n2hufty)
    db.session.add(n3hufty)
    db.session.add(n4hufty)
    db.session.add(n1p8h1)
    db.session.add(testproject)
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
            assert Host.query.filter(Host.hostname == 'n1.hufty').one().state == 'Ready'
        r = self.client.get('/Node/get?key=asdf-1234')
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
        r = self.client.get('/Node/get?key=asdf-1234&ver=6')
        data = json.loads(r.data)

        for hostname in data['hosts']:
            with self.testapp.app_context():
                h = Host.query.filter(Host.hostname == hostname).one()
                assert h.ver == '6'
                assert h.arch == 'x86_64'
                assert h.distro is None
                assert h.state == 'Deployed'

    def test_api_returns_host_with_correct_arch(self):
        r1 = self.client.get('/Node/get?key=asdf-1234&arch=ppc64le')
        data = json.loads(r1.data)

        for hostname in data['hosts']:
            with self.testapp.app_context():
                h = Host.query.filter(Host.hostname == hostname).one()
                assert h.ver == '7'
                assert h.arch == 'ppc64le'
                assert h.distro is None
                assert h.state == 'Deployed'

    def test_api_returns_multiple_hosts(self):
        r = self.client.get('/Node/get?key=asdf-1234&count=2')
        data = json.loads(r.data)
        for hostname in data['hosts']:
            with self.testapp.app_context():
                h = Host.query.filter(Host.hostname == hostname).one()
                assert h.ver == '7'
                assert h.arch == 'x86_64'
                assert len(data['hosts']) == 2

    def test_api_doesnt_return_unless_it_fills_the_request(self):
        r = self.client.get('/Node/get?key=asdf-1234&count=100')
        try:
            data = json.loads(r.data)
        except ValueError:
            assert 'Insufficient Nodes in READY State' in r.data

    def test_exhausting_the_pool(self):
        for poolsize in range(4):
            try:
                r = self.client.get('/Node/get?key=asdf-1234&')
                data = json.loads(r.data)
            except ValueError:
                assert 'Insufficient Nodes in READY State' in r.data

    def test_host_has_ssid(self):
        r = self.client.get('/Node/get?key=asdf-1234&')
        data = json.loads(r.data)

        assert len(data['ssid']) == 8

    def test_different_ssids_per_session(self):
        r1 = self.client.get('/Node/get?key=asdf-1234')
        r1data = json.loads(r1.data)

        r2 = self.client.get('/Node/get?key=asdf-1234')
        r2data = json.loads(r2.data)

        assert r1data['ssid'] != r2data['ssid']

    def test_session_has_state(self):
        r1 = self.client.get('/Node/get?key=asdf-1234&count=2')
        r1data = json.loads(r1.data)

        with self.testapp.app_context():
            s = Session.query.get(r1data['ssid'])
            assert s.state == 'Prod'

    def test_session_has_hosts(self):
        r1 = self.client.get('/Node/get?key=asdf-1234&count=2')
        r1data = json.loads(r1.data)

        with self.testapp.app_context():
            s = Session.query.get(r1data['ssid'])
            assert len(s.hosts) == 2

    def test_nodedone_without_apikey_fails(self):
        r1 = self.client.get('/Node/done')
        data = json.loads(r1.data)
        assert data['msg'] == 'Invalid duffy key'
        assert r1.status_code == 403

    def test_nodedone_without_ssid_fails(self):
        r1 = self.client.get('/Node/done?key=asdf-1234')
        data = json.loads(r1.data)
        assert data['msg'] == 'Invalid session ID'
        assert r1.status_code == 403

    def test_nodedone_sets_node_state(self):
        r1 = self.client.get('/Node/get?key=asdf-1234&count=2')
        r1data = json.loads(r1.data)

        with self.testapp.app_context():
            s = Session.query.get(r1data['ssid'])

            r2 = self.client.get('/Node/done?key=asdf-1234&ssid={0}'.format(s.id))
            for host in s.hosts:
                assert host.state == 'Deprovision'

    def test_nodedone_sets_session_state(self):
        r1 = self.client.get('/Node/get?key=asdf-1234&count=2')
        r1data = json.loads(r1.data)

        with self.testapp.app_context():
            s = Session.query.get(r1data['ssid'])
            r2 = self.client.get('/Node/done?key=asdf-1234&ssid={0}'.format(s.id))

            assert s.state == 'Done'

    def test_nodedone_with_different_apikey_fails(self):
        r1 = self.client.get('/Node/get?key=asdf-1234&count=2')
        r1data = json.loads(r1.data)

        with self.testapp.app_context():
            s = Session.query.get(r1data['ssid'])

            r2 = self.client.get('/Node/done?key=hjkl-4567&ssid={0}'.format(s.id))
            r2data = json.loads(r2.data)
            assert r2data['msg'] == 'Invalid duffy key'
            assert r2.status_code == 403

    def test_nodedone_with_bad_ssid_fails(self):
        r1 = self.client.get('/Node/get?key=asdf-1234&count=2')
        r1data = json.loads(r1.data)

        with self.testapp.app_context():
            r2 = self.client.get('/Node/done?key=1234567890&ssid={0}'.format('INVALID_SSID'))
            r2data = json.loads(r2.data)
            assert r2data['msg'] == 'Invalid session ID'
            assert r2.status_code == 403

    def test_nodefail_sets_node_state(self):
        r1 = self.client.get('/Node/get?key=asdf-1234&count=2')
        r1data = json.loads(r1.data)

        with self.testapp.app_context():
            s = Session.query.get(r1data['ssid'])

            r2 = self.client.get('/Node/fail?key=asdf-1234&ssid={0}'.format(s.id))
            for host in s.hosts:
                assert host.state == 'Fail'

    def test_nodefail_sets_session_state(self):
        r1 = self.client.get('/Node/get?key=asdf-1234&count=2')
        r1data = json.loads(r1.data)

        with self.testapp.app_context():
            s = Session.query.get(r1data['ssid'])

            r2 = self.client.get('/Node/fail?key=asdf-1234&ssid={0}'.format(s.id))
            assert s.state == 'Fail'

    def test_nodefail_with_different_apikey_fails(self):
        r1 = self.client.get('/Node/get?key=asdf-1234&count=2')
        r1data = json.loads(r1.data)

        with self.testapp.app_context():
            s = Session.query.get(r1data['ssid'])

            r2 = self.client.get('/Node/fail?key=hjkl-4567&ssid={0}'.format(s.id))
            r2data = json.loads(r2.data)
            assert r2data['msg'] == 'Invalid duffy key'
            assert r2.status_code == 403

    def test_nodefail_with_bad_ssid_fails(self):
        r1 = self.client.get('/Node/get?key=asdf-1234&count=2')
        r1data = json.loads(r1.data)

        with self.testapp.app_context():
            r2 = self.client.get('/Node/fail?key=1234567890&ssid={0}'.format('INVALID_SSID'))
            r2data = json.loads(r2.data)
            assert r2data['msg'] == 'Invalid session ID'
            assert r2.status_code == 403
