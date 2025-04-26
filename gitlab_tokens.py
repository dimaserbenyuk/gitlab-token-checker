
import requests
import datetime
import os
import logging

# Настройки
GITLAB_BASE_URL = "http://192.168.64.6"
GITLAB_API_URL = f"{GITLAB_BASE_URL}/api/v4"
GITLAB_ADMIN_TOKEN = os.environ.get("GITLAB_ADMIN_TOKEN")
HEADERS = {"PRIVATE-TOKEN": GITLAB_ADMIN_TOKEN}
EXPIRY_THRESHOLD_DAYS = 30

LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()
if len(logging.getLogger().handlers) > 0:
    logging.getLogger().setLevel(LOGLEVEL)
else:
    logging.basicConfig(
        level=LOGLEVEL,
        format="%(message)s"
    )
logger = logging.getLogger(__name__)

seen_tokens = {}
tokens_printed = 0


def print_token(token, label=None, link=None):
    global tokens_printed
    token_key = (token.get("id"),)
    if token_key in seen_tokens:
        return
    seen_tokens[token_key] = True
    tokens_printed += 1

    if link and label:
        logger.info(f"🔗 {label}: {link}")

    fields = [
        ("Token",      "🔑", token.get("name")),
        ("Scopes",     "📜", ', '.join(token.get('scopes', [])) or "(not specified)"),
        ("Created",    "🗓️", token.get('created_at', '—')),
        ("Last used",  "🕒", token.get('last_used_at') or "Never"),
        ("Expires at", "📅", token.get('expires_at')),
    ]

    max_label_width = max(len(label) for label, _, _ in fields)

    for label, emoji, value in fields:
        logger.info(f"{emoji} {label + ':':<{max_label_width + 1}} {value}")

    logger.info("-" * 60)


def check_expiration(expires_at):
    if not expires_at or expires_at == "∞":
        return False
    expiry_date = datetime.datetime.strptime(expires_at, "%Y-%m-%d")
    days_left = (expiry_date - datetime.datetime.utcnow()).days
    return days_left <= EXPIRY_THRESHOLD_DAYS


def check_personal_tokens():
    for page in range(1, 1000):
        url = f"{GITLAB_API_URL}/personal_access_tokens?per_page=100&page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=5)
            if resp.status_code != 200:
                break
            tokens = resp.json()
            if not tokens:
                break
            for token in tokens:
                if token.get("revoked") or not token.get("active", True):
                    continue
                if not check_expiration(token.get("expires_at")):
                    continue
                user = token.get("user")
                if user:
                    label = f"{user['username']} <{user.get('email', 'без email')}>"
                    print_token(token, label=label)
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            break


def get_all_projects():
    projects = []
    for page in range(1, 1000):
        try:
            url = f"{GITLAB_API_URL}/projects?per_page=100&page={page}"
            resp = requests.get(url, headers=HEADERS, timeout=5)
            if resp.status_code != 200:
                break
            data = resp.json()
            if not data:
                break
            projects.extend(data)
        except requests.RequestException as e:
            print(f"[ERROR] Request failed: {e}")
            break
    return projects


def check_project_tokens():
    for project in get_all_projects():
        try:
            url = f"{GITLAB_API_URL}/projects/{project['id']}/access_tokens"
            resp = requests.get(url, headers=HEADERS, timeout=5)
            if resp.status_code != 200:
                continue
            for token in resp.json():
                if token.get("revoked") or not token.get("active", True):
                    continue
                if not check_expiration(token.get("expires_at")):
                    continue
                path = project['path_with_namespace']
                link = f"{GITLAB_BASE_URL}/{path}"
                print_token(token, label="Project", link=link)
        except requests.RequestException as e:
            print(f"[ERROR] Request failed: {e}")
            continue


def get_all_groups():
    groups = []
    for page in range(1, 1000):
        try:
            url = f"{GITLAB_API_URL}/groups?per_page=100&page={page}"
            resp = requests.get(url, headers=HEADERS, timeout=5)
            if resp.status_code != 200:
                break
            data = resp.json()
            if not data:
                break
            groups.extend(data)
        except requests.RequestException as e:
            print(f"[ERROR] Request failed: {e}")
            break
    return groups


def check_group_tokens():
    for group in get_all_groups():
        try:
            url = f"{GITLAB_API_URL}/groups/{group['id']}/access_tokens"
            resp = requests.get(url, headers=HEADERS, timeout=5)
            if resp.status_code != 200:
                continue
            for token in resp.json():
                if token.get("revoked") or not token.get("active", True):
                    continue
                if not check_expiration(token.get("expires_at")):
                    continue
                link = f"{GITLAB_BASE_URL}/groups/{group['full_path']}"
                print_token(token, label="Group", link=link)
        except requests.RequestException as e:
            print(f"[ERROR] Request failed: {e}")
            continue


def handler(event, context):
    global tokens_printed
    try:
        logger.info("\n=== Tokens expiring within 30 days or sooner (UTC) ===\n")
        check_personal_tokens()
        check_project_tokens()
        check_group_tokens()

        if tokens_printed == 0:
            logger.info("✅ All tokens are valid. No tokens are expiring within 30 days.")
    except Exception as e:
        logger.exception(f"Unexpected error in Lambda handler: {e}")


if __name__ == "__main__":
    handler(event=None, context=None)