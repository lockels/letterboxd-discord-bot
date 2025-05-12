import json
from pathlib import Path
import rating_updates


def load_servers(path="utils/servers.json"):
    if Path(path).exists():
        with open(path, "r") as file:
            return json.load(file)
    return {}


def save_servers(servers, path="utils/servers.json"):
    with open(path, "w") as file:
        json.dump(servers, file, indent=2)


def add_server(db, server_id):
    if server_id not in db:
        db[server_id] = {}
    save_servers(db)


def insert_user(db, user, letterboxd_handle, server_id):
    if server_id not in db:
        db[server_id] = {}
    db[server_id][user] = letterboxd_handle
    save_servers(db)


def delete_user(db, user, server_id):
    if server_id in db and user in db[server_id]:
        del db[server_id][user]

    rating_updates.remove_user_data(user, server_id)
    save_servers(db)


def get_url_from_handle(handle, server_id):
    servers = load_servers()
    try:
        handle = servers[server_id][handle]
        return f"https://letterboxd.com/{handle}/films/page/1/"
    except KeyError:
        return None


if __name__ == "__main__":
    servers = load_servers()
    print(servers)
