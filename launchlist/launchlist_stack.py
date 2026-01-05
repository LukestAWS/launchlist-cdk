from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct

class LaunchlistStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # --- Static Site Logic ---
        bucket = s3.Bucket(self, "SiteBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        distribution = cloudfront.Distribution(self, "SiteDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            default_root_object="index.html",
        )

        bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                resources=[bucket.arn_for_objects("*")],
                conditions={"StringEquals": {"AWS:SourceArn": distribution.distribution_arn}},
            )
        )

        s3deploy.BucketDeployment(self, "DeploySite",
            sources=[s3deploy.Source.asset("./assets")],
            destination_bucket=bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        # --- Backend Logic (Moved from __init__.py) ---
        # DynamoDB single-table
        table = dynamodb.Table(self, "LaunchlistTable",
            partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Lambda function for subscribe
        subscribe_lambda = _lambda.Function(self, "SubscribeHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.main",
            code=_lambda.Code.from_asset("lambda"), # Ensure handler.py is in a /lambda folder
            environment={
                "TABLE_NAME": table.table_name,
            },
        )

        table.grant_write_data(subscribe_lambda)

        # API Gateway
        api = apigw.RestApi(self, "LaunchlistApi",
            rest_api_name="LaunchList API",
        )

        subscribe_integration = apigw.LambdaIntegration(subscribe_lambda)
        api.root.add_resource("subscribe").add_method("POST", subscribe_integration)

        # Outputs
        CfnOutput(self, "SiteURL", value=distribution.distribution_domain_name)
        CfnOutput(self, "ApiUrl", value=api.url)