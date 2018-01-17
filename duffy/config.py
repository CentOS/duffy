# -*- coding: utf-8 -*-
""" Duffy2 configuration. """
import os


class Config(object):
    SECRET_KEY = os.environ.get('DUFFY2_SECRET', 'OMGREALLYSEKRIT')
    APP_DIR = os.path.abspath(os.path.dirname(__file__))
    ROOT = os.path.abspath(os.path.join(APP_DIR, os.pardir))
    DEBUG_TB_ENABLED = False
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class ProdConfig(Config):
    ENV = 'prod'
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = ''
    DEBUG_TB_ENABLED = False


class DevConfig(Config):
    ENV = 'dev'
    DEBUG = True
    DB = 'development.db'
    DB_PATH = os.path.join(Config.ROOT, DB)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///{0}'.format(DB_PATH)


class TestConfig(Config):
    ENV = 'test'
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///'
    BCRYPT_LOG_ROUNDS = 4
    WTF_CSRF_ENABLED = False
