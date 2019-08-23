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


def get_repo_pair_in_config(repo_param):
    for repo in config['repositories']:
        if repo['source'] == repo_param:
            return repo['target']
        if repo['target'] == repo_param:
            return repo['source']

    return False


def close_pull_request(target, number):
    url = 'https://api.github.com/repos/' + target + '/pulls/' + number + '/reviews?access_token=' + token_github

    data_func = dict()
    data_func['body'] = config['message']
    data_func['event'] = 'COMMENT'
    data_func = jsn.dumps(data_func)
    message = dict()
    message['message'] = ''
    message['code'] = 0
    message['cmd'] = 'pull_request'
    message['repo'] = target
    response = requests.post(url, data=data_func, headers={'Content-Type': 'application/json'})
    if response.status_code == 200:
        message['message'] = 'Comment succeeded'
        message['code'] = 200
        print(jsn.dumps(message, indent=2))

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


def targets_check():
    result = list()

    for repo in config['repositories']:
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


class Handler(http.server.BaseHTTPRequestHandler):

    def reply(self, message=dict(), silent=False, code=200, cmd='', repo=''):
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

    def log_message(self, format, *args):
        return

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

        if repo not in config['repositories']:
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
    parser.add_argument('--user', dest='user', default='Fiware-ops', help='github user (default: Fiware-ops)',
                        action="store")
    parser.add_argument('--email', dest='email', default='test@example.com', help='github user (default: test@example.com)',
                        action="store")
    parser.add_argument('--threads', dest='threads', default=0, help='threads to start (default: len(repos)//2 + 3)',
                        action="store")
    parser.add_argument('--socks', dest='socks', default=0, help='threads to start (default: threads)',  action="store")

    args = parser.parse_args()

    ip = args.ip
    port = args.port
    user = args.user
    email = args.email
    threads = args.threads
    socks = args.socks
    config_path = args.config_path

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
            config = jsn.load(f)
    except ValueError:
        print(jsn.dumps({'message': 'Unsupported config type', 'code': 500, 'cmd': 'start'}, indent=2))
        sys.exit(1)

    print(jsn.dumps({'message': 'Checking config', 'code': 200, 'cmd': 'start'}, indent=2))

    if 'repositories' not in config:
        print(jsn.dumps({'message': 'Repositories not defined', 'code': 500, 'cmd': 'start'}, indent=2))
        sys.exit(1)
    elif len(config['repositories']) == 0:
        print(jsn.dumps({'message': 'Repositories list is empty', 'code': 500, 'cmd': 'start'}, indent=2))
        sys.exit(1)
    if 'message' not in config:
        print(jsn.dumps({'message': 'Message not defined', 'code': 500, 'cmd': 'start'}, indent=2))
        sys.exit(1)

    if threads == 0:
        threads = len(config['repositories'])//2 + 3
    if socks == 0:
        socks = threads

    address = (ip, port)

    cmd_get_rl = ['ping', 'config', 'version', 'check']
    cmd_post_hr = ['ping', 'pull_request']
    cmd_post_hr_ignored = ['check_run', 'check_suite', 'commit_comment', 'deployment', 'deployment_status', 'status',
                           'gollum', 'installation', 'installation_repositories', 'issue_comment', 'issues', 'label',
                           'marketplace_purchase', 'member', 'membership', 'milestone', 'organization', 'org_block',
                           'page_build', 'project_card', 'project_column', 'project', 'public', 'push', 'fork',
                           'pull_request_review_comment', 'pull_request_review', 'repository', 'watch', 'team_add',
                           'repository_vulnerability_alert', 'team', 'create', 'delete', 'release']
    cmd_post = cmd_post_hr + cmd_post_hr_ignored

    version_file = open(os.path.split(os.path.abspath(__file__))[0] + '/version').read().split('\n')
    version = dict()
    version['build'] = version_file[0]
    version['commit'] = version_file[1]

    event = threading.BoundedSemaphore(1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(address)
    sock.listen(socks)

    [Thread(i) for i in range(threads)]

    print(jsn.dumps({'message': 'Service started', 'code': 200, 'threads': threads, 'socks': socks}, indent=2))

    while True:
        time.sleep(9999)
