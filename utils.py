# utils.py
import os
import zmq
import zmq.asyncio
import logging

# ZMQ addresses (override via environment variables for Kubernetes support)
PRESENCE_CHANNEL = os.getenv("AIPERF_PRESENCE_CHANNEL", "tcp://127.0.0.1:5556")
CONTROL_CHANNEL = os.getenv("AIPERF_CONTROL_CHANNEL", "tcp://127.0.0.1:5557")
TIMING_CHANNEL  = os.getenv("AIPERF_TIMING_CHANNEL",  "tcp://127.0.0.1:5560")
DATASET_CHANNEL = os.getenv("AIPERF_DATASET_CHANNEL", "tcp://127.0.0.1:5561")
RESULTS_CHANNEL = os.getenv("AIPERF_RESULTS_CHANNEL","tcp://127.0.0.1:5558")

# Async ZMQ context
ctx = zmq.asyncio.Context()

def create_pub_socket(addr: str, bind: bool = True, socket_type=zmq.PUB):
    sock = ctx.socket(socket_type)
    if bind:
        logging.info("Binding PUB socket to %s", addr)
        sock.bind(addr)
    else:
        logging.info("Connecting PUB socket to %s", addr)
        sock.connect(addr)
    return sock

def create_sub_socket(addr: str, bind: bool = False, topics=None, socket_type=zmq.SUB):
    sock = ctx.socket(socket_type)
    if bind:
        logging.info("Binding SUB socket to %s", addr)
        sock.bind(addr)
    else:
        logging.info("Connecting SUB socket to %s", addr)
        sock.connect(addr)
    if topics is None:
        sock.setsockopt_string(zmq.SUBSCRIBE, "")
    else:
        for t in topics:
            sock.setsockopt_string(zmq.SUBSCRIBE, t)
    return sock 