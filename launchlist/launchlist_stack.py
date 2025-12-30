from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct

class LaunchlistStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Private S3 bucket
        bucket = s3.Bucket(self, "SiteBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,  # private
            website_index_document="index.html",
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Origin Access Control (modern replacement for OAI)
        oac = cloudfront.OriginAccessControl(self, "OAC",
            origin_access_control_name="LaunchlistOAC",
            signing_behavior=cloudfront.SigningBehavior.ALWAYS, # changed from SIGV4_ALWAYS
        )

        # CloudFront distribution with OAC
        distribution = cloudfront.Distribution(self, "SiteDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket, origin_access_control=oac),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
        )

        # Bucket policy to allow CloudFront OAC
        bucket.add_to_resource_policy(
            s3.PolicyStatement(
                actions=["s3:GetObject"],
                effect=s3.Effect.ALLOW,
                principals=[cloudfront.DistributionPrincipal(distribution)],
                resources=[bucket.arn_for_objects("*")],
            )
        )

        # Deploy assets
        s3deploy.BucketDeployment(self, "DeploySite",
            sources=[s3deploy.Source.asset("./assets")],
            destination_bucket=bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        CfnOutput(self, "SiteURL", value=distribution.distribution_domain_name)

        print(f"SITE_URL=https://{distribution.distribution_domain_name}")
