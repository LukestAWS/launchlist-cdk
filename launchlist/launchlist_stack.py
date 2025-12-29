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

        bucket = s3.Bucket(self, "SiteBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ACLS,
            public_read_access=True,
            website_index_document="index.html",
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        s3deploy.BucketDeployment(self, "DeploySite",
            sources=[s3deploy.Source.asset("./assets")],
            destination_bucket=bucket,
        )

        distribution = cloudfront.Distribution(self, "SiteDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
        )

        CfnOutput(self, "SiteURL", value=distribution.distribution_domain_name)

        print(f"SITE_URL=https://{distribution.distribution_domain_name}")
