import datetime
from duffy.database import db
from duffy.models import Host, Session, Project

def _populate_test_data():
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
                  flavor='tiny',
                  console_port=123)

    n2p8h1 = Host(hostname='n2.p8h2',
                  ip='127.0.0.6',
                  chassis='p8h2',
                  used_count=6,
                  state='Ready',
                  comment='-',
                  distro=None,
                  rel=None,
                  ver=7,
                  arch='ppc64le',
                  pool=1,
                  flavor='medium',
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
    db.session.add(n2p8h1)
    db.session.add(testproject)
    db.session.commit()
