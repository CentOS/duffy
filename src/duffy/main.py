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

import click


try:
    # Running the installation when built using setuptools
    from duffy.__init__ import __version__ as duffy_version
    from duffy.api.api import duffy_api
except Exception:
    # Running the installation from a development environment or Docker image
    from __init__ import __version__ as duffy_version
    from api.api import duffy_api


@click.command()
@click.option("-p", "--portdata", "portdata", help="Set the port value [0-65536]", default="9696")
@click.version_option(version=duffy_version, prog_name=click.style("CentOS/Duffy", fg="magenta"))
def uptownfunc(portdata):
    """
    Uptownfunc gonna give Duffy to ya
    """
    duffy_api.run(port=portdata, host="0.0.0.0")


if __name__ == "__main__":
    uptownfunc()
