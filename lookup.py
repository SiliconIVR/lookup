import os
import pyperclip
import argparse
import requests
import inquirer
import readchar
import time
from dotenv import load_dotenv

CONFIG_DIR = os.path.expanduser("~/.gclookup")
ENV_FILE = os.path.join(CONFIG_DIR, ".env")
GENESYS_CLOUD_REGION = "usw2.pure.cloud"  # default

# ['User by ID', 'User by Name', 'Queue by ID', 'Queue by Name']
QUERY_USERID = "User by ID"
QUERY_USERNAME = "User by Name"
QUERY_QUEUEID = "Queue by ID"
QUERY_QUEUENAME = "Queue by Name"
QUERY_INTERACTION = "Interaction by ID"


# Ensure the config directory exists with correct permissions
try:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)  # Only user can access
except Exception as e:
    print(f"An error occurred: {e}")


def setup_env():
    """Create the .env file in ~/.gclookup if it doesn’t exist."""
    if not os.path.exists(ENV_FILE):
        region = (
            input("Enter your region [usw2.pure.cloud]: ").strip() or "usw2.pure.cloud"
        )

        if not region:
            region = "usw2.pure.cloud"
        client_id = input("Enter your CLIENT_ID: ").strip()
        client_secret = input("Enter your CLIENT_SECRET: ").strip()
        if not client_secret:
            print("CLIENT_SECRET cannot be empty.")
            return

        # Store the secrets in the .env file (plain text)
        with open(ENV_FILE, "w") as env_file:
            env_file.write(f"CLIENT_ID={client_id}\n")
            env_file.write(f"CLIENT_SECRET={client_secret}\n")
            env_file.write(f"GENESYS_CLOUD_REGION={region}\n")

        os.chmod(ENV_FILE, 0o600)  # Only user can read/write


def get_access_token():
    load_dotenv(ENV_FILE)
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    global GENESYS_CLOUD_REGION
    client_region = os.getenv("GENESYS_CLOUD_REGION")
    if client_region:
        GENESYS_CLOUD_REGION = client_region

    url = f"https://login.{GENESYS_CLOUD_REGION}/oauth/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response.json().get("access_token")


def fetch_user_details(access_token, user_id):
    url = f"https://api.{GENESYS_CLOUD_REGION}/api/v2/users/{user_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def search_user_details(access_token, search_text):
    url = f"https://api.{GENESYS_CLOUD_REGION}/api/v2/users/search"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    data = {
        "query": [
            {
                "type": "CONTAINS",
                "fields": ["name"],
                "value": search_text,  # Using f-string to insert the variable
            }
        ],
        "pageSize": 50,
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def fetch_interaction(access_token, conversation_id):
    url = f"https://api.{GENESYS_CLOUD_REGION}/api/v2/conversations/{conversation_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def fetch_queue_details(access_token, queue_id):
    url = f"https://api.{GENESYS_CLOUD_REGION}/api/v2/routing/queues/{queue_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def search_queue_details(access_token, search_text):
    url = f"https://api.{GENESYS_CLOUD_REGION}/api/v2/routing/queues?pageSize=100&name=*{search_text}*"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def prompt_user_for_query(args):
    """Prompt user if no CLI arguments are provided."""
    search_types = [
        QUERY_USERID,
        QUERY_USERNAME,
        QUERY_QUEUEID,
        QUERY_QUEUENAME,
        QUERY_INTERACTION,
    ]
    questions = [
        inquirer.List(
            "query_type",
            message="What kind of lookup would you like?",
            choices=search_types,
        )
    ]
    selected_search = inquirer.prompt(questions)
    query_type = selected_search["query_type"]
    search_text = input("Search value:").strip()

    query_map = {
        QUERY_USERID: "user_id",
        QUERY_USERNAME: "user_name",
        QUERY_QUEUEID: "queue_id",
        QUERY_QUEUENAME: "queue_name",
        QUERY_INTERACTION: "interaction",
    }

    if query_type in query_map:
        setattr(
            args,
            query_map[query_type],
            [search_text] if "id" in query_map[query_type] else search_text,
        )


def process_interaction(access_token, interaction_id):
    """Fetch and display interaction details."""
    interaction_data = fetch_interaction(access_token, interaction_id)
    print("#######################################################")
    print(f"#  Interaction {interaction_id}")
    print("#######################################################")
    print(f'Start Time: {interaction_data.get("startTime", "??")}')
    for participant in interaction_data.get("participants", []):
        print(f'{participant.get("purpose", "UNK")} — {participant.get("name", "UNK")}')
        attributes = participant.get("attributes", {})
        for key, value in attributes.items():
            print(f"{key}: {value}")
    print("Copy Conversation URL? (Y/n)", end="", flush=True)
    if readchar.readchar() != "n":
        url = f"https://apps.{GENESYS_CLOUD_REGION}/directory/#/analytics/interactions/{interaction_id}/admin/details"
        pyperclip.copy(url)


def process_users(access_token, user_ids):
    """Fetch and display user details."""
    print("Getting User(s)")
    for user_id in user_ids:
        try:
            user_data = fetch_user_details(access_token, user_id)
            print(f"{user_data.get('name')} ({user_data.get('email')})")
        except requests.HTTPError:
            print(f"Failed to fetch details for user {user_id}")
        time.sleep(0.25)


def process_queues(access_token, queue_ids):
    """Fetch and display queue details."""
    print("Getting Queue(s)")
    for queue_id in queue_ids:
        try:
            queue_data = fetch_queue_details(access_token, queue_id)
            print(f"{queue_data.get('name')} : {queue_id}")
        except requests.HTTPError:
            print(f"Failed to fetch details for queue {queue_id}")
        time.sleep(0.25)


def search_users(access_token, search_text):
    """Search for users by name."""
    print("Finding User(s)")
    user_data = search_user_details(access_token, search_text)
    for user in user_data.get("results", []):
        print(f"{user.get('name')}, {user.get('email')}, {user.get('id')}")


def search_queues(access_token, search_text):
    """Search for queues by name."""
    print("Finding Queue(s)")
    queue_data = search_queue_details(access_token, search_text)
    for queue in queue_data.get("entities", []):
        print(f"{queue.get('name')}, {queue.get('id')}")


def main():
    setup_env()

    parser = argparse.ArgumentParser(
        description="Fetch user details from Genesys Cloud"
    )
    parser.add_argument("-u", "--user_id", nargs="+", help="List of User GUIDs")
    parser.add_argument("-un", "--user_name", help="Search text for User by given name")
    parser.add_argument("-q", "--queue_id", nargs="+", help="List of Queue GUIDs")
    parser.add_argument("-qn", "--queue_name", help="Search text for Queue by name.")
    parser.add_argument("-i", "--interaction", help="Show Interaction Details")
    args = parser.parse_args()

    access_token = get_access_token()

    if not any(
        [args.queue_name, args.user_name, args.queue_id, args.user_id, args.interaction]
    ):
        prompt_user_for_query(args)

    if args.interaction:
        process_interaction(access_token, args.interaction)

    if args.user_id:
        process_users(access_token, args.user_id)

    if args.queue_id:
        process_queues(access_token, args.queue_id)

    if args.user_name:
        search_users(access_token, args.user_name)

    if args.queue_name:
        search_queues(access_token, args.queue_name)


if __name__ == "__main__":
    main()
