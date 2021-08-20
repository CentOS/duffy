"""
   Copyright 2021 CentOS

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

# -*- coding: utf-8 -*-
import setuptools
import codecs
import os.path


# use README.md as readme
def readme():
    with open('README.md') as f:
        return f.read()


# get __version__ from a file
def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


setuptools.setup(
    name='duffy',
    description='',
    version=get_version("src/duffy/__init__.py"),
    long_description=readme(),
    long_description_content_type="text/markdown",
    license='Apache 2.0',
    install_requires=[
        'flask>=2.0.1',
        'flask-migrate>=3.0.1',
        'Flask-SQLAlchemy>=2.5.0',
    ],
    packages=setuptools.find_packages('src'),
    include_package_data=True,
    package_dir={
        '': 'src',
    },
    entry_points={
      'console_scripts': ['duffy=duffy.main:uptownfunc'],
    },
    classifiers=[
      'Development Status :: 4 - Beta',
      'Environment :: Console',
      'License :: OSI Approved :: Apache Software License',
      'Intended Audience :: xxx',
      'Natural Language :: English',
      'Programming Language :: Python :: 3',
      'Operating System :: POSIX :: Linux',
      'Topic :: System :: Software :: System Software',
    ],
    scripts=[],
)
