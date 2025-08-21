"""
This lambda function is used to process Auth0 logs from DynamoDB and send a report to the given Google Sheet.
"""


import logging
import boto3
import time

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from decimal import Decimal


logger = logging.getLogger()
logger.setLevel(logging.INFO)

DYNAMODB_TABLE_NAME = 'DDBTableName'  # This is the name of the DynamoDB table you want to use, you MUST change this!
SPREADSHEET_ID      = 'GoogleSheetID'  # This is the ID of the Google Sheet you want to use, you MUST change this!
EXCLUDED_DOMAINS    = ['test.com']  # Optional, if you want to exclude certain domains from the report, add them here.
TIMEOUT_SECONDS     = 900  # 15 minutes, max for Lambda, adjust as needed


def lambda_handler(event, context):
    logger.info(f'Event: {event}')
    # Get the start and end dates and sheet name from the arguments
    start_date_str = event.get('start_date', None)
    end_date_str = event.get('end_date', None)
    sheet = event.get('sheet', 'TEMPSHEET')
    watched_domains = event.get('watched_domains', [])
    unique_addresses_only = bool(event.get('unique_addresses_only', False))

    # Get some context for a default range in case it's needed, cheap to find.
    first_day_current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day_last_month = first_day_current_month - timedelta(days=1)

    if not start_date_str:
        # Set start_date
        first_day_last_month = last_day_last_month.replace(day=1)
        start_date_str = first_day_last_month.strftime('%Y-%m-%d')

    if not end_date_str:
        # Set end_date to last day of last month
        end_date_str = last_day_last_month.strftime('%Y-%m-%d')

    # Get logs from DynamoDB
    logger.info(f'Getting logs from {start_date_str} to {end_date_str}')
    logs = get_logs(start_date_str, end_date_str)

    # Used for pulling a list of unique email addresses
    if unique_addresses_only:
        try:
            logger.info('Getting unique addresses')
            result = {
                'statusCode': 200,
                'body': get_unique_addresses(logs)
            }
            # logger.info('Unique addresses execution complete! Returning...')
            return result
        except Exception as e:
            logger.error(f'Error getting unique addresses: {e}')
            return {
                'statusCode': 500,
                'body': f'Error getting unique addresses: {e}'
            }

    logger.info('Counting users...')
    # Unpack all return values from count_users
    (total_users, users_by_domain, successful_logins, successful_logins_by_domain,
     failed_logins, failed_logins_by_domain, password_changes, password_changes_by_domain,
     users_by_watched_domain) = count_users(logs, watched_domains)

    if sheet is not None:
        # Send results to Google Sheets
        logger.info('Sending results to Google Sheets...')
        send_to_google_sheets(
            start_date_str,
            end_date_str,
            total_users,
            users_by_domain, 
            successful_logins, 
            successful_logins_by_domain,
            failed_logins, 
            failed_logins_by_domain, 
            password_changes, 
            password_changes_by_domain,
            users_by_watched_domain,
            sheet
        )
    
    logger.info('Execution complete! Returning...')
    return {
        'statusCode': 200,
        'body': 'Report complete, review GSheet'
    }


def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            items.append((new_key, flatten_list(v)))
        elif isinstance(v, Decimal):
            items.append((new_key, int(v)))
        else:
            items.append((new_key, v))
    return dict(items)


def flatten_list(l):
    return str(l)


def daterange(start_date, end_date):
    # Ensure start_date and end_date are datetime objects
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(n)


def get_logs(start_date=None, end_date=None):
    """
    Get logs from DynamoDB table.
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    start_time = time.time()

    logs = []

    # If start_date and end_date are provided, query logs based on these dates
    if start_date and end_date:
        for single_date in daterange(start_date, end_date):
            for i in range(10):  # Maximum of 10 retries
                try:
                    response = table.query(
                        KeyConditionExpression=Key('day').eq(single_date.strftime("%Y-%m-%d"))
                    )
                    for item in response['Items']:
                            if item['data']['type'] in ['f', 's', 'scp', 'fcpr']:
                                logs.append(item)

                    while 'LastEvaluatedKey' in response:
                        # logger.info(f'Querying page... LEK: {response["LastEvaluatedKey"]}')
                        response = table.query(
                            KeyConditionExpression=Key('day').eq(single_date.strftime("%Y-%m-%d")),
                            ExclusiveStartKey=response['LastEvaluatedKey']
                        )

                        # Don't evaluate logs we're not interested in,
                        # see https://auth0.com/docs/deploy-monitor/logs/log-event-type-codes for more details.
                        for item in response['Items']:
                            if item['data']['type'] in ['f', 's', 'scp', 'fcpr']:
                                logs.append(item)

                        # Check for timeout
                        if time.time() - start_time > TIMEOUT_SECONDS:
                            raise TimeoutError(f'Query took too long on {single_date.strftime("%Y-%m-%d")}!')

                    break

                except ClientError as e:
                    if e.response['Error']['Code'] == 'ProvisionedThroughputExceededException':
                        time.sleep(2 ** i)  # Exponential backoff
                    else:
                        raise
    else:
        # If start_date and end_date are not provided, scan entire table
        response = table.scan()
        logs = response['Items']

        # If there are more items than can be returned in a single scan, continue scanning until all items are returned
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            logs.extend(response['Items'])

    return logs


def get_unique_addresses(logs):
    unique_addresses = set()

    for log in logs:
        try:
            user_email = log['data']['user_name']

            if '@' not in user_email or user_email.endswith('@'):
                continue

            domain = user_email.split('@')[-1]

            if domain not in EXCLUDED_DOMAINS:
                unique_addresses.add(user_email)

        except KeyError:
            continue

    # This is yet another hack, just need to pull the unique addresses
    print(f'Unique addresses: {len(unique_addresses)}')
    return list(unique_addresses)


def count_users(logs, watched_domains):
    unique_users = set()
    unique_users_by_domain = {}
    users_by_domain = {}
    successful_logins = 0
    failed_logins = 0
    password_changes = 0
    successful_logins_by_domain = {}
    failed_logins_by_domain = {}
    password_changes_by_domain = {}

    for log in logs:
        try:
            user_email = log['data']['user_name']
            log_type = log['data']['type']
        except KeyError:
            continue

        if '@' not in user_email or user_email.endswith('@'):
            continue

        domain = user_email.split('@')[-1]

        if domain in EXCLUDED_DOMAINS:
            continue

        unique_users.add(user_email)
        if domain not in unique_users_by_domain:
            unique_users_by_domain[domain] = set()
        unique_users_by_domain[domain].add(user_email)

        if domain in watched_domains:
            if domain not in users_by_domain:
                users_by_domain[domain] = {'emails': {}}
            users_by_domain[domain]['emails'][user_email] = users_by_domain[domain]['emails'].get(user_email, 0) + 1

        if log_type == 's':
            successful_logins += 1
            successful_logins_by_domain[domain] = successful_logins_by_domain.get(domain, 0) + 1
        elif log_type == 'f':
            failed_logins += 1
            failed_logins_by_domain[domain] = failed_logins_by_domain.get(domain, 0) + 1
        elif log_type in ['scp', 'fcpr']:
            password_changes += 1
            password_changes_by_domain[domain] = password_changes_by_domain.get(domain, 0) + 1

    total_users = len(unique_users)
    unique_users_by_domain = {domain: len(users) for domain, users in unique_users_by_domain.items()}
    users_by_domain = {domain: {'emails': data['emails']} for domain, data in users_by_domain.items()}

    return (total_users, unique_users_by_domain, successful_logins, successful_logins_by_domain,
            failed_logins, failed_logins_by_domain, password_changes, password_changes_by_domain, users_by_domain)


def send_to_google_sheets(start_date, end_date, total_users, users_by_domain, successful_logins, successful_logins_by_domain,
                          failed_logins, failed_logins_by_domain, password_changes, password_changes_by_domain,
                          users_by_watched_domain, sheet_name):
    credentials = Credentials.from_service_account_file('google-api-credentials.json')
    service = build('sheets', 'v4', credentials=credentials)
    range_ = sheet_name
    sheet_metadata = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets = sheet_metadata.get('sheets', '')
    sheet_names = [sheet.get('properties', {}).get('title') for sheet in sheets]
    if range_ not in sheet_names:
        body = {'requests': [{'addSheet': {'properties': {'title': range_}}}]}
        service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body).execute()

    values = [
        [f"Report for {start_date} to {end_date}"], ['', ''],
        ['Metrics', 'Total'],
        ['Active Accounts', total_users],
        ['Successful Logins', successful_logins],
        ['Failed Logins', failed_logins],
        ['Password Changes', password_changes],
        ['', ''], ['Active Accounts by Email Domain'],
        *[[f"{domain}", int(count)] for domain, count in users_by_domain.items()],
        ['', ''], ['Successful Logins by Email Domain'],
        *[[f"{domain}", int(count)] for domain, count in successful_logins_by_domain.items()],
        ['', ''], ['Failed Logins by Email Domain'],
        *[[f"{domain}", int(count)] for domain, count in failed_logins_by_domain.items()],
        ['', ''], ['Password Changes by Email Domain'],
        *[[f"{domain}", int(count)] for domain, count in password_changes_by_domain.items()],
        ['', ''], ['Users by Watched Domains'],
        *[[f"{domain}", f"{user_email}", f"{data['emails'][user_email]}"] for domain, data in users_by_watched_domain.items() for user_email in data['emails']],
    ]

    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=range_,
        valueInputOption='RAW',
        body={'values': values}
    ).execute()
