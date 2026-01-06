from aws_cdk import (
    Stack,
    aws_cognito as cognito,
    aws_ses as ses,
    aws_ses_actions as ses_actions,
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
                conditions={
                    "StringEquals": {
                        "AWS:SourceArn": distribution.distribution_arn
                    }
                },
            )
        )

        s3deploy.BucketDeployment(self, "DeploySite",
            sources=[s3deploy.Source.asset("./assets")],
            destination_bucket=bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        # --- Backend Logic ---
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
            },
        )

        table.grant_write_data(subscribe_lambda)

        api = apigw.RestApi(self, "LaunchlistApi",
            rest_api_name="LaunchList API",
        )

        subscribe_integration = apigw.LambdaIntegration(subscribe_lambda)
        api.root.add_resource("subscribe").add_method("POST", subscribe_integration)

        # --- NEW: Cognito User Pool ---
        user_pool = cognito.UserPool(self, "LaunchlistUserPool",
            user_pool_name="LaunchlistUserPool",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_digits=True,
                require_lowercase=True,
                require_symbols=True,
                require_uppercase=True,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        user_pool_client = user_pool.add_client("LaunchlistAppClient",
            auth_flows=cognito.AuthFlow(user_password=True),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.EMAIL, cognito.OAuthScope.OPENID, cognito.OAuthScope.PROFILE],
                callback_urls=["https://d1psz3m8fwuyiu.cloudfront.net"],  # update with frontend URL
                logout_urls=["https://d1psz3m8fwuyiu.cloudfront.net"],
            ),
        )

        # Protect API with Cognito
        authorizer = apigw.CognitoUserPoolsAuthorizer(self, "LaunchlistAuthorizer",
            cognito_user_pools=[user_pool],
        )

        api.root.get_resource("subscribe").add_method("POST",
            subscribe_integration,
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # --- NEW: SES for confirmation emails ---
        # Manual: Verify email/domain in SES console
        # Add to subscribe_lambda environment: "SES_FROM_EMAIL": "your@verified.email"
        # Update lambda/handler.py to send email (next)

        # Outputs
        CfnOutput(self, "SiteURL", value=distribution.distribution_domain_name)
        CfnOutput(self, "ApiUrl", value=api.url)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
        print(f"SITE_URL=https://{distribution.distribution_domain_name}")
        print(f"API_URL={api.url}")