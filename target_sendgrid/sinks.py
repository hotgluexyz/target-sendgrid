"""sendgrid target sink class, which handles writing streams."""

from __future__ import annotations

import requests
import time
from typing import Dict
from target_hotglue.client import HotglueBatchSink


def divide_chunks(l, n=100):
    for i in range(0, len(l), n):
        yield l[i : i + n]


class sendgridSink(HotglueBatchSink):
    base_url = "https://api.sendgrid.com"

    max_size = 10000  # Max records to write in one batch
    context = {}


class ContactsSink(sendgridSink):
    name = "Contacts"
    endpoint = "/v3/marketing/contacts"
    suppression_endpoint = "/v3/asm/suppressions/global"
    state_to_update = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers = {"Authorization": f"Bearer {self.config.get('auth_token')}"}
    

    def _process_job_id_and_state(self, job_id):
        request_not_complete = True
        while request_not_complete:
            response = self.request_api(
                "GET",
                f"/v3/marketing/contacts/imports/{job_id}",
                headers=self.headers,
            )
            time.sleep(5)
            if response.json().get("status") == "completed":
                request_not_complete = False
        

        results = response.json().get("results")
        successful_create_and_deletes = results.get("created_count", 0) + results.get("deleted_count", 0)
        updated_count = results.get("updated_count", 0)
        if successful_create_and_deletes > 0:
            self.logger.info(
                f"Successfully created/updated/deleted {successful_create_and_deletes} contacts"
            )
        failed_upserts = results.get("errored_count", 0)
        if failed_upserts > 0:
            self.logger.info(
                f"Failed creating/updating/deleting {failed_upserts} contacts"
            )
        for _ in range(successful_create_and_deletes):
            self.state_to_update.append({"success": True})
        
        for _ in range(failed_upserts):
            self.state_to_update.append({"fail": True})
        
        for _ in range(updated_count):
            self.state_to_update.append({"is_updated": True, "success": True})


    def _unsubscribe(self, unsubscribe_list):
        suppression_payload = {
                "recipient_emails": [rec["email"] for rec in unsubscribe_list]
            }
        try:
            response = self.request_api(
                "POST",
                self.suppression_endpoint,
                request_data=suppression_payload,
                headers=self.headers,
            )
            self.logger.info(
                f"Successfully unsubscribed {len(response.json()['recipient_emails'])} contacts"
            )
            for _ in range(unsubscribe_list):
                self.state_to_update.append({"success": True})
        except Exception as e:
            self.logger.info(
                f"Error occurred while posting unsubscribed contacts: {e}"
            )            


    def make_batch_request(self, records, default_list_id=None):
        unsubscribe = []
        subscribed = []
        for record in records:
            subscribe_status = record.pop("subscribe_status")
            if subscribe_status == "unsubscribe":
                unsubscribe.append(record)
            else:
                subscribed.append(record)

        contacts_payload = {"contacts": unsubscribe + subscribed}

        if default_list_id:
            contacts_payload["list_ids"] = [default_list_id]

        try:
            response = self.request_api(
                "PUT", self.endpoint, request_data=contacts_payload, headers=self.headers
            )
            self._process_job_id_and_state(response.json()["job_id"])
        except Exception as e:
            self.logger.info(f"Error occurred while posting subscribed contacts: {e}")
        

        if len(unsubscribe) > 0:
            self._unsubscribe(unsubscribe)
            

    def process_batch_record(self, record, index):
        row = {
            "email": record.get("email"),
            "first_name": record.get("first_name"),
            "last_name": record.get("last_name"),
            "subscribe_status": record.get("subscribe_status"),
        }

        if record.get("addresses"):
            address = record.get("addresses")[0]
            row["address_line_1"] = address.get("line1")
            row["address_line_2"] = address.get("line2")
            row["city"] = address.get("city")
            row["state_province_region"] = address.get("state")
            row["country"] = address.get("country")
            row["postal_code"] = address.get("postal_code")
        
        if record.get("phone_numbers"):
            phone_numbers = record.get("phone_numbers")
            if phone_numbers[0].get("number"):
                row["phone_number"] = phone_numbers[0].get("number")

        return row

    def _get_default_list_id(self):
        response = self.request_api(
            "GET",
            f"/v3/marketing/lists",
            headers=self.headers,
        )
        for list in response.json()["result"]:
            if list["name"] == self.config.get("list_name"):
                return list["id"]
            elif list["id"] == self.config.get("list_id"):
                return list["id"]
        
        raise Exception(f"List with name {self.config.get('list_name')} doesn't exist'")

    def process_batch(self, context: dict) -> None:
        if not self.latest_state:
            self.init_state()

        raw_records = context["records"]
        records = list(map(lambda e: self.process_batch_record(e[1], e[0]), enumerate(raw_records)))

        if self.config.get("list_name"):
            list_id = self._get_default_list_id()
        else:
            list_id = None

        self.make_batch_request(records, default_list_id=list_id)

        for state in self.state_to_update:
            self.update_state(state)


class CustomersSink(ContactsSink):
    name = "Customers"
