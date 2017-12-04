from flask import Flask, request
from flask_socketio import SocketIO
from flask_pymongo import PyMongo

from github import Github

import requests

import os
import json

users = {}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'changemenow')
app.config['MONGO_HOST'] = os.environ.get('MONGO_HOST','ragithub_db_1')
mongo = PyMongo(app)
socketio = SocketIO(app)

UNAUTHORIZED_MSG = "Can't add issues to active sprint, milestone was unset."

ZENHUB_API_TOKEN = os.environ['ZENHUB_API_TOKEN']
ZENHUB_ROOT_URL = "https://api.zenhub.io"

gh = Github(os.environ['GITHUB_USER'], os.environ['GITHUB_PASSWORD'])

@app.before_first_request
def setup_config():
  repo_id = os.environ['DEFAULT_REPO_ID']
  repo_name = os.environ['DEFAULT_REPO_NAME']
  mongo.db.config.replace_one(
    {
      "repo_id": repo_id
    },
    {
      "repo_id": repo_id,
      "repository_name": repo_name,
      "active_release": {
        "name": "release1.0",
        "sp_target": 5
      },
      "accepted_labels": [
        'Bug', 'Expedite', 'GERS Replacement', 'New', 'Project', 'SOW', 'UX'
      ],
      "authorized_logins": [
        'robneville73a',
      ]
    }, True
  )

def get_zenhub_issue(repo_id, issue_id):
  url = '{root}/p1/repositories/{repo}/issues/{issue_number}'.format(
    root=ZENHUB_ROOT_URL,
    repo=repo_id,
    issue_number=issue_id
  )
  headers = {
    'X-Authentication-Token': ZENHUB_API_TOKEN
  }
  response = requests.get(url, headers=headers)
  return response.json()

@app.route('/github_webhook', methods=['POST'])
def on_milestone():
  event = request.get_json()
  config = mongo.db.config.find_one()
  repo = gh.get_repo(config['repository_name'])
  action = event['action']
  repo_id = config['repo_id']
  
  if action == 'milestoned':
    allowed = True
    message = None
    authorized = event['sender']['login'] in config['authorized_logins']
    accepted_labels = config['accepted_labels']
    issue = event['issue']
    issue_obj = repo.get_issue(issue['number'])
    status = issue['milestone']['description']
    
    zenhub_issue = get_zenhub_issue(repo_id, issue_obj.number)
    
    if not zenhub_issue.get('estimate', False):
      allowed = False
      message = "Must have an estimate to be added to active milestone"
    # {u'pipeline': {u'name': u'New Issues'}, u'estimate': {u'value': 1}, u'plus_ones': [], u'is_epic': False}
    elif not issue_obj.assignee:
      allowed = False
      message = "Must be assigned before it can be scheduled in a milestone."
    elif len(set([l.name for l in issue_obj.labels]).intersection(set(accepted_labels))) == 0:
      allowed = False
      message = "To be scheduled, must have one of the following labels: " + ", ".join(accepted_labels)
    elif status == 'active' and not authorized:
      allowed = False
      message = "You don't have authority to add issues to active milestone"

    if not allowed:
      issue_obj.edit(milestone=None)
      sid = users.get(event['sender']['login'], None)
      if sid:
        msg = {
          'title': 'Milestone Disallowed',
          'message': message
        }
        socketio.emit('display-notification', msg, room=sid)

  return "OK"

@socketio.on('store-client-data')
def associate_user(data):
  browser_plugin_user = data.get('gh_user')
  if browser_plugin_user:
    users[browser_plugin_user] = request.sid

if __name__ == '__main__':
  socketio.run(app, debug=True, host='0.0.0.0')
