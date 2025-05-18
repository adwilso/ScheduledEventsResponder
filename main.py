from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flashing messages

# Global variable to store the active scenario and last event
active_scenario = None
last_event = None
last_doc_incarnation = 1

# Predefined scenarios
scenarios = {
    "Live Migration": {
        "EventId": str(uuid.uuid4()),
        "NotBeforeDelayInMinutes": 15,
        "StartedDurationInMinutes": 5,
        "EventStatus": ["Scheduled", "Started", "Completed"],
        "EventType": "Freeze",
        "Description": "Simulates a live migration event",
        "ScenarioDescription": "This scenario simulates a live migration event for testing.",
        "EventSource": "Platform",
        "DurationInSeconds": 5,
    },
    "User Reboot": {
        "EventId": str(uuid.uuid4()),
        "NotBeforeDelayInMinutes": 15,
        "StartedDurationInMinutes": 10,
        "EventStatus": ["Scheduled", "Started", "Completed"],
        "EventType": "Reboot",
        "Description": "Simulates a user-initiated reboot",
        "ScenarioDescription": "This scenario simulates a reboot initiated by the user.",
        "EventSource": "User",
        "DurationInSeconds": -1,
    },
    "Host Agent Maintenance": {
        "EventId": str(uuid.uuid4()),
        "NotBeforeDelayInMinutes": 15,
        "StartedDurationInMinutes": 10,
        "EventStatus": ["Scheduled", "Started", "Completed"],
        "EventType": "Freeze",
        "Description": "Simulates host maintenance",
        "ScenarioDescription": "This scenario simulates host agent maintenance.",
        "EventSource": "Platform",
        "DurationInSeconds": 9,
    },
    "Redeploy": {
        "EventId": str(uuid.uuid4()),
        "NotBeforeDelayInMinutes": 15,
        "StartedDurationInMinutes": 10,
        "EventStatus": ["Scheduled", "Started", "Completed"],
        "EventType": "Redeploy",
        "Description": "Simulates a redeploy event",
        "ScenarioDescription": "This scenario simulates a platform-initiated redeploy.",
        "EventSource": "Platform",
        "DurationInSeconds": -1
    },
    "User Redeploy": {
        "EventId": str(uuid.uuid4()),
        "NotBeforeDelayInMinutes": 15,
        "StartedDurationInMinutes": 10,
        "EventStatus": ["Scheduled", "Started", "Completed"],
        "EventType": "Redeploy",
        "Description": "Simulates a user-initiated redeploy",
        "ScenarioDescription": "This scenario simulates a redeploy initiated by the user.",
        "EventSource": "User",
        "DurationInSeconds": -1
    },
    "Canceled Maintenance": {
        "EventId": str(uuid.uuid4()),
        "NotBeforeDelayInMinutes": 15,
        "StartedDurationInMinutes": 10,
        "EventStatus": ["Scheduled", "Canceled"],
        "EventType": "Freeze",
        "Description": "Simulates a canceled maintenance event",
        "ScenarioDescription": "This scenario simulates a maintenance event that was canceled.",
        "EventSource": "Platform",
        "DurationInSeconds": 9,
    }
    # Add more scenarios as needed
}

@app.route('/')
def index():
    """
    Render the main page with the scenario and event status selection form.
    """
    # Prepare IMDS event format for the last event, if it exists
    imds_event = None
    if last_event:
        scenario_details = last_event["ActiveScenario"]
        event_status = last_event["EventStatus"]
        if event_status in ["Completed", "Canceled"]:
            imds_event = {
                "DocumentIncarnation": last_doc_incarnation,
                "Events": []
            }
        else:
            if event_status == "Scheduled":
                offset = scenario_details.get("NotBeforeDelayInMinutes", 0)
                not_before_time = (datetime.utcnow() + timedelta(minutes=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                not_before_time = ""
            imds_event = {
                "DocumentIncarnation": last_doc_incarnation,
                "Events": [
                    {
                        "EventId": last_event["EventId"],
                        "EventStatus": event_status,
                        "EventType": scenario_details["EventType"],
                        "ResourceType": "VirtualMachine",
                        "Resources": ["/subscriptions/mock/resourceGroups/mock/providers/Microsoft.Compute/virtualMachines/mockvm"],
                        "EventSource": scenario_details["EventSource"],
                        "NotBefore": not_before_time,
                        "Description": scenario_details["Description"],
                        "DurationInSeconds": scenario_details["DurationInSeconds"]
                    }
                ]
            }
    return render_template(
        'index.html',
        scenarios=scenarios,
        active_scenario=active_scenario,
        last_event=last_event,
        last_doc_incarnation=last_doc_incarnation,
        imds_event=imds_event
    )

@app.route('/set-scenario', methods=['POST'])
def set_scenario():
    """
    Set the active scenario based on user selection from the web UI.
    """
    global active_scenario
    scenario_name = request.form.get("scenario")
    if scenario_name not in scenarios:
        return redirect(url_for('index'))

    active_scenario = scenario_name
    return redirect(url_for('index'))

@app.route('/generate-event', methods=['POST'])
def generate_event():
    """
    Generate a mock event based on the active scenario and user-selected event status.
    """
    global last_event, last_doc_incarnation
    if not active_scenario:
        flash("No active scenario. Please set a scenario first.", "error")
        return redirect(url_for('index'))

    # Get the selected event status from the form
    event_status = request.form.get("event_status")
    if event_status not in scenarios[active_scenario]["EventStatus"]:
        flash("Invalid event status selected.", "error")
        return redirect(url_for('index'))

    # Generate a mock event using the active scenario and selected event status
    event_id = str(uuid.uuid4())
    event = {
        "EventId": event_id,
        "Scenario": active_scenario,
        "EventStatus": event_status,
        "ActiveScenario": scenarios[active_scenario],
    }
    last_event = event
    last_doc_incarnation += 1  # Increment document incarnation
    flash(f"New event generated", "success")
    return redirect(url_for('index'))

@app.route('/metadata/scheduledevents', methods=['GET'])
def imds_scheduledevents():
    """
    Respond as if this is the IMDS scheduled events endpoint.
    Returns the last generated event in IMDS format.
    """
    if not last_event:
        # IMDS returns an empty Events list if there are no scheduled events
        return jsonify({
            "DocumentIncarnation": last_doc_incarnation,
            "Events": []
        }), 200

    event = last_event
    scenario_details = event["ActiveScenario"]
    event_status = event["EventStatus"]

    # If the event is Completed or Canceled, return an empty Events list
    if event_status in ["Completed", "Canceled"]:
        return jsonify({
            "DocumentIncarnation": last_doc_incarnation,
            "Events": []
        }), 200

    # Set NotBefore time logic
    if event_status == "Scheduled":
        offset = scenario_details.get("NotBeforeDelayInMinutes", 0)
        not_before_time = (datetime.utcnow() + timedelta(minutes=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        not_before_time = ""

    imds_event = {
        "EventId": event["EventId"],
        "EventStatus": event_status,
        "EventType": scenario_details["EventType"],
        "ResourceType": "VirtualMachine",
        "Resources": ["/subscriptions/mock/resourceGroups/mock/providers/Microsoft.Compute/virtualMachines/mockvm"],
        "EventSource": scenario_details["EventSource"],
        "NotBefore": not_before_time,
        "Description": scenario_details["Description"],
        "DurationInSeconds": scenario_details["DurationInSeconds"]
    }
    return jsonify({
        "DocumentIncarnation": last_doc_incarnation,
        "Events": [imds_event]
    }), 200

if __name__ == '__main__':
    # Start the Flask web server
    app.run(host='127.0.0.1', port=80, debug=False)


