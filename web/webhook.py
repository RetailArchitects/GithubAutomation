from flask import Flask
from flask import request

from github import Github

import os

app = Flask(__name__)

AUTHORIZED_LOGINS = ('robneville73-a',)

gh = Github(os.environ['GITHUB_USER'], os.environ['GITHUB_PASSWORD'])
repo = gh.get_repo("RetailArchitects/webhook_testing")

@app.route('/github_webhook', methods=['POST'])
def on_milestone():
  event = request.get_json()
  action = event['action']
  if action == 'milestoned':
    authorized = event['sender']['login'] in AUTHORIZED_LOGINS
    issue = event['issue']
    issue_obj = repo.get_issue(issue['number'])
    status = issue['milestone']['description']
    
    if status == 'active' and not authorized:
      issue_obj.edit(milestone=None)
      issue_obj.create_comment("Can't add issues to active sprint, milestone was unset.")

  return "OK"

if __name__ == '__main__':
  app.run(debug=True, host='0.0.0.0')
