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
GENESYS_CLOUD_REGION = 'usw2.pure.cloud' #default

#['User by ID', 'User by Name', 'Queue by ID', 'Queue by Name']
QUERY_USERID = 'User by ID'
QUERY_USERNAME = 'User by Name'
QUERY_QUEUEID = 'Queue by ID'
QUERY_QUEUENAME = 'Queue by Name'
QUERY_INTERACTION = 'Interaction by ID'


# Ensure the config directory exists with correct permissions
try:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)  # Only user can access
except Exception as e:
    print(f"An error occurred: {e}")

def setup_env():
    """Create the .env file in ~/.gclookup if it doesn’t exist."""
    if not os.path.exists(ENV_FILE):
        region = input("Enter your region [usw2.pure.cloud]: ").strip() or 'usw2.pure.cloud'

        if not region:
            region = 'usw2.pure.cloud'
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

    url = f'https://login.{GENESYS_CLOUD_REGION}/oauth/token'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response.json().get('access_token')


def fetch_user_details(access_token, user_id):
    url = f'https://api.{GENESYS_CLOUD_REGION}/api/v2/users/{user_id}'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def search_user_details(access_token, search_text):
    url = f'https://api.{GENESYS_CLOUD_REGION}/api/v2/users/search'
    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
    data = {
        "query": [
            {
                "type": "CONTAINS",
                "fields": [
                    "name"
                ],
                "value": search_text  # Using f-string to insert the variable
            }
        ],
        "pageSize": 50
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def fetch_interaction(access_token, conversation_id):
    url = f'https://api.{GENESYS_CLOUD_REGION}/api/v2/conversations/{conversation_id}'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def fetch_queue_details(access_token, queue_id):
    url = f'https://api.{GENESYS_CLOUD_REGION}/api/v2/routing/queues/{queue_id}'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def search_queue_details(access_token, search_text):
    url = f'https://api.{GENESYS_CLOUD_REGION}/api/v2/routing/queues?pageSize=100&name=*{search_text}*'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def main():
    setup_env()

    parser = argparse.ArgumentParser(description="Fetch user details from Genesys Cloud")
    parser.add_argument("-u", "--user_id", nargs='+', required=False, help="List of User GUIDs")
    parser.add_argument("-un", "--user_name", required=False, help="Search text for User by given name")
    parser.add_argument("-q", "--queue_id", nargs='+', required=False, help="List of Queue GUIDs")
    parser.add_argument("-qn", "--queue_name", required=False, help="Search text for Queue by name.")
    parser.add_argument("-i", "--interaction", required=False, help="Show Interaction Details")
    args = parser.parse_args()

    access_token = get_access_token()

    if not args.queue_name and not args.user_name and not args.queue_id and not args.user_id and not args.interaction:
        #prompt for information
        global QUERY_USERID, QUERY_USERNAME, QUERY_QUEUEID, QUERY_QUEUENAME, QUERY_INTERACTION
        search_types = [QUERY_USERID, QUERY_USERNAME, QUERY_QUEUEID, QUERY_QUEUENAME, QUERY_INTERACTION]
        questions = [inquirer.List('query_type', message="What kind of lookup would you like?", choices=search_types)]
        selected_search = inquirer.prompt(questions)
        query_type = selected_search['query_type']

        searchText = input("Search value:").strip()

        query_map = {
            QUERY_USERID: "user_id",
            QUERY_USERNAME: "user_name",
            QUERY_QUEUEID: "queue_id",
            QUERY_QUEUENAME: "queue_name",
            QUERY_INTERACTION: "interaction"
        }

        if query_type in query_map:
            setattr(args, query_map[query_type], [searchText] if "id" in query_map[query_type] else searchText)


    if args.interaction and len(args.interaction) > 0:
        interaction_data = fetch_interaction(access_token, args.interaction)
        print('#######################################################')
        print(f'#  Interaction {args.interaction}')
        print('#######################################################')
        #print(json.dumps(interaction_data, indent=4))
        print(f'Start Time: {interaction_data.get('startTime','??')}')
        for participant in interaction_data.get('participants',[]):
            print(f'{participant.get('purpose', 'UNK')} — {participant.get('name', 'UNK')}')
            attributes = participant.get('attributes', {})
            for key, value in attributes.items():
                print(f'{key}:{value}')
        print('Copy Conversation URL? (Y/n)', end='', flush=True)
        pop = readchar.readchar()
        print('')
        if (pop != 'n'):
            url = f'https://apps.{GENESYS_CLOUD_REGION}/directory/#/analytics/interactions/{args.interaction}/admin/details'
            pyperclip.copy(url)
            # could also import webbrowser and pop: webbrowser.open_new_tab(url)


    if args.user_id and len(args.user_id) > 0:
        print('Getting User(s)')
        for user_id in args.user_id:
            try:
                user_data = fetch_user_details(access_token, user_id)
                #if args.inactive and user_data.get('state') != 'inactive':
                #    continue
                print(f"{user_data.get('name')} ({user_data.get('email')})")
            except requests.HTTPError:
                print(f"Failed to fetch details for user {user_id}")
            time.sleep(0.25)

    if args.queue_id and len(args.queue_id) > 0:
        print('Getting Queue(s)')
        for queue_id in args.queue_id:
            try:
                queue_data = fetch_queue_details(access_token, queue_id)
                print(f"{queue_data.get('name')} : {queue_id}")
            except requests.HTTPError:
                print(f"Failed to fetch details for user {queue_id}")
            time.sleep(0.25)

    if args.user_name and len(args.user_name) > 0:
        print('Finding User(s)')
        user_data = search_user_details(access_token, args.user_name)
        for user in user_data.get('results',[]):
            try:
                print(f"{user.get('name')}, {user.get('email')}, {user.get('id')}")
            except requests.HTTPError:
                print(f"Failed to fetch details for user {args.user_name}")
            time.sleep(0.25)

    if args.queue_name:
        print('Finding Queue(s)')
        queue_data = search_queue_details(access_token, args.queue_name)
        for queue in queue_data.get('entities',[]):
            try:
                print(f"{queue.get('name')}, {queue.get('id')}")
            except requests.HTTPError:
                print(f"Failed to fetch details for queue {args.queue_name}")
            time.sleep(0.25)



if __name__ == "__main__":
    main()
