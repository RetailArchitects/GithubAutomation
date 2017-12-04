from flask import Flask
from flask import request
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm.exc import NoResultFound

from github import Github

import requests

import os
import json

users = {}

app = Flask(__name__)
app.config['SECRETY_KEY'] = 'S3cret!!'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://ra:another!@db/github'
db = SQLAlchemy(app)
socketio = SocketIO(app)

class GitHubConfig(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  repo_id = db.Column(db.Integer, nullable=False)

AUTHORIZED_LOGINS = ('robneville73a',)
ACCEPTED_LABELS = set(['Bug', 'Expedite', 'GERS Replacement', 'New', 'Project', 'SOW', 'UX'])
UNAUTHORIZED_MSG = "Can't add issues to active sprint, milestone was unset."

ZENHUB_API_TOKEN = os.environ['ZENHUB_API_TOKEN']
REPO_ID = "112486602"
ZENHUB_ROOT_URL = "https://api.zenhub.io"

gh = Github(os.environ['GITHUB_USER'], os.environ['GITHUB_PASSWORD'])
repo = gh.get_repo("RetailArchitects/webhook_testing")

def get_config_record():
  return GitHubConfig.query.one()

@app.route('/setup_db/<repo_id>')
def setup_db(repo_id):
  db.create_all()
  config = None
  try:
    config = get_config_record()
  except NoResultFound:
    config = GitHubConfig()
    config.repo_id = int(repo_id)
    db.session.add(config)
    db.session.commit()
  finally:
    app.logger.info(config.repo_id)
    return "OK"

@app.route('/github_webhook', methods=['POST'])
def on_milestone():
  event = request.get_json()
  action = event['action']
  repo_id = str(get_config_record().repo_id)
  if action == 'milestoned':
    allowed = True
    message = None
    authorized = event['sender']['login'] in AUTHORIZED_LOGINS
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
    elif len(set([l.name for l in issue_obj.labels]).intersection(ACCEPTED_LABELS)) == 0:
      allowed = False
      message = "To be scheduled, must have one of the following labels: " + ", ".join(list(ACCEPTED_LABELS))
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
  app.logger.info(data['gh_user'])
  users[data['gh_user']] = request.sid


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

if __name__ == '__main__':
  socketio.run(app, debug=True, host='0.0.0.0')
