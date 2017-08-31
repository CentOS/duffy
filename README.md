# duffy2

Duffy is the provisioning and instance management tool for https://ci.centos.org/

At its core is a simple api hander, backed by a low latency request queue, and execution workers that implement domain specific tasks. Each component can scale independantly.

## Contributing 

Come join us at https://lists.centos.org/mailman/listinfo/ci-users 
Feature stories are being tracked at https://bugs.centos.org/ 
Breakdown from the feature stores, and user issues are tracked on this github repo

## Code Flow

The expectation is that the Master branch represents the deployed codebase, always. Noone is allowed to break Master at anypoint. All code must come via a PR, each PR must be validated before its merged, upon merge, the code is built and deployed in realtime. There are no version releases, we only track the present state, as a service. History is mapped back via git commit hash's ( use the short form, 8 char as references )

## CI and testing

As much as possible, contributions should come with CI tests and acceptance tests. The aim is to use Jenkinsfiles based pipelines that can auto deploy on success.

## Developer env bringup

On a CentOS Linux 7/x86_64 VM or machine :

```
yum -y install centos-release-openshift-origin
yum -y install origin-clients
oc cluster up
oc new-project duffy-dev
bash cico_build.sh
oc apply -f _OPENSHIFT.yaml
```
