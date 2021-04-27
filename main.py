#!/usr/bin/python3
# import libraries
import daemon
import errno
import logging
import os
import psutil
import socket
import sys
import threading
import time
import yaml
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler
from watchdog.events import PatternMatchingEventHandler

# initialize static variables
files_location = '/etc/bmids/conf.d/files.yaml'
processes_location = '/etc/bmids/conf.d/processes.yaml'
ports_location = '/etc/bmids/conf.d/ports.yaml'
logname = '/var/log/bmids.log'
patterns = "*"
ignore_patterns = ""
case_sensitive = True
testsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
threads = []

# add logger configuration
logging.basicConfig(filename=logname, filemode='a', format='%(asctime)s,%(msecs)d %(name) %(levelname)s %(message)s', datefmt='%H:%M:%S', level=logging.DEBUG)

# initialize event handlers
def on_created_none(event):
    print(f"none event create: {event.src_path}")
    logging.info("none event create: {event.src_path}")

def on_deleted_none(event):
    print(f"none event delete: {event.src_path}")
    logging.info(f"none event delete: {event.src_path}")

def on_modified_none(event):
    print(f"none event modified: {event.src_path}")

def on_moved_none(event):
    print(f"none event moved: {event.src_path} to {event.dest_path}")

def on_created_warn(event):
    print(f"warn event create: {event.src_path}")

def on_deleted_warn(event):
    print(f"warn event delete: {event.src_path}")

def on_modified_warn(event):
    print(f"warn event modified: {event.src_path}")

def on_moved_warn(event):
    print(f"warn event moved: {event.src_path} to {event.dest_path}")

def on_created_critical(event):
    print(f"critical event created: {event.src_path}")

def on_deleted_critical(event):
    print(f"critical event deleted : {event.src_path}")

def on_modified_critical(event):
    print(f"critical event modified: {event.src_path}")

def on_moved_critical(event):
    print(f"critical event moved: {event.src_path} to {event.dest_path}")

# read in configuration files
with open(files_location) as file:
    file_list = yaml.load(file, Loader=yaml.FullLoader)
with open(processes_location) as file:
    processes_list = yaml.load(file, Loader=yaml.FullLoader)
with open(ports_location) as file:
    ports_list = yaml.load(file, Loader=yaml.FullLoader)

# iterate through files objects to create observers
for file_obj in file_list['files']:
    path = file_obj['entry']
    ignore_directories = True
    go_recursively = False
    if file_obj['type'] == 'dir':
        go_recursively = True
        ignore_directories = False
    new_event_handler = PatternMatchingEventHandler(patterns, ignore_patterns, ignore_directories, case_sensitive)
    new_observer = Observer()
    for event_type in ['create','delete','modified','move']:
        if file_obj[event_type] == 'none':
            if event_type == 'create':
                new_event_handler.on_created = on_created_none
            if event_type == 'delete':
                new_event_handler.on_deleted = on_deleted_none
            if event_type == 'modified':
                new_event_handler.on_modified = on_modified_none
            else:
                new_event_handler.on_moved = on_moved_none
        elif file_obj[event_type] == 'warn':
            if event_type == 'create':
                new_event_handler.on_created = on_created_warn
            if event_type == 'delete':
                new_event_handler.on_deleted = on_deleted_warn
            if event_type == 'modified':
                new_event_handler.on_modified = on_modified_warn
            else:
                new_event_handler.on_moved = on_moved_warn
        elif file_obj[event_type] == 'critical':
            if event_type == 'create':
                new_event_handler.on_created = on_created_critical
            if event_type == 'delete':
                new_event_handler.on_deleted = on_deleted_critical
            if event_type == 'modified':
                new_event_handler.on_modified = on_modified_critical
            else:
                new_event_handler.on_moved = on_moved_critical
        else:
            print("handler type invalid: %s", file_obj[event_type])
    new_observer.schedule(new_event_handler, path, recursive=go_recursively)
    print (new_observer)
    threads.append(new_observer)

# iterate through process objects, need to turn into threaded observers
for process_obj in processes_list['processes']:
    for process in psutil.process_iter():
        try:
            if process_obj['entry'].lower() in process.name().lower():
                if process_obj['present'] == 'no':
                    logging.critical("Rogue process found: {process.name}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    if process_obj['present'] == 'yes':
        logging.critical("Essential process missing: {process.name}")

# iterate through port objects, also needs to be turned into threaded observers
for port_obj in ports_list['ports']:
    try:       
        testsock.bind(("127.0.0.1", port_obj['port']))
    except socket.error as sockerr:
        if sockerr.errno == errno.EADDRINUSE:
            if port_obj['open'] == 'no':
                logging.critical("Port {port_obj['port']} is open!")
        logging.critical("Unknown error with {port_obj['port']}!")
    if port_obj['open'] == 'yes':
        logging.critical("Port {port_obj['port']} is closed!")
    testsock.close()    

new_observer.start()

# run threads
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    new_observer.stop()
new_observer.join()
