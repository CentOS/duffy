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

    export FLASK_APP=run.py
    export FLASK_DEBUG=1

Clone the duffy2 repo::

    git clone https://github.com/CentOS/duffy
    cd duffy2
    python setup.py develop
    flask run

To populate the database::

    flask db migrate
    flask db upgrade
    flask run

Tests
-----

To run the tests::

    flask test

DB Migrations
-------------

To migrate a database after a change has been made run the following::

    flask db migrate # generates a migration script
    flask db upgrade # applies the migration script

Authors
-------
Copyright © 2017 Karanbir Singh and `other contributors`

.. _other contributors: https://github.com/CentOS/AUTHORS.txt
