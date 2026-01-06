import os
import json
import boto3

dynamodb = boto3.resource('dynamodb')
ses = boto3.client('ses')
table = dynamodb.Table(os.environ['TABLE_NAME'])
from_email = os.environ['SES_FROM_EMAIL']

def main(event, context):
    body = json.loads(event['body'])
    email = body.get('email', '')

    table.put_item(Item={
        'PK': 'EMAIL',
        'SK': email,
        'email': email,
    })

    ses.send_email(
        Source=from_email,
        Destination={'ToAddresses': [email]},
        Message={
            'Subject': {'Data': 'Welcome to LaunchList!'},
            'Body': {'Text': {'Data': 'Thanks for subscribing.'}}
        }
    )

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Subscribed and email sent!'})
    }