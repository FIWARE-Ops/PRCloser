#!/usr/bin/python3
# -*- coding: utf-8 -*-

import time
import json as jsn
import socket
import threading
import http.server
import requests
import os
import sys
import datetime
import argparse


def close_pull_request(target, number):
    url = 'https://api.github.com/repos/' + target + '/pulls/' + number + '/reviews?access_token=' + token_github

    data_func = dict()
    data_func['body'] = def_message
    data_func['event'] = 'COMMENT'
    data_func = jsn.dumps(data_func)
    message = dict()
    message['message'] = ''
    message['code'] = 0
    message['cmd'] = 'pull_request'
    message['repo'] = target
    response = requests.post(url, data=data_func, headers={'Content-Type': 'application/json'})
    if response.status_code == 200:
        url = 'https://api.github.com/repos/' + target + '/pulls/' + number + '?access_token=' + token_github

        data_func = dict()
        data_func['state'] = 'closed'
        data_func = jsn.dumps(data_func)

        response = requests.patch(url, data=data_func, headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            reply = {'message': 'PR closed successfully'}
            code = 200
        else:
            reply = {'message': 'PR closing failed'}
            code = 500
    else:
        reply = {'message': 'Comment failed'}
        code = 500
    return reply, code


def parse_request_line(request_line):
    request_line = request_line.split('HTTP')[0].strip()
    method = request_line.split('/')[0].strip()
    cmd = request_line.split('/')[1].strip().split('?')[0]
    param = dict()
    if cmd in ['config']:
        if len(request_line.split('?')) > 1:
            for element in request_line.split('?')[1].split('&'):
                if element.split('=')[0] in ['repo', 'obj', 'token']:
                    param[element.split('=')[0]] = element.split('=')[1]

    if method == 'GET' and cmd in cmd_get_rl:
        return cmd, param

    return False, None


def targets_check():
    result = list()

    for repo in config:
        response = requests.get('https://api.github.com/repos/' + repo + '/pulls?access_token=' + token_github)
        if response.status_code == 200:
            if response.text:
                response = jsn.loads(response.text)
                for i in response:
                    if i['state'] != 'closed':
                        result.append(repo)
        else:
            result.append('GitHub error')

    if len(result) > 0:
        return {'message': 'Test failed', 'repos': result}
    else:
        return False


class Handler(http.server.BaseHTTPRequestHandler):

    def do_POST(self):
        cmd = self.headers.get('X-GitHub-Event')
        gh = self.headers.get('X-GitHub-Delivery')

        if not cmd:
            message = {'message': 'Request not found'}
            self.reply(message, code=404)
            return

        if cmd not in cmd_post:
            message = {'message': 'Request not found'}
            self.reply(message, code=404, cmd=cmd)
            return

        if cmd in cmd_post_hr_ignored:
            message = {'message': 'Request in ignored list'}
            self.reply(message, cmd=cmd)
            return

        if cmd == 'ping':
            message = {'message': 'Pong'}
            self.reply(message, cmd=cmd)
            return

        content_length = int(self.headers.get('content-length'))

        if content_length == 0:
            message = {'message': 'Length Required'}
            self.reply(message, code=411, cmd=cmd)
            return

        body = self.rfile.read(content_length).decode('utf-8')

        try:
            body = jsn.loads(body)
        except ValueError:
            message = {'message': 'Unsupported media type'}
            self.reply(message, code=400, cmd=cmd)
            return

        status = True
        if 'repository' in body:
            if 'full_name' in body['repository']:
                repo = body['repository']['full_name']
            else:
                status = False
        else:
            status = False

        if not status:
            message = {'message': 'Bad request'}
            self.reply(message, code=400, cmd=cmd)
            return

        if repo not in config:
            message = {'message': 'Repo not found'}
            self.reply(message, code=404, cmd=cmd, repo=repo)
            return

        if body['action'] == 'opened':
            message, code = close_pull_request(repo, str(body['number']))
            self.reply(message, code=code, cmd=cmd, repo=repo)
            return
        else:
            message = {'message': 'Pull request ignored, ' + body['action']}
            self.reply(message, cmd=cmd, repo=repo)

    def do_GET(self):
        cmd, param = parse_request_line(self.requestline)
        if not cmd:
            message = {'message': 'Request not found'}
            self.reply(message, code=404)
            return

        if cmd == 'ping':
            message = {'message': 'Pong'}
            self.reply(message, silent=True, cmd=cmd)
            return

        if cmd == 'version':
            message = {'message': version}
            self.reply(message, cmd=cmd)
            return

        if cmd == 'config':
            status = False
            if 'token' in param:
                if param['token'] == token:
                    message = {'message': config}
                    self.reply(message, cmd=cmd)
                else:
                    status = True
            else:
                status = True

            if status:
                message = {'message': 'Access denied'}
                self.reply(message, code=401, cmd=cmd)
            return

        if cmd == 'check':
            message = targets_check()
            if message:
                self.reply(message, code=500, cmd=cmd)
            else:
                self.reply({'message': 'Test passed'}, cmd=cmd)
            return

    def log_message(self, format, *args):
        return

    def reply(self, message=None, silent=False, code=200, cmd=None, repo=None):
        self.send_response(code)
        self.send_header('content-type', 'application/json')
        self.end_headers()
        self.wfile.write(bytes(jsn.dumps(message, indent=2) + '\n', 'utf8'))

        if not silent:
            message['code'] = code
            if self.headers.get('X-Real-IP'):
                message['ip'] = self.headers.get('X-Real-IP')
            else:
                message['ip'] = self.client_address[0]
            message['request'] = self.requestline
            message['date'] = datetime.datetime.now().isoformat()
            if cmd:
                message['cmd'] = cmd
            if repo:
                message['repo'] = repo
            if self.headers.get('X-GitHub-Delivery'):
                message['gh'] = self.headers.get('X-GitHub-Delivery')
            print(jsn.dumps(message, indent=2))
        return


class Thread(threading.Thread):
    def __init__(self, i):
        threading.Thread.__init__(self)
        self.i = i
        self.daemon = True
        self.start()

    def run(self):
        httpd = http.server.HTTPServer(address, Handler, False)

        httpd.socket = sock
        httpd.server_bind = self.server_close = lambda self: None

        httpd.serve_forever()


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', dest="ip", default='0.0.0.0', help='ip address (default: 0.0.0.0)', action="store")
    parser.add_argument('--port', dest="port", default=8000, help='port (default: 8000)', action="store")
    parser.add_argument('--config', dest='config_path', default='/opt/config.json',
                        help='path to config file (default: /opt/config.json)',  action="store")
    parser.add_argument('--user', dest='user', default='fw-ops', help='github user (default: fw-ops)',
                        action="store")
    parser.add_argument('--email', dest='email', default='fiware.bot@gmail.com',
                        help='github user (default: fiware.bot@gmail.com)',
                        action="store")
    parser.add_argument('--threads', dest='threads', default=2, help='threads to start (default: 2)',
                        action="store")
    parser.add_argument('--socks', dest='socks', default=1, help='threads to start (default: 1)',  action="store")

    args = parser.parse_args()

    user = args.user
    email = args.email
    config_path = args.config_path

    address = (args.ip, args.port)
    version_path = os.path.split(os.path.abspath(__file__))[0] + '/version'

    cmd_get_rl = ['ping', 'config', 'version', 'check']
    cmd_post_hr = ['ping', 'pull_request']
    cmd_post_hr_ignored = ['check_run', 'check_suite', 'commit_comment', 'deployment', 'deployment_status', 'status',
                           'gollum', 'installation', 'installation_repositories', 'issue_comment', 'issues', 'label',
                           'marketplace_purchase', 'member', 'membership', 'milestone', 'organization', 'org_block',
                           'page_build', 'project_card', 'project_column', 'project', 'public', 'push', 'fork',
                           'pull_request_review_comment', 'pull_request_review', 'repository', 'watch', 'team_add',
                           'repository_vulnerability_alert', 'team', 'create', 'delete', 'release']
    cmd_post = cmd_post_hr + cmd_post_hr_ignored

    if 'TOKEN_GITHUB' in os.environ:
        token_github = os.environ['TOKEN_GITHUB']
    else:
        print(jsn.dumps({'message': 'TOKEN_GITHUB not found', 'code': 500, 'cmd': 'start'}, indent=2))
        token_github = None
        sys.exit(1)

    if 'TOKEN' in os.environ:
        token = os.environ['TOKEN']
    else:
        print(jsn.dumps({'message': 'TOKEN not found', 'code': 404, 'cmd': 'start'}, indent=2))
        token = None

    if not os.path.isfile(config_path):
        print(jsn.dumps({'message': 'Config file not found', 'code': 500, 'cmd': 'start'}, indent=2))
        config_file = None
        sys.exit(1)
    try:
        with open(config_path) as f:
            cfg = jsn.load(f)
    except ValueError:
        print(jsn.dumps({'message': 'Unsupported config type', 'code': 500, 'cmd': 'start'}, indent=2))
        sys.exit(1)

    print(jsn.dumps({'message': 'Loading config', 'code': 200, 'cmd': 'start'}, indent=2))

    config = list()
    try:
        def_message = cfg['message']
        config = cfg['repositories']
    except KeyError:
        print(jsn.dumps({'message': 'Config is not correct', 'code': 500, 'cmd': 'start'}, indent=2))
        sys.exit(1)

    if len(config) == 0:
        print(jsn.dumps({'message': 'Repositories list is empty', 'code': 500, 'cmd': 'start'}, indent=2))
        sys.exit(1)

    version = dict()
    if not os.path.isfile(version_path):
        print(jsn.dumps({'message': 'Version file not found', 'code': 500, 'cmd': 'start'}, indent=2))
        version_file = None
        sys.exit(1)
    try:
        with open(version_path) as f:
            version_file = f.read().split('\n')
            version['build'] = version_file[0]
            version['commit'] = version_file[1]
    except IndexError:
        print(jsn.dumps({'message': 'Unsupported version file type', 'code': 500, 'cmd': 'start'}, indent=2))
        sys.exit(1)

    event = threading.BoundedSemaphore(1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(address)
    sock.listen(args.socks)

    [Thread(i) for i in range(args.threads)]

    print(jsn.dumps({'message': 'Service started', 'code': 200}, indent=2))

    while True:
        time.sleep(9999)
