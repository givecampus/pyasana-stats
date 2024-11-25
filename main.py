import os
from csv import DictWriter
from datetime import datetime, date, timedelta
from collections import defaultdict

# Import the library
import asana
from asana.rest import ApiException

import click

from termcolor import colored

TOKEN_ENV_VAR = "ASANA_TOKEN"

# Configure personal access token
configuration = asana.Configuration()
#configuration.access_token = (
#    "2/1208085993592881/1208468006795122:f0426c416206b166a5ef6ae9320177ca"
#)
configuration.access_token = os.environ.get(TOKEN_ENV_VAR)
api_client = asana.ApiClient(configuration)

# Construct resource API Instance
users_api_instance = asana.UsersApi(api_client)
user_gid = "me"
opts = {}

# PLATFORM_SPRINT_ID = '1205117034782288' # NOPE
PLATFORM_SPRINT_ID = "1203953156205290"
ESTIMATED_POINTS_GID = "1202399449289965"
SUPPORT_BOARD_ID = "1201157086826331"


@click.command()
@click.option("--support-board", is_flag=True, help="List tasks for the support board")
@click.option("--code-orange", is_flag=True, help="List tasks for Code Orange")
@click.option("--velo-tracking", is_flag=True, help="List tasks for velocity tracking")
@click.option(
    "-p", "--project-id", default=None, help="Filter tasks for this project id"
)
@click.option("-s", "--specific-tasks", is_flag=True, help="List specific tasks")
@click.option("--task-id-file", default=None, help="File with task ids")
@click.option(
    "-c",
    "--completed-since",
    default=None,
    help="Filter tasks completed since this date",
)
def asana_router(
    support_board, code_orange, velo_tracking, project_id, completed_since, specific_tasks, task_id_file
):
    if support_board:
        support_board_stats()
    elif code_orange:
        code_orange_stats()
    elif velo_tracking:
        velocity_tracking(completed_since, project_id)
    elif specific_tasks:
        get_specific_tasks(task_id_file)
    else:
        print("No command specified")


def code_orange_stats():
    tasks_api = asana.TasksApi(api_client)
    TAG_ID = "1208541407042522"
    tasks = tasks_api.get_tasks_for_tag(
        TAG_ID,
        {
            "opt_fields": "name,completed,completed_at,completed_by,permalink_url,assignee.name",
        },
    )
    print("name,completed,completed_at,completed_by,permalink_url,assignee.name")
    for x in tasks:
        assignee = x["assignee"] or {}
        print(
            f"{x['name']},{x['completed']},{x['completed_at']},{x['completed_by']},{x['permalink_url']},{assignee.get("name", "unknown")}"
        )

def get_specific_tasks(task_id_file=None):
    tasks_api = asana.TasksApi(api_client)
    full_task_list = []
    filename = task_id_file or "list_of_ids.txt"
    for id in open(filename):
        if not id:
            continue
        task = tasks_api.get_task(
            id.strip(),
            {
                "opt_fields": "name,completed,created_at,permalink_url,assignee.name,custom_fields",
            },
        )
        task["converted_time"] = datetime.strptime(task["created_at"].split("T")[0], "%Y-%m-%d")
        
        full_task_list.append(task)
    sorted_tasks = sorted(full_task_list, key=lambda x: x["converted_time"])
    oldest_tasks = 0
    old_tasks = 0
    this_year = 0
    print("name,completed,created_at,updated_at,permalink_url,assignee.name")
    for task in sorted_tasks:
        assignee = task["assignee"] or {}
        print(
            f"{task['name']},{task['completed']},{task['created_at']},{task['permalink_url']},{assignee.get("name", "unknown")}"
        )
        if task["converted_time"].year == 2022:
            oldest_tasks += 1
        elif task["converted_time"].year == 2023:
            old_tasks += 1
        else:
            this_year += 1
    
    print(f"Oldest tasks: {oldest_tasks}")
    print(f"Old tasks: {old_tasks}")
    print(f"This year tasks: {this_year}")



def support_board_stats():
    tasks_api = asana.TasksApi(api_client)
    tasks = tasks_api.get_tasks_for_project(
        SUPPORT_BOARD_ID,
        {
            "opt_fields": "name,completed,completed_at,completed_by,permalink_url,assignee.name,custom_fields",
            "completed": True,
            "completed_since": datetime.now().strftime("%Y-%m-%dT00:00:00"),
        },
    )
    print("name,completed,completed_at,completed_by,permalink_url,assignee.name")
    for x in tasks:
        assignee = x["assignee"] or {}
        print(
            f"{x['name']},{x['completed']},{x['completed_at']},{x['completed_by']},{x['permalink_url']},{assignee.get("name", "unknown")}"
        )


@click.option(
    "--completed-since", default=None, help="Filter tasks completed since this date"
)
@click.option(
    "--project-id", default=PLATFORM_SPRINT_ID, help="Filter tasks for this project id"
)
def velocity_tracking(completed_since=None, project_id=None):
    tasks_api = asana.TasksApi(api_client)
    if not completed_since:
        # 1 week backwards
        completed_since = (datetime.now() - timedelta(days=7)).strftime(
            "%Y-%m-%dT00:00:00"
        )

    if not project_id:
        project_id = PLATFORM_SPRINT_ID

    tasks = tasks_api.get_tasks_for_project(
        PLATFORM_SPRINT_ID,
        {
            "opt_fields": "name,status,completed,completed_by,completed_at,custom_fields,permalink_url",
            "completed": True,
            "completed_since": completed_since,
        },
    )
    user_completion_dict = defaultdict(int)
    point_tally = 0
    for x in tasks:
        if x["completed"]:
            for cf in x["custom_fields"]:
                if cf["gid"] == ESTIMATED_POINTS_GID:
                    try:
                        point = float(cf["enum_value"]["name"].split("-")[0].strip())
                        point_tally += point
                    except (KeyError, TypeError):
                        # import ipdb; ipdb.set_trace()
                        print(colored("--- MISSING POINTS ---", "red"))
                        print(
                            colored(
                                f"Task: {x['name']}, has no points. Go to {x['permalink_url']} to update",
                                "red",
                            )
                        )
                    except ValueError:
                        print(f"Bad point value: {point}")

                    try:
                        completed_by_gid = x["completed_by"]["gid"]
                        user_completion_dict[completed_by_gid] += point
                    except KeyError:
                        print(f"Task {x['name']} has no completed_by")

    print(f"Total points completed: {point_tally}, since {completed_since}")
    for user_gid, points in user_completion_dict.items():
        user = users_api_instance.get_user(user_gid, opts)
        print(f"{user['name']}: {points}")


if __name__ == "__main__":
    asana_router()
