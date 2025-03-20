import os
import sys
import json
import pyperclip
import argparse
import requests
import inquirer
import readchar
import time
import keyring

# Constants for keychain storage
KEYCHAIN_SERVICE = "gclookup_config"
KEYCHAIN_USER = "config"

# Default Genesys Cloud region
DEFAULT_REGION = "usw2.pure.cloud"

# Query type constants
QUERY_USERID = "User by ID"
QUERY_USERNAME = "User by Name"
QUERY_QUEUEID = "Queue by ID"
QUERY_QUEUENAME = "Queue by Name"
QUERY_INTERACTION = "Interaction by ID"


def get_stored_configs():
    """Retrieve stored configuration from keychain as a JSON array."""
    config_str = keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_USER)
    if config_str:
        try:
            configs = json.loads(config_str)
            if isinstance(configs, list):
                return configs
        except Exception as e:
            print(f"Error parsing stored config: {e}")
    return []


def store_configs(configs):
    """Store the configurations list as a JSON string in the keychain."""
    config_str = json.dumps(configs)
    keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_USER, config_str)


def choose_default_config(configs):
    """
    Choose a default configuration.
    If one of the configs has 'name' equal to 'default' (case-insensitive), use that.
    Otherwise, if multiple exist, prompt the user to select one.
    """
    for config in configs:
        if config.get("name", "").lower() == "default":
            return config
    if len(configs) > 1:
        choices = [cfg["name"] for cfg in configs]
        questions = [inquirer.List("config_choice", message="Choose a configuration", choices=choices)]
        answer = inquirer.prompt(questions)
        selected_name = answer["config_choice"]
        for cfg in configs:
            if cfg.get("name") == selected_name:
                return cfg
    elif configs:
        return configs[0]
    return None


def setup_config():
    """
    Set up configuration in the keychain.
    If no configuration exists, prompt the user to create one.
    Returns the chosen configuration.
    """
    configs = get_stored_configs()
    if not configs:
        print("No configuration found in keychain. Let's set up a new configuration.")
        name = input("Enter a label for this configuration (e.g., default): ").strip() or "default"
        region = input(f"Enter your region [{DEFAULT_REGION}]: ").strip() or DEFAULT_REGION
        client_id = input("Enter your CLIENT_ID: ").strip()
        client_secret = input("Enter your CLIENT_SECRET: ").strip()
        if not client_id or not client_secret:
            print("CLIENT_ID and CLIENT_SECRET cannot be empty.")
            exit(1)
        config = {
            "name": name,
            "CLIENT_ID": client_id,
            "CLIENT_SECRET": client_secret,
            "GENESYS_CLOUD_REGION": region
        }
        configs.append(config)
        store_configs(configs)
        return config
    else:
        return choose_default_config(configs)


def prompt_config_data(existing_config=None):
    """
    Prompt the user for configuration data.
    If existing_config is provided, use its values as defaults.
    Returns a config dictionary.
    """
    if existing_config:
        print("Editing configuration. Leave field blank to keep the current value.")
        name = input(f"Configuration name [{existing_config.get('name')}]: ").strip() or existing_config.get('name')
        region = input(f"Region [{existing_config.get('GENESYS_CLOUD_REGION', DEFAULT_REGION)}]: ").strip() or existing_config.get('GENESYS_CLOUD_REGION', DEFAULT_REGION)
        client_id = input(f"CLIENT_ID [{existing_config.get('CLIENT_ID')}]: ").strip() or existing_config.get('CLIENT_ID')
        client_secret = input("CLIENT_SECRET (enter to keep unchanged): ").strip() or existing_config.get('CLIENT_SECRET')
    else:
        print("Creating a new configuration:")
        name = input("Enter a label for this configuration: ").strip() or "default"
        region = input(f"Enter your region [{DEFAULT_REGION}]: ").strip() or DEFAULT_REGION
        client_id = input("Enter your CLIENT_ID: ").strip()
        client_secret = input("Enter your CLIENT_SECRET: ").strip()

    if not client_id or not client_secret:
        print("CLIENT_ID and CLIENT_SECRET cannot be empty.")
        exit(1)

    return {
        "name": name,
        "CLIENT_ID": client_id,
        "CLIENT_SECRET": client_secret,
        "GENESYS_CLOUD_REGION": region
    }

def create_new_config():
    """Prompt the user to create a new configuration and add it to the keychain."""
    config = prompt_config_data()
    configs = get_stored_configs()
    configs.append(config)
    store_configs(configs)
    print("New configuration added.")
    return config

def edit_config():
    """Let the user edit an existing configuration."""
    configs = get_stored_configs()
    if not configs:
        print("No configurations exist. Please create one first.")
        return None
    choices = [cfg["name"] for cfg in configs]
    questions = [inquirer.List("config_choice", message="Select a configuration to edit", choices=choices)]
    answer = inquirer.prompt(questions)
    selected_name = answer["config_choice"]
    for idx, cfg in enumerate(configs):
        if cfg["name"] == selected_name:
            updated_cfg = prompt_config_data(existing_config=cfg)
            configs[idx] = updated_cfg
            store_configs(configs)
            print("Configuration updated.")
            return updated_cfg
    return None

def get_access_token(config):
    """Use the configuration to get an access token from Genesys Cloud."""
    region = config.get("GENESYS_CLOUD_REGION", DEFAULT_REGION)
    url = f"https://login.{region}/oauth/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": config.get("CLIENT_ID"),
        "client_secret": config.get("CLIENT_SECRET")
    }
    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response.json().get("access_token")


def fetch_user_details(access_token, user_id, region):
    """Call the users API for the user data."""
    url = f"https://api.{region}/api/v2/users/{user_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def search_user_details(access_token, search_text, region):
    """Perform a search using users search API. Will cut off at 50."""
    url = f"https://api.{region}/api/v2/users/search"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "query": [
            {
                "type": "CONTAINS",
                "fields": ["name"],
                "value": search_text,
            }
        ],
        "pageSize": 50,
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def fetch_interaction(access_token, conversation_id, region):
    """Get Interaction/Conversation data from API"""
    # Sorry, not sorry. "Interaction" is still stuck in my head and will probably be forever.
    url = f"https://api.{region}/api/v2/conversations/{conversation_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def fetch_queue_details(access_token, queue_id, region):
    """Get Queue details from API"""
    url = f"https://api.{region}/api/v2/routing/queues/{queue_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def search_queue_details(access_token, search_text, region):
    """Search for matching queues by name via API, maxing at 100"""
    PAGE_SIZE = 100 #yes, we could easily page through here but we're expecting you to submit a reasonably narrow search
    url = f"https://api.{region}/api/v2/routing/queues?pageSize={PAGE_SIZE}&name=*{search_text}*"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def prompt_user_for_query(args):
    """Prompt user if no CLI arguments are provided."""
    search_types = [QUERY_USERID, QUERY_USERNAME, QUERY_QUEUEID, QUERY_QUEUENAME, QUERY_INTERACTION]
    questions = [
        inquirer.List("query_type", message="What kind of lookup would you like?", choices=search_types)
    ]
    selected_search = inquirer.prompt(questions)
    if selected_search is None:
                sys.exit(0) #exit
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
        setattr(args, query_map[query_type],
                [search_text] if "id" in query_map[query_type] else search_text)


def process_interaction(access_token, interaction_id, region):
    """Fetch and display interaction details."""
    interaction_data = fetch_interaction(access_token, interaction_id, region)
    print("#######################################################")
    print(f"#  Interaction {interaction_id}")
    print("#######################################################")
    print(f"Start Time: {interaction_data.get('startTime', '??')}")
    for participant in interaction_data.get("participants", []):
        print(f"{participant.get('purpose', 'UNK')} — {participant.get('name', 'UNK')}")
        attributes = participant.get("attributes", {})
        for key, value in attributes.items():
            print(f"{key}: {value}")
    print("Copy Conversation URL? (Y/n)", end="", flush=True)
    print("") # keep it pretty on input
    if readchar.readchar() != "n":
        url = f"https://apps.{region}/directory/#/analytics/interactions/{interaction_id}/admin/details"
        pyperclip.copy(url)


def process_users(access_token, user_ids, region):
    """Fetch and display user details."""
    print("Getting User(s)")
    for user_id in user_ids:
        try:
            user_data = fetch_user_details(access_token, user_id, region)
            print(f"{user_data.get('name')} ({user_data.get('email')})")
        except requests.HTTPError:
            print(f"Failed to fetch details for user {user_id}")
        time.sleep(0.25)


def process_queues(access_token, queue_ids, region):
    """Fetch and display queue details."""
    print("Getting Queue(s)")
    for queue_id in queue_ids:
        try:
            queue_data = fetch_queue_details(access_token, queue_id, region)
            print(f"{queue_data.get('name')} : {queue_id}")
        except requests.HTTPError:
            print(f"Failed to fetch details for queue {queue_id}")
        time.sleep(0.25)


def search_users(access_token, search_text, region):
    """Search for users by name."""
    print("Finding User(s)")
    user_data = search_user_details(access_token, search_text, region)
    for user in user_data.get("results", []):
        print(f"{user.get('name')}, {user.get('email')}, {user.get('id')}")


def search_queues(access_token, search_text, region):
    """Search for queues by name."""
    print("Finding Queue(s)")
    queue_data = search_queue_details(access_token, search_text, region)
    for queue in queue_data.get("entities", []):
        print(f"{queue.get('name')}, {queue.get('id')}")


def main():
    parser = argparse.ArgumentParser(description="Fetch details from Genesys Cloud")
    parser.add_argument("-o", "--org", help="Name of the configuration to use")
    parser.add_argument("--new-config", action="store_true", help="Create a new configuration")
    parser.add_argument("--edit-config", action="store_true", help="Edit existing configurations")
    parser.add_argument("-u", "--user_id", nargs="+", help="List of User GUIDs")
    parser.add_argument("-un", "--user_name", help="Search text for User by given name")
    parser.add_argument("-q", "--queue_id", nargs="+", help="List of Queue GUIDs")
    parser.add_argument("-qn", "--queue_name", help="Search text for Queue by name.")
    parser.add_argument("-i", "--interaction", help="Show Interaction Details")
    args = parser.parse_args()

    # Determine configuration to use
    if args.new_config:
        config = create_new_config()
        sys.exit(0)
    elif args.edit_config:
        config = edit_config()
        sys.exit(0)
    else:
        configs = get_stored_configs()
        if args.org:
            config = next((cfg for cfg in configs if cfg.get("name") == args.org), None)
            if not config:
                print(f"Configuration '{args.org}' not found.")
                exit(1)
        else:
            config = setup_config()

    access_token = get_access_token(config)
    region = config.get("GENESYS_CLOUD_REGION", DEFAULT_REGION)

    if not any([args.queue_name, args.user_name, args.queue_id, args.user_id, args.interaction]):
        prompt_user_for_query(args)

    if args.interaction:
        process_interaction(access_token, args.interaction, region)
    if args.user_id:
        process_users(access_token, args.user_id, region)
    if args.queue_id:
        process_queues(access_token, args.queue_id, region)
    if args.user_name:
        search_users(access_token, args.user_name, region)
    if args.queue_name:
        search_queues(access_token, args.queue_name, region)


if __name__ == "__main__":
    main()
