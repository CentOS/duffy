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
* Clone the repository.
* Install using Poetry: `poetry install`

### Running Duffy using poetry

There are two ways to run the app using the virtual environment poetry manages for you:

```
poetry run uvicorn duffy.app.main:app --reload
```

Or:

```
poetry shell
uvicorn duffy.app.main:app --reload
```

### Running Duffy in an explicitly defined virtual environment

If you create a virtual environment by yourself, poetry will install into this if it's activated. In
this environment, simply run the app like this:

```
uvicorn duffy.app.main:app --reload
```
