#!/usr/bin/python
import json
import requests
from time import sleep

# The URL to access the metadata service
metadata_url ="http://127.0.0.1/metadata/scheduledevents"
# This must be sent otherwise the request will be ignored
header = {'Metadata' : 'true'}
# Current version of the API
query_params = {'api-version':'2020-07-01'}

def get_scheduled_events():           
    resp = requests.get(metadata_url, headers = header, params = query_params)
    print(resp)
    data = resp.json()
    return data

def confirm_scheduled_event(event_id):  
    # This payload confirms a single event with id event_id
    # You can confirm multiple events in a single request if needed      
    payload = json.dumps({"StartRequests": [{"EventId": event_id }]})
    response = requests.post(metadata_url, 
                            headers= header,
                            params = query_params, 
                            data = payload)    
    return response.status_code

def log(event): 
    # This is an optional placeholder for logging events to your system 
    print(event["Description"])
    return

def advanced_sample(last_document_incarnation): 
    # Poll every second to see if there are new scheduled events to process
    # Since some events may have necessarily short warning periods, it is 
    # recommended to poll frequently
    found_document_incarnation = last_document_incarnation
    while (last_document_incarnation == found_document_incarnation):
        sleep(1)
        payload = get_scheduled_events()    
        found_document_incarnation = payload["DocumentIncarnation"]        
        
    # We recommend processing all events in a document together, 
    # even if you won't be actioning on them right away
    for event in payload["Events"]:

        # Events that have already started, logged for tracking
        if (event["EventStatus"] == "Started"):
            log(event)
            
        # Approve all user initiated events. These are typically created by an 
        # administrator and approving them immediately can help to avoid delays 
        # in admin actions
        elif (event["EventSource"] == "User"):
            confirm_scheduled_event(event["EventId"])            
            
        # For this application, freeze events less that 9 seconds are considered
        # no impact. This will immediately approve them
        elif (event["EventType"] == "Freeze" and 
            int(event["DurationInSeconds"]) >= 0  and 
            int(event["DurationInSeconds"]) < 9):
            confirm_scheduled_event(event["EventId"])
            
        # Events that may be impactful (for example reboot or redeploy) may need custom 
        # handling for your application
        else: 
            #TODO Custom handling for impactful events
            log(event)
    print("Processed events from document: " + str(found_document_incarnation))
    return found_document_incarnation

def main():
    # This will track the last set of events seen 
    last_document_incarnation = "-1"

    input_text = "\
        Press 1 to poll for new events \n\
        Press 2 to exit \n "
    program_exit = False 

    while program_exit == False:
        user_input = input(input_text)    
        if (user_input == "1"):                        
            last_document_incarnation = advanced_sample(last_document_incarnation)
        elif (user_input == "2"):
            program_exit = True       

if __name__ == '__main__':
    main()