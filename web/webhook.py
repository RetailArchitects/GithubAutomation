from flask import Flask, request, g
from flask_pymongo import PyMongo

from github import Github

from slackclient import SlackClient

import requests

import os
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'changemenow')

mongo_uri = os.environ.get('MONGODB_URI', None)
if mongo_uri:
  app.config['MONGO_URI'] = mongo_uri
else:
  app.config['MONGO_HOST'] = os.environ.get('MONGO_HOST','ragithub_db_1')  
mongo = PyMongo(app)

ZENHUB_API_TOKEN = os.environ['ZENHUB_API_TOKEN']
ZENHUB_ROOT_URL = "https://api.zenhub.io"

sc = SlackClient(os.environ['SLACK_TOKEN'])

gh = Github(os.environ['GITHUB_USER'], os.environ['GITHUB_PASSWORD'])

class MilestoneException(Exception):
  
  def __init__(self, msg):
    super(MilestoneException, self).__init__(msg)
    self.unset_milestone = False

class MilestoneViolation(MilestoneException):

  def __init__(self, msg):
    super(MilestoneViolation, self).__init__(msg)
    self.unset_milestone = True

class MilestoneWarning(MilestoneException):
  pass

@app.before_first_request
def setup_config():
  slack_user_list = sc.api_call(
    "users.list",
    presence=False
  )

  def get_slack_user(username):
    for user in slack_user_list['members']:
      if user['name'] == username:
        return user
    return None

  users = [
    {
      "github_user": "cabriley",
      "slack_user": "cal",
      "slack_user_id": ""
    },
    {
      "github_user": "cshipani",
      "slack_user": "",
      "slack_user_id": ""
    },
    {
      "github_user": "dsj999",
      "slack_user": "sjohnson",
      "slack_user_id": ""
    },
    {
      "github_user": "jkb-air",
      "slack_user": "jbower",
      "slack_user_id": ""
    },
    {
      "github_user": "kbower",
      "slack_user": "",
      "slack_user_id": ""
    },
    {
      "github_user": "mspisars",
      "slack_user": "mpisarski",
      "slack_user_id": ""
    },
    {
      "github_user": "narenpai",
      "slack_user": "npai",
      "slack_user_id": ""
    },
    {
      "github_user": "robneville73",
      "slack_user": "rneville",
      "slack_user_id": ""
    },
    {
      "github_user": "samshah7",
      "slack_user": "ss",
      "slack_user_id": ""
    },
    {
      "github_user": "smithadifd",
      "slack_user": "as",
      "slack_user_id": ""
    }
  ]

  for user in users:
    slack_user = get_slack_user(user['slack_user'])
    if slack_user:
      user['slack_user_id'] = slack_user['id']

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
        'robneville73',
      ],
      "github_slack_users": users
    }, True
  )

@app.before_request
def get_config():
  g.config = mongo.db.config.find_one()

def get_slack_id_from_github_username(username):
  for user in g.config['github_slack_users']:
    if user['github_user'] == username:
      return user['slack_user_id']
  return None

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

def get_github_repo():
  return gh.get_repo(g.config['repository_name'])

def get_github_milestone(repo, milestone_title):
  milestones = [m for m in repo.get_milestones() if m.title == milestone_title]
  if len(milestones) > 1 or len(milestones) == 0:
    raise KeyError("Error retrieving milestone with title of %s" % milestone_title)
  return milestones[0]

def check_issue_has_estimate(zenhub_issue):
  app.logger.info(zenhub_issue)
  if not zenhub_issue.get('estimate', False):
    raise MilestoneViolation("Must have an estimate to be added to active milestone")

def check_issue_has_asignee(issue):
  if not issue.assignee:
    raise MilestoneViolation("Must be assigned before it can be scheduled in a milestone.")

def check_issue_has_valid_label(issue):
  accepted_labels = g.config['accepted_labels']
  if len(set([l.name for l in issue.labels]).intersection(set(accepted_labels))) == 0:
    raise MilestoneViolation("To be scheduled, must have one of the following labels: " + ", ".join(accepted_labels))

def get_milestone_zenhub_issues(gh_issues_list):
  retval = []
  for issue in gh_issues_list:
    zenhub_issue = get_zenhub_issue(g.config['repo_id'], issue.number)
    retval.append(zenhub_issue)
  return retval

def get_milestone_sp():
  repo = get_github_repo()
  active_milestone = g.config['active_release']['name']
  milestone = get_github_milestone(repo, active_milestone)
  milestone_issues = repo.get_issues(milestone=milestone)
  zenhub_issues = get_milestone_zenhub_issues(milestone_issues)

  sp_total = sum(int(zi['estimate']['value']) for zi in zenhub_issues)

  return sp_total

def resolve_zenhub_stupid_username(username):
  #zenhub events very very stupidly (and delightlfully uselessly) tag the event
  #with the _full text_ user name (e.g. "Joe Blow") as opposed to the github username
  #::sigh::
  repo = get_github_repo()
  repo_users = repo.get_assignees()
  for user in repo_users:
    if username == user.name:
      return user.login
    elif username == user.login:
      return user.login
    elif username == user.id:
      return user.login
  return None

def check_issue_within_targets(zenhub_issue):
  app.logger.info("in check_issue_within_targets")
  sp_total = get_milestone_sp()
  
  current_sp = zenhub_issue['estimate']['value']
  target_sp = g.config['active_release']['sp_target']
  app.logger.info("total_sp = {total} and current_sp = {current} and target_sp = {target}".format(current=current_sp, target=target_sp, total=sp_total))
  if sp_total > target_sp:
    raise MilestoneViolation("Need to remove %r points in order to add this to release" % (sp_total - target_sp))
  
def check_issue_ok_to_change_estimate(issue, zenhub_issue):
  if issue.state == 'closed' and issue.milestone.title == g.config['active_release']['name']:
    raise MilestoneWarning("Please don't change estimates on closed tickets")
  
def notify_error(issue, message, username, unset_milestone=None):
  app.logger.info("here")
  unset_milestone = unset_milestone if unset_milestone else True
  if unset_milestone:
    issue.edit(milestone=None)
  
  slack_user_id = get_slack_id_from_github_username(username)
  if slack_user_id:
    sc.api_call(
      "chat.postMessage",
      channel=slack_user_id,
      text=message
    )
  
@app.route('/zenhub_webhook', methods=['POST'])
def zenhub_event():
  event = request.form
  event_type = event['type']

  gh_username = resolve_zenhub_stupid_username(event['user_name'])

  zenhub_issue = get_zenhub_issue(g.config['repo_id'], event['issue_number'])
  repo = get_github_repo()
  app.logger.info(event)
  issue_obj = repo.get_issue(int(event['issue_number']))

  try:
    if event_type == 'estimate_set':
      check_issue_within_targets(zenhub_issue)
      check_issue_ok_to_change_estimate(issue_obj, zenhub_issue)

    elif event_type == 'estimate_cleared':
      check_issue_ok_to_change_estimate(issue_obj, zenhub_issue)
      
    elif event_type == 'issue_transfer':
      app.logger.info('Issue transfered event %r' % event)
  except MilestoneException as e:
    notify_error(issue_obj, e.message, gh_username, e.unset_milestone)

  return "OK"


@app.route('/github_webhook', methods=['POST'])
def on_milestone():
  event = request.get_json()
  user = event['sender']['login']

  if event['action'] == 'milestoned':
    issue_obj = get_github_repo().get_issue(event['issue']['number'])
    zenhub_issue = get_zenhub_issue(g.config['repo_id'], issue_obj.number)

    try:
      check_issue_has_estimate(zenhub_issue)
      check_issue_has_asignee(issue_obj)
      check_issue_has_valid_label(issue_obj)
      check_issue_within_targets(zenhub_issue)
    except MilestoneException as e:
      notify_error(issue_obj, e.message, user, e.unset_milestone)

  return "OK"

if __name__ == '__main__':
  app.run(debug=True, host='0.0.0.0')
