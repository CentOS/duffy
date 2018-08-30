# -*- coding: utf-8 -*-
import setuptools

setuptools.setup(
    name='duffy',
    description='',
    packages=setuptools.find_packages(),
    include_package_data=True,
    license='Apache 2.0',
    version='2.0.1'

    install_requires=[
        'flask',
        'flask-sqlalchemy',
        'flask-migrate',
        'flask-marshmallow',
        'marshmallow-sqlalchemy',
        'marshmallow==3.0.0b6',
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
