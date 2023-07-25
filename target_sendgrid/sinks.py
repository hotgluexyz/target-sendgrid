"""sendgrid target sink class, which handles writing streams."""

from __future__ import annotations
from typing import Dict
import requests

from target_hotglue.client import HotglueBatchSink


class sendgridSink(HotglueBatchSink):
    """sendgrid target sink class."""
    base_url = "https://api.sendgrid.com"

    max_size = 10000  # Max records to write in one batch
    context = {}
    


class ContactsSink(sendgridSink):
    name = "Contacts"
    endpoint = '/v3/marketing/contacts'
    suppression_endpoint = "/v3/asm/suppressions/global"

    def make_batch_request(self,records):
        unsubscribe = []
        subscribed = []
        for record in records:
            subscribe_status = record['subscribe_status']
            del record['subscribe_status']
            if subscribe_status == 'unsubscribe':
                unsubscribe.append(record)
            else: 
                subscribed.append(record)


        contacts_payload = {
            'contacts': unsubscribe+subscribed
        }


        headers = {'Authorization': f"Bearer {self.config.get('auth_token')}"}

        try:
            response = self.request_api('PUT',self.endpoint,request_data = contacts_payload,headers= headers)
            self.logger.info(f"Successfully PUT {len(unsubscribe)+len(subscribed)} contacts. SendGrid job id: {response.json()['job_id']}")

        except Exception as e: 
            self.logger.info(f'Error occurred while posting subscribed contacts: {e}')
        
        
        if len(unsubscribe) > 0:
            suppression_payload = {
                    "recipient_emails":[
                        rec['email'] for rec in unsubscribe
                    ]
            }
            try: 
                response = self.request_api('POST',self.suppression_endpoint,request_data = suppression_payload, headers=headers)
                self.logger.info(f"Successfully unsubscribed {len(response.json()['recipient_emails'])} contacts")
            except Exception as e: 
                self.logger.info(f"Error occurred while posting unsubscribed contacts: {e}")
            
            


    def process_batch_record(self,record,index):
        
        row = {
            'email':record.get('email'),
            'first_name':record.get('first_name'),
            'last_name':record.get('last_name'),
            'subscribe_status': record.get('subscribe_status')
        }
    
        if record.get('addresses'):
            address = record.get('addresses')[0]
            row['address_line_1'] = address.get('line1')
            row['address_line_2'] = address.get('line2')
            row['city'] = address.get('city')
            row['state_province_region'] = address.get("state")
            row['country'] = address.get('country')
            row['postal_code'] = address.get('postal_code')
        
        return row

    


class CustomersSink(ContactsSink):
    name = 'Customers'
        
