"""Create isolated service databases and populate their scoped runtime secrets."""

from __future__ import annotations

import json
import logging
import os
import secrets
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlparse

import boto3
import psycopg2
from psycopg2 import sql

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServiceDatabase:
    name: str
    database: str
    role: str
    secret_arn_env: str
    secret_key: str
    scheme: str


SERVICES = (
    ServiceDatabase(
        "api",
        "macoach_api",
        "macoach_api",
        "APPLICATION_SECRET_ARN",
        "DATABASE_URL",
        "postgresql+asyncpg",
    ),
    ServiceDatabase(
        "recovery",
        "macoach_recovery",
        "macoach_recovery",
        "RECOVERY_SECRET_ARN",
        "RECOVERY_DATABASE_URL",
        "postgresql",
    ),
    ServiceDatabase(
        "nutrition",
        "macoach_nutrition",
        "macoach_nutrition",
        "NUTRITION_SECRET_ARN",
        "NUTRITION_DATABASE_URL",
        "postgresql",
    ),
    ServiceDatabase(
        "training",
        "macoach_training",
        "macoach_training",
        "TRAINING_SECRET_ARN",
        "TRAINING_DATABASE_URL",
        "postgresql",
    ),
)


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def existing_password(secret_value: dict[str, object], key: str) -> str | None:
    value = secret_value.get(key)
    if not isinstance(value, str) or not value:
        return None
    password = urlparse(value).password
    return unquote(password) if password else None


def secret_json(client, arn: str) -> dict[str, object]:
    value = client.get_secret_value(SecretId=arn)["SecretString"]
    result = json.loads(value)
    if not isinstance(result, dict):
        raise TypeError(f"Runtime secret {arn} must contain a JSON object")
    return result


def connect(master: dict[str, object], endpoint: str):
    return psycopg2.connect(
        host=endpoint,
        port=master.get("port", 5432),
        user=master["username"],
        password=master["password"],
        dbname="postgres",
        sslmode="require",
    )


def runtime_database_url(service: ServiceDatabase, password: str, endpoint: str) -> str:
    """Build an asyncpg-compatible TLS URL for a service database."""
    encoded_password = quote(password, safe="")
    return (
        f"{service.scheme}://{service.role}:{encoded_password}@{endpoint}:5432/"
        f"{service.database}?ssl=require"
    )


def role_exists(cursor, role: str) -> bool:
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    return cursor.fetchone() is not None


def database_exists(cursor, database: str) -> bool:
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
    return cursor.fetchone() is not None


def provision_database(
    cursor, service: ServiceDatabase, password: str, *, reset_password: bool
) -> None:
    if not role_exists(cursor, service.role):
        cursor.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD %s"
            ).format(sql.Identifier(service.role)),
            (password,),
        )
    elif reset_password:
        cursor.execute(
            sql.SQL("ALTER ROLE {} PASSWORD %s").format(sql.Identifier(service.role)),
            (password,),
        )
    if not database_exists(cursor, service.database):
        cursor.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(service.database), sql.Identifier(service.role)
            )
        )
    cursor.execute(
        sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
            sql.Identifier(service.database)
        )
    )
    cursor.execute(
        sql.SQL("GRANT CONNECT, TEMPORARY ON DATABASE {} TO {}").format(
            sql.Identifier(service.database), sql.Identifier(service.role)
        )
    )


def main() -> None:
    secrets_client = boto3.client("secretsmanager", region_name=required("AWS_REGION"))
    master = json.loads(
        secrets_client.get_secret_value(SecretId=required("MASTER_SECRET_ARN"))[
            "SecretString"
        ]
    )
    endpoint = required("DATABASE_ENDPOINT")
    runtime_secrets = {
        service: secret_json(secrets_client, required(service.secret_arn_env))
        for service in SERVICES
    }
    existing_passwords = {
        service: existing_password(runtime_secrets[service], service.secret_key)
        for service in SERVICES
    }
    passwords = {
        service: existing_passwords[service] or secrets.token_urlsafe(32)
        for service in SERVICES
    }

    connection = connect(master, endpoint)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            for service in SERVICES:
                provision_database(
                    cursor,
                    service,
                    passwords[service],
                    reset_password=existing_passwords[service] is None,
                )
    finally:
        connection.close()

    for service in SERVICES:
        value = runtime_secrets[service]
        value[service.secret_key] = runtime_database_url(
            service, passwords[service], endpoint
        )
        secrets_client.put_secret_value(
            SecretId=required(service.secret_arn_env), SecretString=json.dumps(value)
        )
        logger.info("Updated %s runtime database URL", service.name)


if __name__ == "__main__":
    main()
