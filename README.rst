================================
Duffy v2
================================

The Duffy node provisioner for ci.centos.org

Quickstart
----------

Set a secret key in the environment.

.. code-block:: bash

    export DUFFY2_SECRET='SEKURITAH'

Set the ```FLASK_APP``` and ```FLASK_DEBUG``` environment variables
    
.. code-block:: bash

    export FLASK_APP=duffy
    export FLASK_DEBUG=1

Clone the duffy2 repo::

    git clone https://github.com/CentOS/duffy
    cd duffy
    python setup.py develop

Populate a test database::

    flask db init

Run the duffy server::

    flask run -h <bind_interface> -p <port>

Tests
-----

To run the tests::

    py.test


Production
----------

We don't set `FLASK_DEBUG` in production, otherwise it will send unnecessary
info to duffy clients.

.. code-block:: bash

    unset FLASK_DEBUG

DB Migrations
-------------

The migrations folder is only interesting for CentOS CI instance of duffy at
the moment. See above for populating a database for development purposes

    flask db migrate # generates a migration script
    flask db upgrade # applies the migration script

Authors
-------
Copyright © 2017-2020 Karanbir Singh and `other contributors`

.. _other contributors: https://github.com/CentOS/AUTHORS.txt
