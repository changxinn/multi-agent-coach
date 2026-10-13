"""Structural safety checks for the staging v2 CloudFormation template."""

from pathlib import Path

import yaml


class CloudFormationLoader(yaml.SafeLoader):
    """Parse CloudFormation intrinsic tags without evaluating them."""


def _intrinsic(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {tag_suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {tag_suffix: loader.construct_sequence(node)}
    return {tag_suffix: loader.construct_mapping(node)}


CloudFormationLoader.add_multi_constructor("!", _intrinsic)


def _template():
    path = Path(__file__).parents[1] / "infrastructure/cloudformation/staging-v2.yaml"
    return yaml.load(path.read_text(), Loader=CloudFormationLoader)


def _frontend_template():
    path = Path(__file__).parents[1] / "infrastructure/cloudformation/frontend.yaml"
    return yaml.load(path.read_text(), Loader=CloudFormationLoader)


def _legacy_staging_template():
    path = Path(__file__).parents[1] / "infrastructure/cloudformation/staging.yaml"
    return yaml.load(path.read_text(), Loader=CloudFormationLoader)


def _environment(task):
    return task["Properties"]["ContainerDefinitions"][0].get("Environment", [])


def _secrets(task):
    return task["Properties"]["ContainerDefinitions"][0].get("Secrets", [])


def test_v2_redis_is_private_tls_authenticated_multi_az_with_failover():
    template = _template()
    resources = template["Resources"]

    assert resources["RedisSubnets"]["Type"] == "AWS::ElastiCache::SubnetGroup"
    assert resources["Redis"]["Type"] == "AWS::ElastiCache::ReplicationGroup"
    assert (
        resources["Redis"]["Properties"].items()
        >= {
            "Engine": "redis",
            "NumCacheClusters": 2,
            "AutomaticFailoverEnabled": True,
            "MultiAZEnabled": True,
            "AtRestEncryptionEnabled": True,
            "TransitEncryptionEnabled": True,
        }.items()
    )
    assert resources["RedisSg"]["Properties"]["SecurityGroupIngress"] == [
        {
            "IpProtocol": "tcp",
            "FromPort": 6379,
            "ToPort": 6379,
            "SourceSecurityGroupId": {"Ref": "TaskSg"},
        }
    ]
    assert _template()["Outputs"]["RedisReaderEndpoint"]["Value"] == {
        "GetAtt": "Redis.ReaderEndPoint.Address"
    }
    assert "RedisAuthToken" not in resources
    assert template["Parameters"]["RedisAuthTokenSecretArn"]["Type"] == "String"
    assert resources["Redis"]["Properties"]["AuthToken"] == {
        "Sub": "{{resolve:secretsmanager:${RedisAuthTokenSecretArn}:SecretString:password}}"
    }


def test_v2_injects_redis_url_only_into_api_and_scales_api_by_parameter():
    resources = _template()["Resources"]
    api_environment = _environment(resources["ApiTask"])

    redis_url = next(item for item in api_environment if item["Name"] == "REDIS_URL")
    assert "rediss://" in redis_url["Value"]["Sub"]
    assert "Redis.PrimaryEndPoint.Address" in redis_url["Value"]["Sub"]
    assert (
        "${RedisAuthTokenSecretArn}:SecretString:password" in redis_url["Value"]["Sub"]
    )
    for task_name in [
        "BootstrapTask",
        "ApiMigration",
        "RecoveryMigration",
        "NutritionMigration",
        "TrainingMigration",
        "RecoveryTask",
        "NutritionTask",
        "TrainingTask",
        "HeadCoachTask",
        "SummarizerTask",
    ]:
        assert all(
            item["Name"] != "REDIS_URL" for item in _environment(resources[task_name])
        )

    assert _template()["Parameters"]["ApiDesiredCount"]["Default"] == 2
    assert resources["ApiService"]["Properties"]["DesiredCount"] == {
        "Ref": "ApiDesiredCount"
    }


def test_v2_configures_the_compatibility_reviewer_only_for_the_api():
    resources = _template()["Resources"]
    api_environment = _environment(resources["ApiTask"])

    assert next(
        item
        for item in api_environment
        if item["Name"] == "NUTRITION_COMPATIBILITY_ADMIN_EMAIL"
    ) == {
        "Name": "NUTRITION_COMPATIBILITY_ADMIN_EMAIL",
        "Value": "nutrition.admin@example.com",
    }

    for task_name in [
        "BootstrapTask",
        "ApiMigration",
        "RecoveryMigration",
        "NutritionMigration",
        "TrainingMigration",
        "RecoveryTask",
        "NutritionTask",
        "TrainingTask",
        "HeadCoachTask",
        "SummarizerTask",
    ]:
        assert all(
            item["Name"] != "NUTRITION_COMPATIBILITY_ADMIN_EMAIL"
            for item in _environment(resources[task_name])
        )


def test_v2_api_migration_injects_required_application_settings():
    api_migration_secrets = _secrets(_template()["Resources"]["ApiMigration"])

    assert {secret["Name"] for secret in api_migration_secrets if "Name" in secret} >= {
        "DATABASE_URL",
        "JWT_SECRET_KEY",
        "OPENAI_API_KEY",
    }


def test_demo_password_is_not_stored_in_cloudformation_or_service_tasks():
    template = _template()
    resources = template["Resources"]
    assert "SeedDemoUsers" not in template["Parameters"]
    assert "DemoPasswordSecretArn" not in template["Parameters"]
    assert "DemoPasswordReadPolicy" not in resources
    assert _environment(resources["ApiMigration"]) == []
    assert all(
        item["Name"] != "SEED_DEMO_USERS" for item in _environment(resources["ApiTask"])
    )
    assert all(
        item["Name"] != "DEMO_USER_PASSWORD" for item in _secrets(resources["ApiTask"])
    )


def test_frontend_forwards_api_query_strings_without_caching_them():
    resources = _frontend_template()["Resources"]
    no_cache_policy = resources["NoCachePolicy"]["Properties"]["CachePolicyConfig"]
    no_cache_parameters = no_cache_policy["ParametersInCacheKeyAndForwardedToOrigin"]
    no_cache_query_strings = no_cache_parameters["QueryStringsConfig"]
    origin_query_strings = resources["ApiOriginRequestPolicy"]["Properties"][
        "OriginRequestPolicyConfig"
    ]["QueryStringsConfig"]

    assert {no_cache_policy[ttl] for ttl in ("DefaultTTL", "MaxTTL", "MinTTL")} == {0}
    assert no_cache_parameters["EnableAcceptEncodingBrotli"] is False
    assert no_cache_parameters["EnableAcceptEncodingGzip"] is False
    assert no_cache_query_strings == {"QueryStringBehavior": "none"}
    assert origin_query_strings == {"QueryStringBehavior": "all"}


def test_frontend_and_cloudfront_access_logs_are_private_and_retained():
    resources = _frontend_template()["Resources"]

    frontend_bucket = resources["FrontendBucket"]["Properties"]
    log_bucket = resources["AccessLogBucket"]["Properties"]
    distribution = resources["Distribution"]["Properties"]["DistributionConfig"]

    assert frontend_bucket["VersioningConfiguration"] == {"Status": "Enabled"}
    assert frontend_bucket["LoggingConfiguration"] == {
        "DestinationBucketName": {"Ref": "AccessLogBucket"},
        "LogFilePrefix": "frontend-s3/",
    }
    assert log_bucket["PublicAccessBlockConfiguration"]["RestrictPublicBuckets"] is True
    assert log_bucket["LifecycleConfiguration"]["Rules"] == [
        {"Id": "ExpireAccessLogs", "Status": "Enabled", "ExpirationInDays": 90}
    ]
    assert distribution["Logging"] == {
        "Bucket": {"GetAtt": "AccessLogBucket.DomainName"},
        "Prefix": "cloudfront/",
        "IncludeCookies": False,
    }


def test_v2_alb_preserves_explicit_type_and_waits_for_access_log_permissions():
    alb = _template()["Resources"]["Alb"]

    # Removing this replacement-sensitive property can replace an existing ALB,
    # even though application is also the default for newly created resources.
    assert alb["Properties"]["Type"] == "application"
    assert alb["DependsOn"] == "AlbAccessLogBucketPolicy"


def test_v2_alb_writes_access_logs_to_a_private_retained_bucket():
    resources = _template()["Resources"]
    bucket = resources["AlbAccessLogBucket"]["Properties"]
    attributes = resources["Alb"]["Properties"]["LoadBalancerAttributes"]

    assert bucket["PublicAccessBlockConfiguration"]["RestrictPublicBuckets"] is True
    assert bucket["LifecycleConfiguration"]["Rules"] == [
        {"Id": "ExpireAlbAccessLogs", "Status": "Enabled", "ExpirationInDays": 90}
    ]
    assert attributes == [
        {"Key": "access_logs.s3.enabled", "Value": "true"},
        {"Key": "access_logs.s3.bucket", "Value": {"Ref": "AlbAccessLogBucket"}},
        {"Key": "access_logs.s3.prefix", "Value": "alb"},
    ]
    statement = resources["AlbAccessLogBucketPolicy"]["Properties"]["PolicyDocument"][
        "Statement"
    ][0]
    assert statement["Principal"] == {
        "Service": "logdelivery.elasticloadbalancing.amazonaws.com"
    }
    assert statement["Action"] == "s3:PutObject"
    deny_statement = resources["AlbAccessLogBucketPolicy"]["Properties"][
        "PolicyDocument"
    ]["Statement"][1]
    assert deny_statement["Condition"] == {"Bool": {"aws:SecureTransport": False}}
    assert bucket["VersioningConfiguration"]["Status"] == "Enabled"


def test_frontend_buckets_enforce_https_and_retain_access_log_versions():
    resources = _frontend_template()["Resources"]

    assert resources["AccessLogBucket"]["Properties"]["VersioningConfiguration"] == {
        "Status": "Enabled"
    }
    for policy_name, bucket_name in (
        ("FrontendBucketPolicy", "FrontendBucket"),
        ("AccessLogBucketPolicy", "AccessLogBucket"),
    ):
        statements = resources[policy_name]["Properties"]["PolicyDocument"]["Statement"]
        deny_statement = next(
            statement
            for statement in statements
            if statement.get("Sid") == "DenyInsecureTransport"
        )
        assert deny_statement["Condition"] == {"Bool": {"aws:SecureTransport": False}}
        assert {"GetAtt": f"{bucket_name}.Arn"} in deny_statement["Resource"]


def test_legacy_staging_alb_writes_access_logs_to_a_private_retained_bucket():
    resources = _legacy_staging_template()["Resources"]
    bucket = resources["AlbAccessLogBucket"]["Properties"]
    attributes = resources["LoadBalancer"]["Properties"]["LoadBalancerAttributes"]

    assert bucket["PublicAccessBlockConfiguration"]["RestrictPublicBuckets"] is True
    assert bucket["LifecycleConfiguration"]["Rules"] == [
        {"Id": "ExpireAlbAccessLogs", "Status": "Enabled", "ExpirationInDays": 90}
    ]
    assert attributes == [
        {"Key": "access_logs.s3.enabled", "Value": "true"},
        {"Key": "access_logs.s3.bucket", "Value": {"Ref": "AlbAccessLogBucket"}},
        {"Key": "access_logs.s3.prefix", "Value": "alb"},
    ]
    statement = resources["AlbAccessLogBucketPolicy"]["Properties"]["PolicyDocument"][
        "Statement"
    ][0]
    assert statement["Principal"] == {
        "Service": "logdelivery.elasticloadbalancing.amazonaws.com"
    }
    assert statement["Action"] == "s3:PutObject"
    deny_statement = resources["AlbAccessLogBucketPolicy"]["Properties"][
        "PolicyDocument"
    ]["Statement"][1]
    assert deny_statement["Condition"] == {"Bool": {"aws:SecureTransport": False}}
    assert bucket["VersioningConfiguration"]["Status"] == "Enabled"


def test_legacy_alert_topic_uses_aws_managed_sns_encryption():
    alerts = _legacy_staging_template()["Resources"]["Alerts"]

    assert alerts["Properties"]["KmsMasterKeyId"] == "alias/aws/sns"


def test_v2_frontend_is_an_ecs_service_and_alb_routes_api_by_path():
    template = _template()
    resources = template["Resources"]

    assert "FrontendImage" in template["Parameters"]
    assert (
        resources["FrontendTarget"]["Properties"].items()
        >= {
            "Port": 5174,
            "TargetType": "ip",
            "HealthCheckPath": "/",
        }.items()
    )
    assert resources["HttpsListener"]["Properties"]["DefaultActions"] == [
        {"Type": "forward", "TargetGroupArn": {"Ref": "FrontendTarget"}}
    ]
    assert resources["ApiListenerRule"]["Properties"]["Conditions"] == [
        {"Field": "path-pattern", "Values": ["/api", "/api/*"]}
    ]
    assert resources["FrontendService"]["Properties"]["LoadBalancers"] == [
        {
            "ContainerName": "frontend",
            "ContainerPort": 5174,
            "TargetGroupArn": {"Ref": "FrontendTarget"},
        }
    ]
    assert template["Outputs"]["FrontendUrl"]["Value"] == {
        "Sub": "https://${ApplicationDomainName}"
    }
    assert template["Outputs"]["ApiHealthUrl"]["Value"] == {
        "Sub": "https://${ApplicationDomainName}/api/health"
    }


def test_v2_https_terminates_at_alb_and_http_cannot_bypass_redirect():
    template = _template()
    resources = template["Resources"]
    https = resources["HttpsListener"]["Properties"]
    assert https["LoadBalancerArn"] == {"Ref": "Alb"}
    assert https["Port"] == 443
    assert https["Protocol"] == "HTTPS"
    assert https["SslPolicy"] == "ELBSecurityPolicy-TLS13-1-2-2021-06"
    assert https["Certificates"] == [{"CertificateArn": {"Ref": "AlbCertificateArn"}}]
    assert resources["ApiListenerRule"]["Properties"]["ListenerArn"] == {
        "Ref": "HttpsListener"
    }
    assert resources["Listener"]["DependsOn"] == "ApiListenerRule"
    assert resources["Listener"]["Properties"]["DefaultActions"] == [
        {
            "Type": "redirect",
            "RedirectConfig": {
                "Protocol": "HTTPS",
                "Port": "443",
                "Host": {"Ref": "ApplicationDomainName"},
                "Path": "/#{path}",
                "Query": "#{query}",
                "StatusCode": "HTTP_301",
            },
        }
    ]
    for resource in resources.values():
        if resource["Type"] == "AWS::ElasticLoadBalancingV2::ListenerRule":
            assert resource["Properties"]["ListenerArn"] != {"Ref": "Listener"}
    ingress = resources["AlbSg"]["Properties"]["SecurityGroupIngress"]
    assert {rule["FromPort"] for rule in ingress} == {80, 443}
    for target in ("FrontendTarget", "ApiTarget"):
        assert resources[target]["Properties"]["Protocol"] == "HTTP"


def test_v2_https_parameters_reject_urls_and_empty_certificates():
    import re

    parameters = _template()["Parameters"]
    domain_pattern = parameters["ApplicationDomainName"]["AllowedPattern"]
    assert re.fullmatch(domain_pattern, "app.mafitnesscoach.website")
    for invalid in ("", "https://app.mafitnesscoach.website", "app.example.com/api"):
        assert not re.fullmatch(domain_pattern, invalid)
    certificate_pattern = parameters["AlbCertificateArn"]["AllowedPattern"]
    assert re.fullmatch(
        certificate_pattern,
        "arn:aws:acm:ap-southeast-1:758248541054:certificate/3847778d-c077-48c5-85a1-16586b495eab",
    )
    assert not re.fullmatch(certificate_pattern, "")
