# Machine Types

The key operating model for ci.centos.org is to host 'nodes' that are used as places for the tests to run, for the job to get executed on. These nodes can be one or many of a different kind, eg: bare metal or cloud nodes etc. These are the basic nodes we support at the moment:

* metal: Bare Metal ( default )
* cloud: Cloud Nodes, VMss run in cloud.ci.centos.org ( RDO Install )
* virt: LibVirt Nodes, VM's hosted using LibVirt, typically used on platforms RDO isnt viable on or for custom installs.

Wherever possible, the experience should be retained to be consistent and predictable ( eg. the cloud nodes resource allocation should match the libvirt hosted ones, for the same flavour name )

## Common attribs across all types

For each node, we need to maintain the following attributes for each node, regardless of its type:

* distro: The Distrobution name, defaults to CentOS
* arch: The base archetecture, should map to 'uname -p', defaults to x86_64
* rel: Any release tag or version eg. 7.1708
* ipaddr: the IP address for the specific node

## metal

We dont need any specific information for bare metal nodes beyond the common attributes

## cloud

For cloud nodes, we need to maintain the following extra information:

* flavour: the machine flavour type. The flavours are mapped to fixed resources, the present allocation is:

flavour | cpu | ram | disk | notes
--- | --- | --- | --- | ---
tine | 0.5 | 2 GB | 8 GB | -
small | 1 | 4 GB | 8 GB | -
large | 2 | 8 GB | 8 GB | -

Note: at this point the disk sizes are fixed.

## virt

For libvirt hosted nodes, we need the following in addition to the common attribs:

* host: address for the host machine where the libvirt instance is running
* flavour: the machine flavour type. The flavours are mapped to fixed resources, the present allocation is:

flavour | cpu | ram | disk | notes
--- | --- | --- | --- | ---
tine | 0.5 | 2 GB | 8 GB | -
small | 1 | 4 GB | 8 GB | -
large | 2 | 8 GB | 8 GB | -
