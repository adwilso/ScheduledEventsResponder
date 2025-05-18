from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from collections import OrderedDict
import uuid
from datetime import datetime, timedelta, timezone
import threading
import time

#TODO: List for Monday:
# 1. Create readme file
# 2. Update description strings to real ones 
# 3. Confirm timings on events, switch to minutes on the autorunners
# 3. Add more descriptive scenario descriptions


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
        "EventStatus": OrderedDict([
            ("Scheduled", 15),
            ("Started", 5),
            ("Completed", 0)
        ]),
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
        "EventStatus": OrderedDict([
            ("Scheduled", 15),
            ("Started", 10),
            ("Completed", 0)
        ]),
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
        "EventStatus": OrderedDict([
            ("Scheduled", 15),
            ("Started", 10),
            ("Completed", 0)
        ]),
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
        "EventStatus": OrderedDict([
            ("Scheduled", 15),
            ("Started", 10),
            ("Completed", 0)
        ]),
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
        "EventStatus": OrderedDict([
            ("Scheduled", 15),
            ("Started", 10),
            ("Completed", 0)
        ]),
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
        "EventStatus": OrderedDict([
            ("Scheduled", 8),
            ("Canceled", 0)
        ]),
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
        if event_status in scenario_details["EventStatus"] and event_status in ["Completed", "Canceled"]:
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
    Also resets last_event so NotBefore is recalculated for the new scenario.
    """
    global active_scenario, last_event
    scenario_name = request.form.get("scenario")
    if scenario_name not in scenarios:
        return redirect(url_for('index'))

    active_scenario = scenario_name
    last_event = None  # Reset event state so NotBefore is recalculated
    return redirect(url_for('index'))

@app.route('/generate-event', methods=['POST'])
def generate_event():
    """
    Generate a mock event based on the active scenario and user-selected event status.
    """
    global last_event, last_doc_incarnation, active_scenario
    if not active_scenario:
        flash("No active scenario. Please set a scenario first.", "error")
        return redirect(url_for('index'))

    event_status = request.form.get("event_status")
    if event_status not in scenarios[active_scenario]["EventStatus"]:
        flash("Invalid event status selected.", "error")
        return redirect(url_for('index'))

    # Set NotBefore time for the event
    scenario = scenarios[active_scenario]
    not_before_time = None
    if event_status == "Scheduled":
        offset = scenario.get("NotBeforeDelayInMinutes", 0)
        not_before_time = (datetime.now(timezone.utc) + timedelta(minutes=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")

    event_id = str(uuid.uuid4())
    event = {
        "EventId": event_id,
        "Scenario": active_scenario,
        "EventStatus": event_status,
        "ActiveScenario": scenario,
        "NotBefore": not_before_time
    }
    last_event = event
    last_doc_incarnation += 1
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
    not_before_time = event.get("NotBefore")

    # If the event is Completed or Canceled, return an empty Events list
    if event_status in scenario_details["EventStatus"] and event_status in ["Completed", "Canceled"]:
        return jsonify({
            "DocumentIncarnation": last_doc_incarnation,
            "Events": []
        }), 200

    # If status is Started, NotBefore must be an empty string
    if event_status == "Started":
        not_before_time = ""

    imds_event = {
        "EventId": event["EventId"],
        "EventStatus": event_status,
        "EventType": scenario_details["EventType"],
        "ResourceType": "VirtualMachine",
        "Resources": ["/subscriptions/mock/resourceGroups/mock/providers/Microsoft.Compute/virtualMachines/mockvm"],
        "EventSource": scenario_details["EventSource"],
        "NotBefore": not_before_time if not_before_time else "",
        "Description": scenario_details["Description"],
        "DurationInSeconds": scenario_details["DurationInSeconds"]
    }
    return jsonify({
        "DocumentIncarnation": last_doc_incarnation,
        "Events": [imds_event]
    }), 200

auto_run_thread = None
stop_auto_run = threading.Event()

def auto_run_scenario():
    global last_event, last_doc_incarnation, active_scenario, stop_auto_run
    scenario = scenarios[active_scenario]
    event_statuses = list(scenario["EventStatus"].keys())
    durations = list(scenario["EventStatus"].values())
    not_before_time = None
    for idx, status in enumerate(event_statuses):
        if stop_auto_run.is_set() or (last_event is not None and active_scenario != last_event.get("Scenario", None)):
            break
        # Only set NotBefore for the first event if not already set
        if idx == 0:
            if last_event is None or last_event.get("NotBefore") is None:
                if status == "Scheduled":
                    offset = scenario.get("NotBeforeDelayInMinutes", 0)
                    not_before_time = (datetime.now(timezone.utc) + timedelta(minutes=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    not_before_time = None
            else:
                not_before_time = last_event.get("NotBefore")
        else:
            not_before_time = last_event.get("NotBefore")
        event_id = str(uuid.uuid4())
        event = {
            "EventId": event_id,
            "Scenario": active_scenario,
            "EventStatus": status,
            "ActiveScenario": scenario,
            "NotBefore": not_before_time
        }
        last_event = event
        last_doc_incarnation += 1
        if idx < len(event_statuses) - 1:
            time.sleep(durations[idx])
    # After reaching the last state, keep returning the same event until user changes scenario

@app.route('/auto-run-scenario', methods=['POST'])
def auto_run_scenario_route():
    global active_scenario, auto_run_thread, stop_auto_run
    if not active_scenario:
        flash("No active scenario. Please set a scenario first.", "error")
        return redirect(url_for('index'))
    stop_auto_run.set()  # Stop any previous auto-run
    stop_auto_run = threading.Event()  # Reset event
    def run():
        auto_run_scenario()
    auto_run_thread = threading.Thread(target=run, daemon=True)
    auto_run_thread.start()
    flash("Automatically running scenario.", "success")
    return redirect(url_for('index'))

@app.route('/stop-auto-run', methods=['POST'])
def stop_auto_run_route():
    global stop_auto_run, last_event
    stop_auto_run.set()
    stop_auto_run = threading.Event()
    last_event = None
    flash("Event playback stopped and reset.", "success")
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Start the Flask web server
    app.run(host='127.0.0.1', port=80, debug=False)


