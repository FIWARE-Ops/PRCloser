![FIWARE Banner](https://nexus.lab.fiware.org/content/images/fiware-logo1.png)

# GitHub Pull Request Closer
[![Docker badge](https://img.shields.io/docker/pulls/fiware/service.prcloser.svg)](https://hub.docker.com/r/fiware/service.prcloser/)
[![Build Status](https://travis-ci.org/FIWARE-Ops/PRCloser.svg?branch=master)](https://travis-ci.org/FIWARE-Ops/PRCloser)

## Overview
This project is part of [FIWARE](https://fiware.org) OPS infrastructure.
It automatically add comment with defined message and close open pull request in GitHub repositories.
It works as a service and can receive GitHub notifications as well as direct requests.

## How to run
```console
$ docker run -e TOKEN=${TOKEN} \
             -p 0.0.0.0:8080:8080 \
             fiware/service.prcloser \
             --ip 0.0.0.0 \
             --port ${PORT} \
             --config ${PATH_TO_CONFIG}  
```
```console
$ curl http://localhost:8080/ping
```
## How to configure
+ To comment and close PR at GitHub, you should provide a valid token with an environment variable TOKEN.
+ Sample config is located [here](./config-example.json). 

## How to use
Ping
```console
$ curl http://localhost:8080/ping
```
Get version
```console
$ curl http://localhost:8080/version
```
Check opened PR
```console
$ curl http://localhost:8080/check
```

## GitHub integration
This project works as an endpoint and it should receive notifications from GitHub, so you should configure the webhook in the GitHub repository:
* application/json
* only pull_request event
* no secrets
