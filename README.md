## Info
Community Platform Engineering team (of Red Hat) is working on revamping this project and thus, have cleaned this repository by
* marking other branches stale
* Clean branch created for development

to see the current deployed version of Duffy in CentOS CI Infra, check stale/master branch.


## Duffy
Duffy is the middle layer running ci.centos.org that manages the provisioning, maintenance and teardown / rebuild of the Nodes (physical hardware for now, VMs coming soon) that are used to run the tests in the CI Cluster.

## Development

### Installation
To install Duffy:
1. Clone the repository and navigate into the project directory.
   ```
   git clone https://github.com/CentOS/duffy.git
   cd duffy
   ```
2. Set up and activate a virtual environment.
   * Using native virtual environment
     ```
     python3 -m venv duffyenv
     source duffyenv/bin/activate
     ```
   Or
   * Using virtualenv wrapper
     ```
     virtualenv duffyenv
     source duffyenv/bin/activate
     ```
   Or
   * Using Poetry virtual environment shell
     ```
     poetry shell
     ```
3. Install using Poetry
   ```
   poetry install
   ```

### Running Duffy server

#### Viewing CLI usage

```
duffy --help
```

```
Usage: duffy [OPTIONS]

  Duffy is the middle layer running ci.centos.org that manages the
  provisioning, maintenance and teardown / rebuild of the Nodes (physical
  hardware for now, VMs coming soon) that are used to run the tests in the CI
  Cluster.

Options:
  -p, --portnumb INTEGER          Set the port value [0-65536]
  -6, --ipv6                      Start the server on an IPv6 address
  -4, --ipv4                      Start the server on an IPv4 address
  -l, --loglevel [critical|error|warning|info|debug|trace]
                                  Set the log level
  --version                       Show the version and exit.
  --help                          Show this message and exit.
```

#### Starting the server at port 8080 using IP version 4 and setting the log level to `trace`

```
duffy -p 8000 -4 -l trace
```

```
 * Starting Duffy...
 * Port number : 8000
 * IP version  : 4
 * Log level   : trace
INFO:     Started server process [104283]
INFO:     Waiting for application startup.
TRACE:    ASGI [1] Started scope={'type': 'lifespan', 'asgi': {'version': '3.0', 'spec_version': '2.0'}}
TRACE:    ASGI [1] Receive {'type': 'lifespan.startup'}
TRACE:    ASGI [1] Send {'type': 'lifespan.startup.complete'}
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Exit out of the server using `Ctrl` + `C`
