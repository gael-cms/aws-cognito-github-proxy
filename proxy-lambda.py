#!/usr/bin/env python3
import boto3
import jwt
import os
import time
import requests

from functools import lru_cache

APP_ID: str = os.environ["APP_ID"]
INSTALLATION_ID: str = os.environ["INSTALLATION_ID"]
PEM_CONTENTS_SECRET_NAME: str = os.environ["PEM_CONTENTS_SECRET_NAME"]


class AuthorizationException(Exception):
    pass


def get_ttl_hash(seconds: int) -> int:
    """Return the same value within `seconds` time period"""
    return round(time.time() / seconds)


@lru_cache(maxsize=2)
def get_cached_secret_binary(key_name: str) -> bytes:
    client: boto3.client = boto3.client('secretsmanager')

    return client.get_secret_value(SecretId=key_name)["SecretBinary"]

@lru_cache(maxsize=2)
def jwt_creator(_ttl_hash: int | None = None) -> str:
    jwt_instance: jwt.JWT = jwt.JWT()

    payload: dict[str, object] = {
        # Issued at time
        "iat": int(time.time()),
        # JWT expiration time (10 minutes maximum)
        "exp": int(time.time()) + 600,
        # GitHub App identifier
        "iss": APP_ID,
    }

    signing_key: jwt.AbstractJWKBase = jwt.jwk_from_pem(
        get_cached_secret_binary(
            key_name=PEM_CONTENTS_SECRET_NAME,
        )
    )

    return jwt_instance.encode(payload, signing_key, alg="RS256")


@lru_cache(maxsize=2)
def installation_token_creator(_ttl_hash: int | None = None) -> str:
    jwt_token: str = jwt_creator(get_ttl_hash(60 * 9))  # Lasts for 10 minutes

    github_url: str = f"https://api.github.com/app/installations/{INSTALLATION_ID}/access_tokens"

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
