"""
Machine Metrics Dump Utility
Quick hack to dump machine metrics to a CSV file.
"""

import json
import os
import sys
import time
import requests
import logging
import argparse
import traceback
import datetime
import csv
import re

API_KEY = os.getenv("MM_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def query_graphql(url, query, variables=None):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}'
    }
    
    payload = {
        'query': query,
        'variables': variables
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def fetch_and_store_data(graphql_url, query, initial_offset=0, limit=10):
    all_data = []
    offset = initial_offset

    while True:
        variables = {
            "limit": limit,
            "offset": offset,
            "order_by": [
                {
                    "name": "asc"
                }
            ]
        }

        logging.info(f"Querying with offset: {offset}, limit: {limit}")
        result = query_graphql(graphql_url, query, variables)
        logging.info(f"Result: {result}")
        data = result.get('data', {}).get('machines', [])
        logging.info(f"Fetched data: {data}")

        if not data:
            logging.info("No more data to fetch, breaking the loop.")
            break

        all_data.extend(data)
        offset += limit

    return all_data

def write_to_csv(data, filename='output.csv'):
    if not data:
        logging.info("No data to write.")
        return

    keys = data[0].keys()
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)
        logging.info(f"Data written to {filename}")

if __name__ == "__main__":
    graphql_url = 'https://api.machinemetrics.com/graphql'
    # query = """
    # query ActivitySets(
    #     $limit: Int,
    #     $offset: Int,
    #     $order_by: [ActivitySet_order_by!]
    # ) {
    #     activitySets(
    #         limit: $limit,
    #         offset: $offset,
    #         order_by: $order_by
    #     ) {
    #         activities {
    #             activityType
    #             endAt
    #             startAt
    #         }
    #         activitySetRef
    #         machine {
    #             make
    #             model
    #             name
    #         }
    #         operation {
    #             name
    #         }
    #         workOrderId
    # }
    # }
    # """

    query = """
    query Machines(
        $limit: Int,
        $offset: Int,
        $order_by: [MachineTP_order_by!]
    ) {
        machines(
            limit: $limit,
            offset: $offset,
            order_by: $order_by
        ) {
            activitySets {
                activitySetRef
            }
            decommissionedAt
            machineRef
            make
            metrics {
                metricKey
                type
                subtype
            }
            model
            name
        }
    }
    """

    data = fetch_and_store_data(graphql_url, query)
    write_to_csv(data)
