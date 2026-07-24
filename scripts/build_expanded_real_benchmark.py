"""Build the 15-image, provider-balanced real architecture benchmark."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/benchmarks/real-architecture/benchmark.json"
OUTPUT = ROOT / "data/benchmarks/real-architecture/benchmark-expanded.json"


def component(component_id: str, name: str, component_type: str, bbox: list[float]) -> dict:
    return {"id": component_id, "name": name, "type": component_type, "bboxNormalized": bbox}


def flow(flow_id: str, source: str, target: str, protocol: str = "unknown") -> dict:
    return {"id": flow_id, "from": source, "to": target, "protocol": protocol}


def attach_flow_protocols(item: dict) -> dict:
    explicit = {
        protocol["flowId"]: protocol["value"]
        for protocol in item.get("protocols") or []
        if protocol.get("flowId") and protocol.get("value")
    }
    item["flows"] = [
        {**current, "protocol": current.get("protocol") or explicit.get(current.get("id"), "unknown")}
        for current in item.get("flows") or []
    ]
    return item


def entry(
    entry_id: str,
    provider: str,
    source_group: str,
    split: str,
    image: str,
    components: list[dict],
    flows: list[dict],
    boundaries: list[dict] | None = None,
    protocols: list[dict] | None = None,
) -> dict:
    image_path = ROOT / image
    return {
        "id": entry_id,
        "provider": provider,
        "sourceGroup": source_group,
        "split": split,
        "image": image,
        "imageSha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "annotationStatus": "human_verified",
        "annotationMethod": "Manual visual review of primary architecture content; augmentation overlays excluded.",
        "components": components,
        "flows": attach_flow_protocols({"flows": flows, "protocols": protocols or []})["flows"],
        "boundaries": boundaries or [],
        "protocols": protocols or [],
    }


def additions() -> list[dict]:
    c, f, e = component, flow, entry
    return [
        e("gcp-secure-cloud-run", "gcp", "google_cloud_official_serverless_blueprint", "development_tuning", "data/benchmarks/real-architecture/images/gcp-secure-cloud-run.png", [
            c("internet", "Internet", "internet", [0.00, 0.225, 0.145, 0.295]),
            c("armor", "Google Cloud Armor", "waf", [0.425, 0.132, 0.615, 0.201]),
            c("load_balancer", "Cloud Load Balancer", "load_balancer", [0.425, 0.226, 0.615, 0.294]),
            c("cloud_run", "Cloud Run", "compute", [0.425, 0.344, 0.615, 0.413]),
            c("vpc_connector", "Serverless VPC Access connector", "compute", [0.644, 0.344, 0.880, 0.413]),
            c("artifact_registry", "Artifact Registry", "storage", [0.258, 0.510, 0.434, 0.580]),
            c("kms", "Cloud KMS", "secrets_kms", [0.258, 0.622, 0.434, 0.691]),
            c("secret_manager", "Secret Manager", "secrets_kms", [0.258, 0.733, 0.434, 0.802]),
            c("firewall", "Ingress and egress rules", "waf", [0.660, 0.489, 0.850, 0.596]),
            c("resource", "Internal resource", "compute", [0.653, 0.650, 0.820, 0.721]),
            c("iam", "IAM", "identity_provider", [0.610, 0.878, 0.760, 0.945]),
            c("logging", "Logging", "monitoring", [0.788, 0.878, 0.938, 0.945]),
        ], [
            f("gcp-1", "internet", "load_balancer"), f("gcp-2", "armor", "load_balancer"),
            f("gcp-3", "load_balancer", "cloud_run"), f("gcp-4", "cloud_run", "vpc_connector"),
            f("gcp-5", "vpc_connector", "firewall"), f("gcp-6", "firewall", "resource"),
        ], [
            {"id": "service-project", "name": "Service project", "componentIds": ["armor", "load_balancer", "cloud_run", "vpc_connector"]},
            {"id": "security-project", "name": "Security project", "componentIds": ["artifact_registry", "kms", "secret_manager"]},
            {"id": "host-project", "name": "Host project", "componentIds": ["firewall", "resource"]},
        ]),
        e("generic-cloud-api", "generic", "current_arch_test_0000", "development_tuning", "dataset/hybrid_v2/images/test/current_arch_test_0000.jpg", [
            c("user", "User", "user", [0.47, 0.04, 0.56, 0.13]), c("internet", "Internet", "internet", [0.02, 0.27, 0.14, 0.35]),
            c("cdn", "CDN", "cdn", [0.44, 0.24, 0.56, 0.35]), c("api", "API Gateway", "api_gateway", [0.86, 0.24, 0.98, 0.35]),
            c("compute", "Compute", "compute", [0.02, 0.45, 0.14, 0.55]), c("database", "Database", "database", [0.44, 0.45, 0.56, 0.57]),
            c("storage", "Storage", "storage", [0.86, 0.45, 0.98, 0.55]), c("monitoring", "Monitoring", "monitoring", [0.44, 0.66, 0.56, 0.76]),
        ], [
            f("generic-1", "user", "internet"), f("generic-2", "internet", "cdn"), f("generic-3", "cdn", "api"),
            f("generic-4", "compute", "api"), f("generic-5", "compute", "database"), f("generic-6", "database", "storage"),
            f("generic-7", "monitoring", "storage"),
        ]),
        e("aws-serverless-async", "aws", "aws_amazon_elastic_container_service_0001", "development_tuning", "dataset/raw_kaggle_selected/aws_amazon_elastic_container_service_0001_aug_3.png", [
            c("api", "API Gateway", "api_gateway", [0.408, 0.105, 0.490, 0.195]), c("waf", "AWS WAF", "waf", [0.444, 0.092, 0.496, 0.151]),
            c("cognito", "Cognito Authorizer", "identity_provider", [0.420, 0.300, 0.490, 0.390]),
            c("search_handler", "OpenSearch Handler", "compute", [0.295, 0.455, 0.360, 0.555]), c("api_handler", "API Handler", "compute", [0.552, 0.446, 0.617, 0.548]),
            c("queue", "SQS Queue", "queue", [0.895, 0.484, 0.963, 0.584]), c("worker", "Worker", "compute", [0.756, 0.586, 0.822, 0.685]),
            c("fargate", "ECS Fargate", "compute", [0.758, 0.822, 0.838, 0.936]), c("database", "Aurora Serverless Metadata DB", "database", [0.570, 0.827, 0.640, 0.936]),
            c("catalog", "OpenSearch Catalog", "storage", [0.327, 0.844, 0.396, 0.954]), c("cloudwatch", "CloudWatch", "monitoring", [0.101, 0.466, 0.171, 0.572]),
        ], [
            f("async-1", "api", "cognito"), f("async-2", "cognito", "search_handler"), f("async-3", "cognito", "api_handler"),
            f("async-4", "api_handler", "queue"), f("async-5", "queue", "worker"), f("async-6", "worker", "fargate"),
            f("async-7", "fargate", "database"), f("async-8", "api_handler", "database"), f("async-9", "search_handler", "catalog"),
        ], [{"id": "vpc", "name": "VPC private subnet", "componentIds": ["cognito", "search_handler", "api_handler", "queue", "worker", "fargate", "database", "catalog", "cloudwatch"]}]),
        e("aws-eks-platform", "aws", "aws_amazon_elastic_kubernetes_service_0005", "development_tuning", "dataset/raw_kaggle_selected/aws_amazon_elastic_kubernetes_service_0005_aug_4.png", [
            c("warehouse", "Data Warehouse", "database", [0.055, 0.250, 0.145, 0.390]), c("sql", "SQL Database", "database", [0.055, 0.440, 0.145, 0.570]),
            c("external", "External Services", "compute", [0.055, 0.710, 0.145, 0.840]), c("sagemaker", "AWS SageMaker", "compute", [0.345, 0.150, 0.445, 0.290]),
            c("comprehend", "AWS Comprehend", "compute", [0.345, 0.315, 0.445, 0.420]), c("notebook", "Notebook", "compute", [0.345, 0.440, 0.445, 0.570]),
            c("raw", "Raw Data", "storage", [0.340, 0.710, 0.445, 0.845]), c("processed", "Processed Data", "storage", [0.480, 0.710, 0.585, 0.845]),
            c("lambda", "Functions", "compute", [0.590, 0.215, 0.675, 0.330]), c("microservices", "Microservices", "compute", [0.590, 0.365, 0.675, 0.480]),
            c("glue", "Glue ETL", "compute", [0.590, 0.520, 0.675, 0.635]), c("dynamo", "DynamoDB", "database", [0.740, 0.710, 0.835, 0.845]),
            c("rds", "RDS", "database", [0.850, 0.710, 0.945, 0.845]), c("visualization", "Visualization", "monitoring", [0.825, 0.155, 0.920, 0.290]),
        ], [
            f("eks-1", "warehouse", "sagemaker"), f("eks-2", "sql", "sagemaker"), f("eks-3", "sagemaker", "raw"),
            f("eks-4", "notebook", "raw"), f("eks-5", "raw", "glue"), f("eks-6", "glue", "processed"),
            f("eks-7", "lambda", "microservices"), f("eks-8", "microservices", "dynamo"), f("eks-9", "microservices", "rds"),
            f("eks-10", "rds", "visualization"),
        ]),
        e("azure-private-ai-platform", "azure", "aws_amazon_rds_0005", "development_tuning", "dataset/raw_kaggle_selected/aws_amazon_rds_0005_aug_0.png", [
            c("user", "User", "user", [0.035, 0.410, 0.070, 0.455]), c("app_gateway", "Application Gateway with WAF", "waf", [0.155, 0.405, 0.220, 0.500]),
            c("app_service", "App Service", "compute", [0.210, 0.655, 0.330, 0.780]), c("key_vault", "Azure Key Vault", "secrets_kms", [0.335, 0.655, 0.390, 0.765]),
            c("storage", "Azure Storage", "storage", [0.405, 0.655, 0.455, 0.765]), c("firewall", "Azure Firewall", "waf", [0.650, 0.385, 0.705, 0.465]),
            c("bastion", "Azure Bastion", "compute", [0.735, 0.385, 0.795, 0.470]), c("build_agents", "Build agents", "compute", [0.820, 0.385, 0.875, 0.470]),
            c("ai_search", "Azure AI Search", "storage", [0.545, 0.655, 0.610, 0.765]), c("cosmos", "Azure Cosmos DB", "database", [0.620, 0.655, 0.680, 0.765]),
            c("foundry_agent", "Foundry Agent Service", "compute", [0.915, 0.310, 0.965, 0.400]), c("openai", "Azure OpenAI model", "compute", [0.915, 0.455, 0.965, 0.560]),
        ], [
            f("ai-1", "user", "app_gateway"), f("ai-2", "app_gateway", "app_service"), f("ai-3", "app_service", "key_vault"),
            f("ai-4", "app_service", "storage"), f("ai-5", "app_service", "ai_search"), f("ai-6", "app_service", "cosmos"),
            f("ai-7", "app_service", "foundry_agent"), f("ai-8", "foundry_agent", "openai"),
        ]),
        e("azure-hub-spoke", "azure", "gcp_google_kubernetes_engine_0004", "development_tuning", "dataset/raw_kaggle_selected/gcp_google_kubernetes_engine_0004_aug_2.png", [
            c("onprem", "Cross-premises network", "internet", [0.025, 0.300, 0.175, 0.610]), c("bastion", "Azure Bastion", "compute", [0.245, 0.120, 0.345, 0.230]),
            c("firewall", "Azure Firewall", "waf", [0.245, 0.310, 0.345, 0.430]), c("gateway", "VPN Gateway", "api_gateway", [0.245, 0.500, 0.345, 0.620]),
            c("prod_vm", "Production virtual machines", "compute", [0.690, 0.130, 0.940, 0.270]), c("prod2_vm", "Production virtual machines 2", "compute", [0.690, 0.330, 0.940, 0.470]),
            c("nonprod_vm", "Non-production virtual machines", "compute", [0.450, 0.650, 0.650, 0.840]), c("nonprod2_vm", "Non-production virtual machines 2", "compute", [0.720, 0.650, 0.940, 0.840]),
        ], [
            f("hub-1", "onprem", "gateway"), f("hub-2", "gateway", "firewall"), f("hub-3", "firewall", "prod_vm"),
            f("hub-4", "firewall", "prod2_vm"), f("hub-5", "gateway", "nonprod_vm"), f("hub-6", "gateway", "nonprod2_vm"),
        ]),
        e("aws-notification-platform", "aws", "aws_amazon_simple_notification_service_0008", "blind_holdout", "dataset/kaggle_curated_unique/images/test/kaggle_aws_amazon_simple_notification_service_0008_aug_7.png", [
            c("s3", "Amazon S3", "storage", [0.315, 0.330, 0.405, 0.440]), c("lambda", "AWS Lambda", "compute", [0.315, 0.155, 0.405, 0.260]),
            c("ground_truth", "SageMaker Ground Truth", "compute", [0.535, 0.135, 0.650, 0.260]), c("training", "SageMaker Deep Learning Training", "compute", [0.750, 0.125, 0.870, 0.250]),
            c("model_a", "SageMaker Model", "compute", [0.770, 0.340, 0.875, 0.455]), c("model_b", "SageMaker Model Endpoint", "compute", [0.760, 0.655, 0.875, 0.770]),
        ], [
            f("notify-1", "s3", "lambda"), f("notify-2", "lambda", "ground_truth"), f("notify-3", "ground_truth", "training"),
            f("notify-4", "training", "model_a"), f("notify-5", "model_a", "model_b"),
        ]),
        e("aws-network-load-balancer", "aws", "aws_elastic_load_balancing_network_load_balancer_0004", "blind_holdout", "dataset/kaggle_curated_unique/images/test/kaggle_aws_elastic_load_balancing_network_load_balancer_0004_aug_7.png", [
            c("sources", "Data Sources", "internet", [0.020, 0.420, 0.105, 0.720]), c("ingestion", "Data Ingestion", "queue", [0.115, 0.430, 0.185, 0.720]),
            c("processing", "Data Processing", "compute", [0.220, 0.180, 0.500, 0.670]), c("data_lake", "Data Lake", "storage", [0.225, 0.690, 0.500, 0.875]),
            c("profiles", "Unified Customer Profile", "database", [0.535, 0.170, 0.650, 0.410]), c("activation", "Activation", "compute", [0.670, 0.170, 0.800, 0.410]),
            c("analytics", "Analytics", "monitoring", [0.535, 0.470, 0.805, 0.820]), c("consumers", "Consumers", "user", [0.865, 0.160, 0.975, 0.800]),
        ], [
            f("nlb-1", "sources", "ingestion"), f("nlb-2", "ingestion", "processing"), f("nlb-3", "processing", "data_lake"),
            f("nlb-4", "data_lake", "profiles"), f("nlb-5", "profiles", "activation"), f("nlb-6", "activation", "consumers"),
            f("nlb-7", "data_lake", "analytics"), f("nlb-8", "analytics", "consumers"),
        ]),
        e("azure-kubernetes", "azure", "azure_kubernetes_services_0003", "blind_holdout", "dataset/kaggle_curated_unique/images/test/kaggle_azure_kubernetes_services_0003_aug_7.png", [
            c("users", "Users", "user", [0.025, 0.370, 0.095, 0.470]), c("front_door", "Azure Front Door", "cdn", [0.200, 0.355, 0.285, 0.455]),
            c("app_gateway", "Application Gateway", "api_gateway", [0.325, 0.355, 0.410, 0.455]), c("aks", "Azure Kubernetes Service", "compute", [0.455, 0.330, 0.590, 0.500]),
            c("openai", "Azure OpenAI", "compute", [0.660, 0.300, 0.750, 0.410]), c("cosmos", "Azure Cosmos DB", "database", [0.660, 0.490, 0.750, 0.600]),
            c("storage", "Azure Storage", "storage", [0.660, 0.640, 0.750, 0.750]), c("key_vault", "Key Vault", "secrets_kms", [0.280, 0.650, 0.360, 0.760]),
            c("monitor", "Azure Monitor", "monitoring", [0.455, 0.650, 0.555, 0.760]),
        ], [
            f("aks-1", "users", "front_door"), f("aks-2", "front_door", "app_gateway"), f("aks-3", "app_gateway", "aks"),
            f("aks-4", "aks", "openai"), f("aks-5", "aks", "cosmos"), f("aks-6", "aks", "storage"),
            f("aks-7", "aks", "key_vault"), f("aks-8", "aks", "monitor"),
        ]),
        e("gcp-cicd-gke", "gcp", "google_cloud_official_cicd_gke", "blind_holdout", "data/benchmarks/real-architecture/images/gcp-cicd-gke.png", [
            c("github", "GitHub", "storage", [0.000, 0.130, 0.115, 0.220]), c("developer", "Developer", "user", [0.000, 0.400, 0.115, 0.490]),
            c("source", "Cloud Source Repositories", "storage", [0.200, 0.090, 0.340, 0.255]), c("develop", "Cloud Code", "compute", [0.200, 0.360, 0.340, 0.530]),
            c("dev_cluster", "Development Cluster", "compute", [0.200, 0.560, 0.340, 0.725]), c("ci", "Cloud Build", "compute", [0.380, 0.360, 0.520, 0.530]),
            c("build_artifacts", "Build Artifacts", "storage", [0.535, 0.090, 0.675, 0.255]), c("cd", "Cloud Deploy", "compute", [0.535, 0.360, 0.675, 0.530]),
            c("deploy_artifacts", "Deploy Artifacts", "storage", [0.690, 0.090, 0.830, 0.255]), c("staging", "Staging Cluster", "compute", [0.535, 0.560, 0.675, 0.725]),
            c("production", "Production Cluster", "compute", [0.690, 0.560, 0.830, 0.725]), c("container", "Application Container", "storage", [0.535, 0.760, 0.675, 0.925]),
            c("operations", "Operations Approval", "user", [0.865, 0.600, 0.985, 0.690]),
        ], [
            f("cicd-1", "github", "source"), f("cicd-2", "developer", "develop"), f("cicd-3", "develop", "source"),
            f("cicd-4", "develop", "dev_cluster"), f("cicd-5", "source", "ci"), f("cicd-6", "ci", "build_artifacts"),
            f("cicd-7", "ci", "cd"), f("cicd-8", "cd", "staging"), f("cicd-9", "cd", "deploy_artifacts"),
            f("cicd-10", "operations", "production"), f("cicd-11", "container", "staging"), f("cicd-12", "container", "production"),
        ], [{"id": "gcp", "name": "Google Cloud", "componentIds": ["source", "develop", "dev_cluster", "ci", "build_artifacts", "cd", "deploy_artifacts", "staging", "production", "container"]}]),
        e("fiap-aws-multiaz", "aws", "fiap_architecture_1", "blind_holdout", "data/benchmarks/real-architecture/images/fiap-architecture-1.png", [
            c("users", "Usuarios SEI", "user", [0.040, 0.045, 0.130, 0.105]), c("shield", "AWS Shield", "waf", [0.230, 0.045, 0.300, 0.115]),
            c("cloudfront", "Amazon CloudFront", "cdn", [0.345, 0.045, 0.420, 0.115]), c("waf", "AWS WAF", "waf", [0.460, 0.045, 0.530, 0.115]),
            c("alb_a", "Application Load Balancer A", "load_balancer", [0.170, 0.245, 0.260, 0.330]), c("alb_b", "Application Load Balancer B", "load_balancer", [0.405, 0.245, 0.495, 0.330]),
            c("alb_c", "Application Load Balancer C", "load_balancer", [0.635, 0.245, 0.725, 0.330]), c("compute_a", "SEI/SIP A", "compute", [0.190, 0.415, 0.275, 0.505]),
            c("compute_b", "SEI/SIP B", "compute", [0.420, 0.415, 0.505, 0.505]), c("compute_c", "SEI/SIP C", "compute", [0.650, 0.415, 0.735, 0.505]),
            c("storage", "Amazon EFS", "storage", [0.135, 0.635, 0.230, 0.725]), c("database", "Amazon RDS", "database", [0.330, 0.635, 0.425, 0.725]),
            c("cache", "Amazon ElastiCache", "database", [0.520, 0.635, 0.615, 0.725]), c("cloudtrail", "AWS CloudTrail", "monitoring", [0.805, 0.190, 0.900, 0.270]),
            c("kms", "AWS KMS", "secrets_kms", [0.805, 0.300, 0.900, 0.380]), c("backup", "AWS Backup", "backup", [0.805, 0.410, 0.900, 0.490]),
            c("cloudwatch", "Amazon CloudWatch", "monitoring", [0.805, 0.520, 0.900, 0.600]),
        ], [
            f("fiap-aws-1", "users", "shield"), f("fiap-aws-2", "shield", "cloudfront"), f("fiap-aws-3", "cloudfront", "waf"),
            f("fiap-aws-4", "waf", "alb_a"), f("fiap-aws-5", "waf", "alb_b"), f("fiap-aws-6", "waf", "alb_c"),
            f("fiap-aws-7", "alb_a", "compute_a"), f("fiap-aws-8", "alb_b", "compute_b"), f("fiap-aws-9", "alb_c", "compute_c"),
            f("fiap-aws-10", "compute_a", "storage"), f("fiap-aws-11", "compute_b", "database"), f("fiap-aws-12", "compute_c", "cache"),
        ], [{"id": "vpc", "name": "AWS VPC", "componentIds": ["alb_a", "alb_b", "alb_c", "compute_a", "compute_b", "compute_c", "storage", "database", "cache"]}]),
        e("fiap-azure-integration", "azure", "fiap_architecture_2", "blind_holdout", "data/benchmarks/real-architecture/images/fiap-architecture-2.png", [
            c("entra", "Microsoft Entra", "identity_provider", [0.055, 0.035, 0.135, 0.115]), c("internet", "Internet", "internet", [0.055, 0.245, 0.135, 0.325]),
            c("user", "API Consumer", "user", [0.055, 0.520, 0.135, 0.610]), c("gateway", "API Gateway", "api_gateway", [0.300, 0.305, 0.390, 0.400]),
            c("portal", "Developer Portal", "compute", [0.300, 0.600, 0.390, 0.690]), c("logic", "Logic Apps", "compute", [0.505, 0.305, 0.595, 0.400]),
            c("azure_services", "Azure Services", "compute", [0.760, 0.230, 0.880, 0.330]), c("saas", "SaaS Services", "compute", [0.760, 0.380, 0.880, 0.480]),
            c("rest", "REST Services", "api_gateway", [0.760, 0.550, 0.880, 0.650]), c("soap", "SOAP Services", "api_gateway", [0.760, 0.700, 0.880, 0.800]),
        ], [
            f("fiap-az-1", "user", "internet"), f("fiap-az-2", "internet", "gateway"), f("fiap-az-3", "entra", "gateway"),
            f("fiap-az-4", "gateway", "logic"), f("fiap-az-5", "gateway", "portal"), f("fiap-az-6", "logic", "azure_services"),
            f("fiap-az-7", "logic", "saas"), f("fiap-az-8", "logic", "rest"), f("fiap-az-9", "logic", "soap"),
        ], [{"id": "resource-group", "name": "Resource group", "componentIds": ["gateway", "portal", "logic"]}], [
            {"flowId": "fiap-az-2", "value": "HTTP", "evidenceText": "HTTP"}
        ]),
    ]


def main() -> None:
    base = json.loads(BASE.read_text(encoding="utf-8"))
    previous = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.is_file() else {}
    base_entries = []
    for original in base["entries"]:
        original["split"] = "development_tuning"
        original["annotationStatus"] = "human_verified"
        image_path = ROOT / original["image"]
        original["imageSha256"] = hashlib.sha256(image_path.read_bytes()).hexdigest()
        base_entries.append(attach_flow_protocols(original))
    entries = base_entries + additions()
    benchmark = {
        "schemaVersion": "2.0",
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "sealedAt": previous.get("sealedAt") or datetime.now(timezone.utc).isoformat(),
        "annotationMethod": "Manual review of visible primary nodes, directed flows, explicit protocols, and trust-zone membership.",
        "selectionPolicy": "One primary diagram per source group; provider-corrected labels; no augmented icons treated as ground truth.",
        "splitPolicy": "development_tuning may guide fixes; blind_holdout is evaluated only by the final end-to-end command.",
        "imageCount": len(entries),
        "splitCounts": {
            split: sum(item["split"] == split for item in entries)
            for split in ("development_tuning", "blind_holdout")
        },
        "providers": sorted({item["provider"] for item in entries}),
        "entries": entries,
    }
    OUTPUT.write_text(json.dumps(benchmark, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"Built {len(entries)} entries at {OUTPUT}")


if __name__ == "__main__":
    main()
