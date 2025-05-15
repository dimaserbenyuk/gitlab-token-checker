import requests
import datetime
import os
import logging
from datetime import timezone
import traceback
import boto3
import json
from botocore.exceptions import ClientError

GITLAB_BASE_URL = "https://5d27-2a02-a31a-c282-5880-398e-decf-f98c-1079.ngrok-free.app"
GITLAB_API_URL = f"{GITLAB_BASE_URL}/api/v4"
GITLAB_ADMIN_TOKEN = os.environ.get("GITLAB_ADMIN_TOKEN")
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

if not GITLAB_ADMIN_TOKEN:
    raise EnvironmentError("Missing GITLAB_ADMIN_TOKEN environment variable")

HEADERS = {"PRIVATE-TOKEN": GITLAB_ADMIN_TOKEN}
EXPIRY_THRESHOLD_DAYS = 30
WARNING_THRESHOLD_DAYS = 7

LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()
logging.basicConfig(level=LOGLEVEL, format="%(message)s")
logger = logging.getLogger(__name__)

sqs_client = boto3.client("sqs")
seen_tokens = {}
tokens_printed = 0
expiring_tokens = []

api_failed = True


def send_message(queue_url, message_body, message_attributes=None):
    if not message_attributes:
        message_attributes = {}
    try:
        response = sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body,
            MessageAttributes=message_attributes
        )
        logger.info(f"Message sent to SQS with ID: {response.get('MessageId')}")
        return response
    except ClientError as error:
        logger.exception("Send message failed: %s", message_body)
        raise error


def send_slack_notification(summary, tokens):
    if not SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL is not defined. Skipping Slack send.")
        return

    if not tokens:
        message = {
            "text": f"✅ *All GitLab tokens are valid.* Checked: {summary['tokens_checked']} at {summary['timestamp']}"
        }
    else:
        token_lines = []
        for t in tokens:
            scopes = ', '.join(t['scopes'])
            link_info = f"\n  Project: {t['url']}" if t.get("url") else f"\n  Source: {t['source']}"
            token_lines.append(
                f"• *{t['name']}* expires on `{t['expires_at']}`{link_info}\n  Scopes: _{scopes}_"
            )
        message = {
            "text": f"⚠️ *Expiring GitLab tokens detected! ({len(tokens)})*\n" + "\n".join(token_lines)
        }

    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=5)
        resp.raise_for_status()
        logger.info("Slack notification sent.")
    except requests.RequestException as e:
        logger.error(f"Failed to send Slack notification: {e}")


def send_slack_error_notification(message):
    if not SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL is not defined. Skipping Slack error notification.")
        return

    payload = {
        "text": f"❌ *GitLab Token Checker Error:*\n{message}"
    }

    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        resp.raise_for_status()
        logger.info("Slack error notification sent.")
    except requests.RequestException as e:
        logger.error(f"Failed to send Slack error notification: {e}")


def print_token(token, label=None, link=None):
    global tokens_printed
    token_key = (token.get("id"),)
    if token_key in seen_tokens:
        return

    seen_tokens[token_key] = True
    tokens_printed += 1

    expiring_tokens.append({
        "name": token.get("name"),
        "scopes": token.get("scopes"),
        "expires_at": token.get("expires_at"),
        "created_at": token.get("created_at"),
        "source": label or "unknown",
        "url": link or None
    })

    fields = [
        ("Token", token.get("name")),
        ("Scopes", ', '.join(token.get('scopes', [])) or "(not specified)"),
        ("Created", token.get('created_at', '—')),
        ("Last used", token.get('last_used_at') or "Never"),
        ("Expires at", token.get('expires_at')),
    ]

    max_label_width = max(len(label) for label, _ in fields)
    for label, value in fields:
        logger.info(f"{label + ':':<{max_label_width + 1}} {value}")
    logger.info("-" * 60)


def get_days_until_expiration(expires_at):
    if not expires_at or expires_at == "∞":
        return None
    expiry_date = datetime.datetime.strptime(expires_at, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    now = datetime.datetime.now(timezone.utc)
    return (expiry_date - now).days


def paginated_get(endpoint):
    global api_failed
    results = []
    for page in range(1, 1000):
        url = f"{GITLAB_API_URL}/{endpoint}?per_page=100&page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=5)
            if resp.status_code != 200:
                break
            api_failed = False
            data = resp.json()
            if not data:
                break
            results.extend(data)
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            break
    return results


def check_personal_tokens():
    global api_failed
    for page in range(1, 1000):
        url = f"{GITLAB_API_URL}/personal_access_tokens?per_page=100&page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=5)
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            break

        if resp.status_code != 200:
            break

        api_failed = False
        tokens = resp.json()
        if not tokens:
            break

        for token in tokens:
            if token.get("revoked") or not token.get("active", True):
                continue

            days_left = get_days_until_expiration(token.get("expires_at"))
            if days_left is None or days_left > EXPIRY_THRESHOLD_DAYS:
                continue

            user = token.get("user")
            if user:
                label = f"{user['username']} <{user.get('email', 'no email')}>"
                print_token(token, label=label)


def check_project_tokens():
    global api_failed
    for project in paginated_get("projects"):
        url = f"{GITLAB_API_URL}/projects/{project['id']}/access_tokens"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=5)
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            continue

        if resp.status_code != 200:
            continue

        api_failed = False
        for token in resp.json():
            if token.get("revoked") or not token.get("active", True):
                continue

            days_left = get_days_until_expiration(token.get("expires_at"))
            if days_left is None or days_left > EXPIRY_THRESHOLD_DAYS:
                continue

            path = project['path_with_namespace']
            label = "Project"
            link = f"{GITLAB_BASE_URL}/{path}"
            print_token(token, label=label, link=link)


def check_group_tokens():
    global api_failed
    for group in paginated_get("groups"):
        url = f"{GITLAB_API_URL}/groups/{group['id']}/access_tokens"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=5)
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            continue

        if resp.status_code != 200:
            continue

        api_failed = False
        for token in resp.json():
            if token.get("revoked") or not token.get("active", True):
                continue

            days_left = get_days_until_expiration(token.get("expires_at"))
            if days_left is None or days_left > EXPIRY_THRESHOLD_DAYS:
                continue

            label = "Group"
            link = f"{GITLAB_BASE_URL}/groups/{group['full_path']}"
            print_token(token, label=label, link=link)


def lambda_handler(event=None, context=None):
    global tokens_printed, api_failed
    try:
        logger.info("=== Lambda execution started ===")
        logger.info(f"Token length: {len(GITLAB_ADMIN_TOKEN) if GITLAB_ADMIN_TOKEN else 'MISSING'}")

        check_personal_tokens()
        logger.info("\n--- Project Tokens ---\n")
        check_project_tokens()
        logger.info("\n--- Group Tokens ---\n")
        check_group_tokens()

        if api_failed:
            error_msg = "GitLab API is unavailable!!! Unable to check tokens."
            logger.error(f"❌ {error_msg}")
            send_slack_error_notification(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "tokens_checked": 0
            }

        summary = {
            "tokens_checked": tokens_printed,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

        if tokens_printed == 0:
            logger.info("All tokens are valid. No tokens are expiring within 30 days.")
        else:
            logger.info(f"{tokens_printed} expiring tokens found.")

        if SQS_QUEUE_URL:
            message = {
                "summary": summary,
                "tokens": expiring_tokens
            }
            send_message(SQS_QUEUE_URL, json.dumps(message))

        send_slack_notification(summary, expiring_tokens)

        logger.info("=== Lambda execution finished ===")
        return {
            "status": "ok",
            "tokens_checked": tokens_printed
        }

    except Exception as e:
        logger.error("ERROR OCCURRED IN LAMBDA EXECUTION")
        logger.error(str(e))
        traceback_str = traceback.format_exc()
        logger.error(traceback_str)
        send_slack_error_notification(f"Unexpected error:\n{str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback_str
        }


if __name__ == "__main__":
    lambda_handler()
