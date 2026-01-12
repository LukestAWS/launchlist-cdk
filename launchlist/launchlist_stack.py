from aws_cdk import (
    Stack,
    aws_cognito as cognito,
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

        # 1. --- Static Site ---
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

        # 2. --- Cognito (Moved UP to fix UnboundLocalError) ---
        user_pool = cognito.UserPool(self, "LaunchlistUserPool",
            user_pool_name="LaunchlistUserPool",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            removal_policy=RemovalPolicy.DESTROY,
        )
        # Cognito Domain (for Hosted UI)
        cognito_domain = user_pool.add_domain("LaunchlistDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix="mlukest-launchlist-v1",  # unique prefix
            ),
        )

        user_pool_client = user_pool.add_client("LaunchlistAppClient",
            auth_flows=cognito.AuthFlow(user_password=True),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.EMAIL, cognito.OAuthScope.OPENID, cognito.OAuthScope.PROFILE],
                callback_urls=["https://" + distribution.distribution_domain_name],
                logout_urls=["https://" + distribution.distribution_domain_name],
            ),
        )

        # 3. --- Backend Logic ---
        table = dynamodb.Table(self, "LaunchlistTable",
            partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        subscribe_lambda = _lambda.Function(self, "SubscribeHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.main",
            code=_lambda.Code.from_asset("lambda"),

            environment={
                "TABLE_NAME": table.table_name,
                "SES_FROM_EMAIL": "mlukest@gmail.com" 
            },
        )

        table.grant_write_data(subscribe_lambda)
        
        # Grant SES permission to Lambda
        subscribe_lambda.add_to_role_policy(iam.PolicyStatement(
            actions=["ses:SendEmail", "ses:SendRawEmail"],
            resources=["*"]
        ))

        # 4. --- API Gateway ---
        api = apigw.RestApi(self, "LaunchlistApi",
            rest_api_name="LaunchList API",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=["*"], # Tighten this in production
                allow_methods=["POST", "OPTIONS"]
            )
        )

        authorizer = apigw.CognitoUserPoolsAuthorizer(self, "LaunchlistAuthorizer",
            cognito_user_pools=[user_pool],
        )

        subscribe_resource = api.root.add_resource("subscribe")
        subscribe_resource.add_method("POST",
            apigw.LambdaIntegration(subscribe_lambda),
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO
        )

        # Outputs
        CfnOutput(self, "SiteURL", value=distribution.distribution_domain_name)
        CfnOutput(self, "ApiUrl", value=api.url)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)