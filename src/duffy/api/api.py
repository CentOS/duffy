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

from hashlib import sha256
from json import dumps
from time import time

from flask import (
    Flask,
    abort,
    redirect,
    request,
)


duffy_api = Flask(__name__)


@duffy_api.get("/")
def index():
    return "Index route"


@duffy_api.get("/api/v2/node")
@duffy_api.post("/api/v2/node")
@duffy_api.put("/api/v2/node")
@duffy_api.delete("/api/v2/node")
def api_node():
    """
    this is what black compliant code looks like kids!
    """
    if request.method == "GET":
        """
        GET method
        """
        apikey = request.args.get("apikey")
        if apikey == "letmein":
            return dumps({"msg": "authorised"})
        return dumps({"msg": "unauthorised"})
    elif request.method == "POST":
        """
        POST method
        """
        apikey = request.form["apikey"]
        if apikey == "letmein":
            return dumps({"msg": "authorised"})
        return dumps({"msg": "unauthorised"})
    elif request.method == "PUT":
        """
        PUT method
        """
        apikey = request.form["apikey"]
        if apikey == "letmein":
            return dumps({"msg": "authorised"})
        return dumps({"msg": "unauthorised"})
    elif request.method == "DELETE":
        """
        DELETE method
        """
        apikey = request.form["apikey"]
        if apikey == "letmein":
            return dumps({"msg": "authorised"})
        return dumps({"msg": "unauthorised"})
    else:
        """
        MISC method
        """
        return dumps({"msg": "bad method"})


@duffy_api.errorhandler(404)
def e404page(ertx):
    print(ertx)
    return "404 Error", 404


@duffy_api.errorhandler(403)
def e403page(ertx):
    print(ertx)
    return "403 Error", 403


@duffy_api.errorhandler(500)
def e500page(ertx):
    print(ertx)
    return "500 Error", 500
