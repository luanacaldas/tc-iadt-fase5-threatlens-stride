"""Canonical cloud class mapping for ThreatLens.

This file centralizes cloud-provider-to-canonical-class normalization so the
dataset preparer and other scripts can stay aligned.
"""

from __future__ import annotations

from dataclasses import dataclass


CANONICAL_CLASSES = [
    "api_gateway",
    "backup",
    "cdn",
    "compute",
    "database",
    "identity_provider",
    "internet",
    "load_balancer",
    "monitoring",
    "queue",
    "secrets_kms",
    "storage",
    "user",
    "waf",
]


@dataclass(frozen=True)
class CloudClassMapping:
    provider: str
    source_name: str
    canonical_name: str


PROVIDER_ALIASES = {
    "aws": "aws",
    "amazon web services": "aws",
    "azure": "azure",
    "microsoft azure": "azure",
    "gcp": "gcp",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
}


CLASS_ALIASES = {
    "api gateway": "api_gateway",
    "api gateway service": "api_gateway",
    "apigateway": "api_gateway",
    "aws api gateway": "api_gateway",
    "azure api management": "api_gateway",
    "gcp api gateway": "api_gateway",
    "cloud endpoints": "api_gateway",
    "cloudfront": "cdn",
    "cdn": "cdn",
    "compute engine": "compute",
    "ec2": "compute",
    "ecs": "compute",
    "aks": "compute",
    "gke": "compute",
    "cloud run": "compute",
    "cloud functions": "compute",
    "app service": "compute",
    "database": "database",
    "db": "database",
    "rds": "database",
    "cloudsql": "database",
    "sql database": "database",
    "sql": "database",
    "cosmos db": "database",
    "identity provider": "identity_provider",
    "idp": "identity_provider",
    "iam": "identity_provider",
    "entra id": "identity_provider",
    "adfs": "identity_provider",
    "auth0": "identity_provider",
    "internet": "internet",
    "public internet": "internet",
    "load balancer": "load_balancer",
    "alb": "load_balancer",
    "elb": "load_balancer",
    "application gateway": "load_balancer",
    "monitoring": "monitoring",
    "logs": "monitoring",
    "cloud watch": "monitoring",
    "cloud monitoring": "monitoring",
    "queue": "queue",
    "pubsub": "queue",
    "sqs": "queue",
    "service bus": "queue",
    "secrets": "secrets_kms",
    "kms": "secrets_kms",
    "key management": "secrets_kms",
    "secret manager": "secrets_kms",
    "key vault": "secrets_kms",
    "storage": "storage",
    "s3": "storage",
    "gcs": "storage",
    "blob storage": "storage",
    "cloud storage": "storage",
    "user": "user",
    "actor": "user",
    "waf": "waf",
    "web application firewall": "waf",
}


# Ordered, conservative fallback rules for provider-specific labels. Exact
# aliases above always win. These rules cover labels such as
# ``aws_amazon_api_gateway`` and ``azure_sql_server`` without maintaining a
# separate alias for every provider spelling.
CLASS_KEYWORD_ALIASES = [
    ("api gateway", "api_gateway"),
    ("api management", "api_gateway"),
    ("cloud endpoints", "api_gateway"),
    ("apigee", "api_gateway"),
    ("web application firewall", "waf"),
    ("cloud armor", "waf"),
    ("waf", "waf"),
    ("cloudfront", "cdn"),
    ("front door", "cdn"),
    ("cdn", "cdn"),
    ("load balancer", "load_balancer"),
    ("elastic load balancing", "load_balancer"),
    ("cloud load balancing", "load_balancer"),
    ("application gateway", "load_balancer"),
    ("traffic manager", "load_balancer"),
    ("recovery services", "backup"),
    ("backup", "backup"),
    ("archive", "backup"),
    ("key vault", "secrets_kms"),
    ("secret manager", "secrets_kms"),
    ("secrets manager", "secrets_kms"),
    ("key management", "secrets_kms"),
    ("certificate manager", "secrets_kms"),
    ("kms", "secrets_kms"),
    ("simple queue service", "queue"),
    ("simple notification service", "queue"),
    ("service bus", "queue"),
    ("event hubs", "queue"),
    ("event grid", "queue"),
    ("pub sub", "queue"),
    ("pubsub", "queue"),
    ("kinesis", "queue"),
    ("queue", "queue"),
    ("cloudwatch", "monitoring"),
    ("application insights", "monitoring"),
    ("cloud trail", "monitoring"),
    ("cloudtrail", "monitoring"),
    ("log analytics", "monitoring"),
    ("monitor", "monitoring"),
    ("logging", "monitoring"),
    ("sql server", "database"),
    ("sql database", "database"),
    ("sql managed instance", "database"),
    ("cloud sql", "database"),
    ("cosmos db", "database"),
    ("dynamodb", "database"),
    ("bigtable", "database"),
    ("bigquery", "database"),
    ("firestore", "database"),
    ("spanner", "database"),
    ("synapse analytics", "database"),
    ("redshift", "database"),
    ("aurora", "database"),
    ("rds", "database"),
    ("database", "database"),
    ("cloud storage", "storage"),
    ("elastic block store", "storage"),
    ("blob storage", "storage"),
    ("data lake storage", "storage"),
    ("elastic file system", "storage"),
    ("simple storage service", "storage"),
    ("storage", "storage"),
    ("elasticache", "database"),
    ("identity and access management", "identity_provider"),
    ("active directory", "identity_provider"),
    ("entra id", "identity_provider"),
    ("cognito", "identity_provider"),
    ("identity", "identity_provider"),
    ("iam", "identity_provider"),
    ("elastic kubernetes service", "compute"),
    ("kubernetes services", "compute"),
    ("kubernetes engine", "compute"),
    ("container instances", "compute"),
    ("container service", "compute"),
    ("container apps", "compute"),
    ("compute engine", "compute"),
    ("lambda function", "compute"),
    ("function apps", "compute"),
    ("cloud functions", "compute"),
    ("cloud run", "compute"),
    ("app service", "compute"),
    ("logic apps", "compute"),
    ("machine learning studio", "compute"),
    ("machine learning", "compute"),
    ("vertex ai", "compute"),
    ("openai", "compute"),
    ("vm scale sets", "compute"),
    ("auto scaling", "compute"),
    ("virtual machines", "compute"),
    ("virtual machine", "compute"),
    ("data factories", "compute"),
    ("databricks", "compute"),
    ("lambda", "compute"),
    ("fargate", "compute"),
    ("ec2", "compute"),
    ("ecs", "compute"),
    ("eks", "compute"),
    ("gke", "compute"),
]


PROVIDER_PREFIXES = (
    "amazon web services ",
    "google cloud platform ",
    "microsoft azure ",
    "aws amazon ",
    "google cloud ",
    "azure ",
    "gcp ",
    "aws ",
)


PROVIDER_HINTS = {
    "aws": {
        "api_gateway": "aws",
        "database": "aws",
        "storage": "aws",
        "identity_provider": "aws",
        "secrets_kms": "aws",
        "waf": "aws",
        "cdn": "aws",
        "load_balancer": "aws",
        "monitoring": "aws",
        "queue": "aws",
        "compute": "aws",
    },
    "azure": {
        "api_gateway": "azure",
        "database": "azure",
        "storage": "azure",
        "identity_provider": "azure",
        "secrets_kms": "azure",
        "waf": "azure",
        "cdn": "azure",
        "load_balancer": "azure",
        "monitoring": "azure",
        "queue": "azure",
        "compute": "azure",
    },
    "gcp": {
        "api_gateway": "gcp",
        "database": "gcp",
        "storage": "gcp",
        "identity_provider": "gcp",
        "secrets_kms": "gcp",
        "waf": "gcp",
        "cdn": "gcp",
        "load_balancer": "gcp",
        "monitoring": "gcp",
        "queue": "gcp",
        "compute": "gcp",
    },
}


def normalize_provider_name(value: str | None) -> str:
    if not value:
        return "generic"
    key = " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())
    return PROVIDER_ALIASES.get(key, key)


def normalize_class_name(value: str | None) -> str | None:
    if not value:
        return None
    key = " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())
    if key in CLASS_ALIASES:
        return CLASS_ALIASES[key]
    canonical = key.replace(" ", "_")
    if canonical in CANONICAL_CLASSES:
        return canonical
    if key in CANONICAL_CLASSES:
        return key

    provider_neutral = key
    for prefix in PROVIDER_PREFIXES:
        if provider_neutral.startswith(prefix):
            provider_neutral = provider_neutral[len(prefix):]
            break

    if provider_neutral in CLASS_ALIASES:
        return CLASS_ALIASES[provider_neutral]

    for keyword, canonical_name in CLASS_KEYWORD_ALIASES:
        if keyword in provider_neutral:
            return canonical_name
    return None


def map_class(provider: str | None, source_name: str | None) -> str | None:
    canonical = normalize_class_name(source_name)
    if canonical is None:
        return None
    provider_key = normalize_provider_name(provider)
    if provider_key in PROVIDER_HINTS and canonical in PROVIDER_HINTS[provider_key]:
        return canonical
    return canonical


def describe_mappings() -> list[CloudClassMapping]:
    rows: list[CloudClassMapping] = []
    for provider in ("aws", "azure", "gcp"):
        for source_name, canonical_name in CLASS_ALIASES.items():
            rows.append(CloudClassMapping(provider=provider, source_name=source_name, canonical_name=canonical_name))
    return rows


if __name__ == "__main__":
    print("Canonical ThreatLens classes:")
    for index, class_name in enumerate(CANONICAL_CLASSES):
        print(f"  {index:02d}: {class_name}")

    print("\nKnown mappings:")
    for row in describe_mappings()[:100]:
        print(f"  {row.provider}: {row.source_name} -> {row.canonical_name}")
