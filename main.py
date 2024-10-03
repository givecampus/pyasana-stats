import os
from datetime import datetime, date, timedelta
from collections import defaultdict

# Import the library
import asana
from asana.rest import ApiException

import click

from termcolor import colored

TOKEN_ENV_VAR = 'ASANA_TOKEN'

# Configure personal access token
configuration = asana.Configuration()
# configuration.access_token = '2/1208085993592881/1208468006795122:f0426c416206b166a5ef6ae9320177ca'
configuration.access_token = os.environ.get(TOKEN_ENV_VAR)
api_client = asana.ApiClient(configuration)

# Construct resource API Instance
users_api_instance = asana.UsersApi(api_client)
user_gid = "me"
opts = {}

# PLATFORM_SPRINT_ID = '1205117034782288' # NOPE
PLATFORM_SPRINT_ID = '1203953156205290'
ESTIMATED_POINTS_GID = '1202399449289965'


@click.command()
@click.option('--completed-since', default=None, help='Filter tasks completed since this date')
@click.option('--project-id', default=PLATFORM_SPRINT_ID, help='Filter tasks for this project id')
def main(completed_since=None, project_id=None):
    tasks_api = asana.TasksApi(api_client)
    if not completed_since:
        # 1 week backwards
        completed_since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00")

    if not project_id:
        project_id = PLATFORM_SPRINT_ID

    tasks = tasks_api.get_tasks_for_project(
        PLATFORM_SPRINT_ID, 
        {
            'opt_fields': 'name,status,completed,completed_by,completed_at,custom_fields,permalink_url',
            'completed': True,
            'completed_since': completed_since
        }
    )
    user_completion_dict = defaultdict(int)
    point_tally = 0
    for x in tasks:
        if x['completed']:
            for cf in x['custom_fields']:
                if cf['gid'] == ESTIMATED_POINTS_GID:
                    try:
                        point = float(cf['enum_value']['name'].split('-')[0].strip())
                        point_tally += point
                    except (KeyError, TypeError):
                        #import ipdb; ipdb.set_trace()
                        print(colored("--- MISSING POINTS ---", 'red'))
                        print(colored(f"Task: {x['name']}, has no points. Go to {x['permalink_url']} to update", 'red'))
                    except ValueError:
                        print(f"Bad point value: {point}")

                    try:
                        completed_by_gid = x['completed_by']['gid']
                        user_completion_dict[completed_by_gid] += point
                    except KeyError:
                        print(f"Task {x['name']} has no completed_by")

    print(f"Total points completed: {point_tally}, since {completed_since}")
    for user_gid, points in user_completion_dict.items():
        user = users_api_instance.get_user(user_gid, opts)
        print(f"{user['name']}: {points}")

if __name__ == "__main__":
    main()