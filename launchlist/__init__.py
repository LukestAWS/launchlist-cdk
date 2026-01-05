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
    code=_lambda.Code.from_asset("lambda"),
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