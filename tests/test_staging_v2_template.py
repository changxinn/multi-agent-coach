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


def test_v2_api_migration_injects_required_application_settings():
    api_migration_secrets = _secrets(_template()["Resources"]["ApiMigration"])

    assert {secret["Name"] for secret in api_migration_secrets} >= {
        "DATABASE_URL",
        "JWT_SECRET_KEY",
        "OPENAI_API_KEY",
    }


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
    assert resources["Listener"]["Properties"]["DefaultActions"] == [
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
        "Sub": "http://${Alb.DNSName}"
    }
    assert template["Outputs"]["ApiHealthUrl"]["Value"] == {
        "Sub": "http://${Alb.DNSName}/api/health"
    }
