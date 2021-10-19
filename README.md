## Info
Community Platform Engineering team (of Red Hat) is working on revamping this project and thus, have cleaned this repository by
* marking other branches stale
* Clean branch created for development

to see the current deployed version of Duffy in CentOS CI Infra, check stale/master branch.


## Duffy
Duffy is the middle layer running ci.centos.org that manages the provisioning, maintenance and teardown / rebuild of the Nodes (physical hardware for now, VMs coming soon) that are used to run the tests in the CI Cluster.

## Installation
To install Duffy:
* Clone the repository.
* Install using Poetry: `poetry install`
