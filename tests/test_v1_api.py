# -*- coding: utf-8 -*-

import datetime
import json
import unittest
import mock 

# Normal imports
from duffy.app import create_app
from duffy.data import _populate_test_data
from duffy.database import db
from duffy.config import TestConfig as CONFIG
from duffy.models import Host, Session, Project

#Stuff we patch/mock out later
from duffy.models.nodes import uuid


class DuffyV1ApiTests(unittest.TestCase):
    def setUp(self):
        self.testapp = create_app(CONFIG)
        self.client = self.testapp.test_client()
        m = mock.MagicMock(return_value=True)
        Host.contextualize = m
        with self.testapp.app_context():
            _populate_test_data()

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

    def test_api_returns_host_with_correct_flavor(self):

        # Test request with a default flavor
        r1 = self.client.get('/Node/get?key=asdf-1234&arch=ppc64le')
        data = json.loads(r1.data)

        for hostname in data['hosts']:
            with self.testapp.app_context():
                h = Host.query.filter(Host.hostname == hostname).one()
                assert h.ver == '7'
                assert h.arch == 'ppc64le'
                assert h.distro is None
                assert h.state == 'Deployed'
                assert h.flavor == 'tiny'

        # Test a request with a specified flavor
        r2 = self.client.get('/Node/get?key=asdf-1234&arch=ppc64le&flavor=medium')
        data = json.loads(r2.data)

        for hostname in data['hosts']:
            with self.testapp.app_context():
                h = Host.query.filter(Host.hostname == hostname).one()
                assert h.ver == '7'
                assert h.arch == 'ppc64le'
                assert h.distro is None
                assert h.state == 'Deployed'
                assert h.flavor == 'medium'

    def test_api_returns_host_without_excluded_hostname(self):
        for hname in [".hufty", ".crusty", "n2.crusty"]:
            r1 = self.client.get('/Node/get?key=asdf-1234&exclude_host=%{}'.format(hname))
            data = json.loads(r1.data)

            for hostname in data['hosts']:
                with self.testapp.app_context():
                    h = Host.query.filter(Host.hostname == hostname).one()
                    assert h.ver == '7'
                    assert not hostname.endswith(hname)

    def test_api_returns_host_without_multiple_excluded_hostnames(self):
        r1 = self.client.get('/Node/get?key=asdf-1234&exclude_host=%.hufty,n1.crusty')
        data = json.loads(r1.data)

        for hostname in data['hosts']:
            with self.testapp.app_context():
                h = Host.query.filter(Host.hostname == hostname).one()
                assert h.ver == '7'
                assert not hostname.endswith('.hufty')
                assert hostname != 'n1.crusty'

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

    def test_nodedone_node_has_no_session_after(self):
        r1 = self.client.get('/Node/get?key=asdf-1234&count=2')
        r1data = json.loads(r1.data)

        with self.testapp.app_context():
            s = Session.query.get(r1data['ssid'])

            r2 = self.client.get('/Node/done?key=asdf-1234&ssid={0}'.format(s.id))
            for host in s.hosts:
                assert host.session == None
                assert host.session_id == ''

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

    def test_inventory_with_apikey_returns_hosts_and_sessions(self):
        r = self.client.get('/Node/get?key=asdf-1234&count=2')
        data = json.loads(r.data)

        i = self.client.get('/Inventory?key=asdf-1234')
        idata = json.loads(i.data)
        assert any('n1.hufty' in x for x in idata)
        assert any('n4.hufty' in x for x in idata)

    @mock.patch.object(uuid, 'uuid4', return_value='deadbeef')
    def test_inventory_without_apikey_returns_all_hosts(self, mock_uuid):
        r = self.client.get('/Node/get?key=asdf-1234&count=2')
        n1huftylist = [1, u'n1.hufty', u'127.0.0.1', u'hufty', 4, u'Deployed', u'deadbeef', None, None, u'7', u'x86_64', 1, 123, None]
        n2huftylist = [2, u'n2.hufty', u'127.0.0.2', u'hufty', 5, u'Ready', None, None, None, u'6', u'x86_64', 1, 123, None]
        data = json.loads(r.data)
        i = self.client.get('/Inventory')
        idata = json.loads(i.data)

        assert n1huftylist in idata
        assert n2huftylist in idata

