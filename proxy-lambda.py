#!/usr/bin/env python3
import jwt
import os
import time
import requests

from functools import lru_cache

AWS_SESSION_TOKEN: str = os.environ["AWS_SESSION_TOKEN"]
PARAMETERS_SECRETS_EXTENSION_HTTP_PORT: str = os.environ.get("PARAMETERS_SECRETS_EXTENSION_HTTP_PORT", "2773")
APP_ID_SECRET_NAME: str = os.environ["APP_ID_SECRET_NAME"]
INSTALLATION_ID_SECRET_NAME: str = os.environ["INSTALLATION_ID_SECRET_NAME"]
PEM_CONTENTS_SECRET_NAME: str = os.environ["PEM_CONTENTS_SECRET_NAME"]


class AuthorizationException(Exception):
    pass


def get_ttl_hash(seconds: int) -> int:
    """Return the same value within `seconds` time period"""
    return round(time.time() / seconds)


@lru_cache(maxsize=20)
def get_cached_secret_string(key_name: str, is_binary: bool = False) -> str:
    value_key: str = "SecretBinary" if is_binary else "SecretString"

    url: str = (
        "https://localhost:"
        + PARAMETERS_SECRETS_EXTENSION_HTTP_PORT
        + "/secretsmanager/get?secretId="
        + key_name
    )

    headers: dict[str, str] = {
        "X-Aws-Parameters-Secrets-Token": AWS_SESSION_TOKEN,
    }
    response: requests.Response = requests.request(method="get", url=url, headers=headers)
    if response.status_code != 200:
        raise AuthorizationException("Failed retrieving secret from AWS Secrets Manager")
    return response.json()[value_key]

@lru_cache(maxsize=2)
def jwt_creator(_ttl_hash: int | None = None) -> str:
    jwt_instance: jwt.JWT = jwt.JWT()

    payload: dict[str, object] = {
        # Issued at time
        "iat": int(time.time()),
        # JWT expiration time (10 minutes maximum)
        "exp": int(time.time()) + 600,
        # GitHub App identifier
        "iss": get_cached_secret_string(APP_ID_SECRET_NAME)
    }

    pem_contents: bytes = (
        get_cached_secret_string(
            key_name=PEM_CONTENTS_SECRET_NAME,
            is_binary=True,
        ).encode(encoding="ascii")
    )

    signing_key: jwt.AbstractJWKBase = jwt.jwk_from_pem(pem_contents)

    return jwt_instance.encode(payload, signing_key, alg="RS256")


@lru_cache(maxsize=2)
def installation_token_creator(_ttl_hash: int | None = None) -> str:
    jwt_token: str = jwt_creator(get_ttl_hash(60 * 9))  # Lasts for 10 minutes
    installation_id: str = get_cached_secret_string(INSTALLATION_ID_SECRET_NAME)

    github_url: str = f"https://api.github.com/app/installations/{installation_id}/access_tokens"

    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {jwt_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response: requests.Response = requests.request(method="post", url=github_url, headers=headers)
    if response.status_code != 200:
        raise AuthorizationException("Failed retrieving installation token")
    return response.json()["token"]


def lambda_handler(event, _context) -> dict[str, object]:
    try:
        token: str = installation_token_creator(get_ttl_hash(60 * 60))  # Lasts for 1 hour
    except AuthorizationException as e:
        return {
            "statusCode": 401,
            "body": e.args[0],
        }
    except Exception:
        return {
            "statusCode": 500,
            "body": "Unexpected server error when generating authorization tokens"
        }

    pathParameters: str = event["pathParameters"]["github"]
    httpMethod: str = event["httpMethod"]
    headers: dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    # Set the GitHub GraphQL API endpoint
    github_url = "https://api.github.com/" + pathParameters

    response: requests.Response = requests.request(
        method=httpMethod,
        data=event["body"],
        url=github_url,
        headers=headers,
    )

    return {
        "statusCode": response.status_code,
        "body": response.text,
        "headers": response.headers,
    }
