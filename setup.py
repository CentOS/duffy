# -*- coding: utf-8 -*-
import setuptools

setuptools.setup(
    name='duffy',
    description='',
    version='2.0.0',
    packages=setuptools.find_packages(),
    include_package_data=True,
    license='Apache 2.0',

    install_requires=[
        'beanstalkc',
        'flask',
        'flask-marshmallow',
        'flask-migrate',
        'flask-sqlalchemy',
        'marshmallow-sqlalchemy',
        'marshmallow==3.0.0b6',
        'pymysql',
        'paramiko',
    ],

    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Topic :: Utilities",
    ],

    scripts=[],
)
