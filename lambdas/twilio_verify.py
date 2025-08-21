import logging
import json
import os
from typing import Dict, Any
import requests

# Configure logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
logger = logging.getLogger()
logger.setLevel(getattr(logging, LOG_LEVEL))

# Environment variables
TWILIO_ACCOUNT_SID = os.environ['TWILIO_ACCOUNT_SID']
TWILIO_AUTH_TOKEN = os.environ['TWILIO_AUTH_TOKEN']
TWILIO_VERIFY_SERVICE_SID = os.environ['TWILIO_VERIFY_SERVICE_SID']

def update_verification_status(phone_number: str, status: str = "approved") -> None:
    """Update the verification status in Twilio Verify using the Feedback API."""
    url = f"https://verify.twilio.com/v2/Services/{TWILIO_VERIFY_SERVICE_SID}/Verifications/{phone_number}"
    
    logger.info(f"Updating verification status to {status} for phone: {phone_number}")
    
    response = requests.post(
        url,
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        data={'Status': status}
    )
    
    if not response.ok:
        logger.error(f"Failed to update verification: {response.text}")
        raise Exception(f"Failed to update verification status: {response.text}")
    else:
        logger.info(f"Successfully updated verification for {phone_number} to status: {status}")

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process Auth0 login success events and update Twilio Verify status."""
    try:
        # Parse the incoming event from EventBridge
        auth0_event = event['detail']['data']
        event_type = auth0_event.get('type')
        logger.info(f"Processing Auth0 event type: {event_type}")
        
        # Early exit if not a gd_auth_succeed event
        if event_type != 'gd_auth_succeed':
            logger.info(f"Skipping event type: {event_type}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'Event type {event_type} not relevant for Verify feedback'
                })
            }
        
        # Get phone number from authenticator object
        details = auth0_event.get('details', {})
        authenticator = details.get('authenticator', {})
        
        if not authenticator:
            logger.error('No authenticator details found in event')
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No authenticator details found in event'
                })
            }
        
        phone_number = authenticator.get('phone_number')
        if not phone_number:
            logger.error('No phone number found in authenticator details')
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No phone number found in authenticator details'
                })
            }
        
        # Clean up phone number to ensure E.164 format
        phone_number = phone_number.replace(" ", "")
        
        # Update the verification status
        update_verification_status(phone_number)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully updated verification for {phone_number}'
            })
        }
            
    except Exception as e:
        logger.error('Unhandled exception', exc_info=True)
        logger.error(f'Event that caused error: {json.dumps(event)}')
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error'
            })
        }