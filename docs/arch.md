# Overall Arch

The core of duffy is a beanstalkd instance that is used to handle all requests for provision/destrory. In addition to this a database is used to keep a 'stock' table for each machine type, that can be used by the api service to hand out nodes on demand. The following drawing lays out the basic operating model:

![overview](https://raw.githubusercontent.com/kbsingh/duffy2/master/docs/overview.png)

The service functions like this:

* A cron based inventory script runs for each machine type. It will check the db to ensure the required number of nodes for each distro/arch/rel/ver are available in the 'stock' tables. If the number is below required, it will add a request to the right beanstalkd queue, asking for a new node to be provisioned - at which point a provision worker will take up the job, work through whatever is needed and bring up a new node. Once up, it will update the stock table.
* When a user calls the api service requesting a node, the api service will check the stock table, and allocate the least used node to the user. It will then login to the node, drop in the users ssh key for the root user, and return a json object to the client with the hostname and any other details needed. This node's used_count is incremented. Each allocation is done in a session, with its own ssid
* users can request multiple nodes, all of which must be the same machine type, and will be included in the same ssid, and must be all returned at the same time.
* there is a basic quota system in place, limiting nodes per unit time, total nodes per machine type.
* another cron job runs to check stock, user allocations and ssid init times, and will auto-reap ( by calling the api service ) machine nodes that are over their timeout time period ( ~ 6 hrs ).
* nodes marked as failed, will get twice the timeout time period ( ~ 12 hrs)
* some machine types, eg: Libvirt nodes have no timeout period and will never get auto-reaped, but will count towards the users quota.