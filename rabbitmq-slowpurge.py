"""
USAGE: Make sure you export the RABBITMQ_PASSWORD environment variable with the right password!
python rabbitmq-slowpurge.py 1
python rabbitmq-slowpurge.py 0.5
python rabbitmq-slowpurge.py 0.01, etc.
"""

import os
import pika
import sys
import time


# RabbitMQ connection parameters
RABBITMQ_HOST = 'eager-olden-wallaby.rmq.cloudamqp.com'
RABBITMQ_VHOST = 'epeyjyev'
RABBITMQ_USER = 'epeyjyev'
RABBITMQ_PASSWORD = os.environ['RABBITMQ_PASSWORD']

# RabbitMQ connection parameters
parameters = pika.ConnectionParameters(
    host=RABBITMQ_HOST,
    virtual_host=RABBITMQ_VHOST,
    credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
)

def slow_purge_queue(queue_name):
    # Establish connection with the RabbitMQ server
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # Define a callback function to process messages
    def callback(ch, method, properties, body):
        # Sleep however long is specified in the first command line argument
        time.sleep(float(sys.argv[1]))

    # Start consuming messages with auto_ack=True
    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

    # Start the consuming loop
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()

    # Close the connection
    connection.close()

# Queue name to consume
queue_name = 'to_delete'

# Execute the consume operation
slow_purge_queue(queue_name)