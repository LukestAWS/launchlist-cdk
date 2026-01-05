import os
import json
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def main(event, context):
    body = json.loads(event['body'])
    email = body['email']

    table.put_item(Item={
        'PK': 'EMAIL',
        'SK': email,
        'email': email,
    })

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Subscribed!'})
    }