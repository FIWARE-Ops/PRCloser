#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from aiohttp import web, ClientSession, ClientConnectorError
from argparse import ArgumentParser
from asyncio import TimeoutError, set_event_loop_policy
from logging import error, getLogger
from os import path, environ
from uvloop import EventLoopPolicy
from yajl import dumps, loads

api_url = 'https://api.github.com/repos/'
config = dict()
header = {'Content-Type': 'application/json'}
version = dict()
routes = web.RouteTableDef()

cmd_ignored = ['check_run', 'check_suite', 'commit_comment', 'deployment', 'deployment_status', 'status', 'gollum',
               'installation', 'installation_repositories', 'issue_comment', 'issues', 'label', 'marketplace_purchase',
               'member', 'membership', 'milestone', 'organization', 'org_block', 'page_build', 'project_card', 'team',
               'project_column', 'project', 'public', 'push', 'fork', 'pull_request_review_comment', 'create', 'delete',
               'pull_request_review', 'repository', 'watch', 'team_add', 'repository_vulnerability_alert', 'release']

cmd_accepted = ['pull_request']


@routes.get('/check')
async def get_handler(request):
    result = list()

    async with ClientSession() as session:
        for repository in config['repositories']:
            url = api_url + repository + '/pulls?access_token=' + token

            try:
                async with session.get(url) as response:
                    status = response.status
                    text = loads(await response.text())
            except ClientConnectorError:
                web.Response(text='Checking' + repository + 'failed due to the connection problem\n', status=502)
            except TimeoutError:
                web.Response(text='Checking' + repository + 'failed due to the timeout\n', status=504)
            except Exception as exception:
                error('check, %s', exception)
                return web.HTTPInternalServerError()

            if status != 200:
                return web.Response(text='Checking' + repository + 'failed due to the: ' + text['message'] + '\n',
                                    status = status)

            for item in text:
                if item['state'] != 'closed':
                    result.append(repository)

    if len(result) > 0:
        return web.Response(text=dumps({'message': 'Test failed', 'repositories': result}, indent=4))
    else:
        return web.HTTPOk()


@routes.get('/ping')
async def get_handler(request):
    return web.Response(text = 'pong\n')


@routes.get('/version')
async def get_handler(request):
    return web.Response(text=version)


@routes.post('/')
async def get_handler(request):
    try:
        event = request.headers['X-GitHub-Event']
    except KeyError:
        error('Bad request, %s', request.headers)
        return web.HTTPBadRequest()

    if event == 'ping':
        return web.Response(text='pong\n')

    if event in cmd_ignored:
        return web.Response(text='event in the ignored list\n')

    if event not in cmd_accepted:
        error('Unknown event, %s', event)
        return web.Response(text="Unknown event" + event + '\n', status=400)

    data = (await request.read()).decode('UTF-8')

    try:
        data = loads(data)
    except ValueError:
        error('Bad request, %s', data)
        return web.HTTPBadRequest()

    try:
        repository = data['repository']['full_name']
        action = data['action']
        number = data['number']
    except ValueError:
        error('Bad request, %s', data)
        return web.HTTPBadRequest()

    if not repository or repository not in config['repositories']:
        return web.Response(text='Repository not found in the config, or not defined\n', status=404)

    if not action or action not in ['opened', 'reopened']:
        return web.HTTPOk()

    async with ClientSession() as session:
        data = {'body': config['message'],
                'event': 'COMMENT'}
        url = api_url + repository + '/pulls/' + str(number) + '/reviews?access_token=' + token
        try:
            async with session.post(url, data=dumps(data), headers=header) as response:
                status = response.status
                text = loads(await response.text())
        except ClientConnectorError:
            web.Response(text='Adding comment failed due to the connection problem\n', status=502)
        except TimeoutError:
            web.Response(text='Adding comment request failed due to the timeout\n', status=504)
        except Exception as exception:
            error('close_pull_request, %s', exception)
            return web.HTTPInternalServerError()

        if status != 200:
            return web.Response(text="Adding comment failed due to the: " + text['message'] + '\n', status = status)

        data = {'state': 'closed'}
        url = api_url + repository + '/pulls/' + str(number) + '?access_token=' + token
        try:
            async with session.post(url, data=dumps(data), headers=header) as response:
                status = response.status
                text = loads(await response.text())
        except ClientConnectorError:
            web.Response(text='Closing PR failed due to the connection problem\n', status=502)
        except TimeoutError:
            web.Response(text='Closing PR request failed due to the timeout\n', status=504)
        except Exception as exception:
            error('close_pull_request, %s', exception)
            return web.HTTPInternalServerError()

        if status != 200:
            return web.Response(text="Closing PR failed due to the: " + text['message'] + '\n', status = status)

    return web.HTTPOk()


if __name__ == '__main__':

    parser = ArgumentParser()
    parser.add_argument('--ip', default='0.0.0.0', help='ip to use, default is 0.0.0.0')
    parser.add_argument('--port', default=8080, help='port to use, default is 8080')
    parser.add_argument('--config', default='/opt/config.json', help='path to config file, default is /opt/config.json')

    args = parser.parse_args()

    getLogger().setLevel(40)
    set_event_loop_policy(EventLoopPolicy())

    if 'TOKEN' in environ:
        token = environ['TOKEN']
    else:
        error('TOKEN not provided in the Env')
        exit(1)

    version_path = './version'
    if not path.isfile(version_path):
        error('Version file not found')
        exit(1)
    try:
        with open(version_path) as f:
            version_file = f.read().split('\n')
            version['build'] = version_file[0]
            version['commit'] = version_file[1]
            version = dumps(version, indent=4)
    except IndexError:
        error('Unsupported version file type')
        exit(1)

    if not path.isfile(args.config):
        error('Config file not found')
        exit(1)
    try:
        with open(args.config) as file:
            config = loads(file.read())
    except ValueError:
        error('Unsupported config type')
        exit(1)

    if len(config['repositories']) == 0:
        error('Repository list is empty')
        exit(1)

    if 'message' not in config:
        error('Message not exists in config')
        exit(1)

    app = web.Application()
    app.add_routes(routes)
    web.run_app(app, host=args.ip, port=args.port)
