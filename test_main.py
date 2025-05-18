import pytest
from main import app, scenarios
from collections import OrderedDict
import uuid

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_imds_scheduledevents_valid_event_for_each_scenario(client):
    for scenario_name in scenarios.keys():
        # Set the scenario
        client.post('/set-scenario', data={'scenario': scenario_name})
        # For each status in the scenario, generate the event and check the IMDS response
        for status in scenarios[scenario_name]['EventStatus'].keys():
            client.post('/generate-event', data={'event_status': status})
            resp = client.get('/metadata/scheduledevents')
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'DocumentIncarnation' in data
            assert 'Events' in data
            # If status is Completed or Canceled, Events should be empty
            if status in ['Completed', 'Canceled']:
                assert data['Events'] == []
            else:
                assert len(data['Events']) == 1
                event = data['Events'][0]
                assert event['EventId']
                assert event['EventStatus'] == status
                assert event['EventType'] == scenarios[scenario_name]['EventType']
                assert event['ResourceType'] == 'VirtualMachine'
                assert event['EventSource'] == scenarios[scenario_name]['EventSource']
                assert event['Description'] == scenarios[scenario_name]['Description']
                assert 'NotBefore' in event
                assert 'DurationInSeconds' in event
                # NotBefore logic
                if status == 'Started':
                    assert event['NotBefore'] == ''
                elif status == 'Scheduled':
                    assert event['NotBefore'] != ''

def test_invalid_scenario_selection(client):
    resp = client.post('/set-scenario', data={'scenario': 'NonExistentScenario'})
    assert resp.status_code == 302  # Should redirect
    # No scenario should be set, so generating event should fail
    resp = client.post('/generate-event', data={'event_status': 'Scheduled'})
    assert resp.status_code == 302

def test_invalid_event_status(client):
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    resp = client.post('/generate-event', data={'event_status': 'InvalidStatus'})
    assert resp.status_code == 302
    # Should not update event, so /metadata/scheduledevents should return empty
    resp = client.get('/metadata/scheduledevents')
    data = resp.get_json()
    assert data['Events'] == []

def test_notbefore_for_non_scheduled_status(client):
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    for status in scenarios[scenario_name]['EventStatus'].keys():
        client.post('/generate-event', data={'event_status': status})
        resp = client.get('/metadata/scheduledevents')
        data = resp.get_json()
        if status == 'Started':
            if data['Events']:
                assert data['Events'][0]['NotBefore'] == ''
        elif status == 'Scheduled':
            if data['Events']:
                assert data['Events'][0]['NotBefore'] != ''
        elif data['Events']:
            assert data['Events'][0]['NotBefore'] == ''


def test_autorun_scenario_progression(client):
    scenario_name = list(scenarios.keys())[0]
    statuses = list(scenarios[scenario_name]['EventStatus'].keys())
    client.post('/set-scenario', data={'scenario': scenario_name})
    # Simulate auto-run by generating events in order
    notbefore = None
    for idx, status in enumerate(statuses):
        client.post('/generate-event', data={'event_status': status})
        resp = client.get('/metadata/scheduledevents')
        data = resp.get_json()
        if status == 'Scheduled' and data['Events']:
            notbefore = data['Events'][0]['NotBefore']
        if status == 'Started' and data['Events']:
            assert data['Events'][0]['NotBefore'] == ''
        if status == 'Completed' and data['Events']:
            assert data['Events'] == []
    # NotBefore should not change for the scenario run
    if notbefore:
        client.post('/generate-event', data={'event_status': statuses[1]})
        resp = client.get('/metadata/scheduledevents')
        data = resp.get_json()
        if data['Events']:
            assert data['Events'][0]['NotBefore'] == ''

def test_no_scenario_selected(client):
    # Reset by posting to stop auto-run (which clears last_event)
    client.post('/stop-auto-run')
    resp = client.get('/metadata/scheduledevents')
    data = resp.get_json()
    assert data['Events'] == []


def test_document_incarnation_increments(client):
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    client.post('/generate-event', data={'event_status': 'Scheduled'})
    resp1 = client.get('/metadata/scheduledevents')
    doc1 = resp1.get_json()['DocumentIncarnation']
    client.post('/generate-event', data={'event_status': 'Started'})
    resp2 = client.get('/metadata/scheduledevents')
    doc2 = resp2.get_json()['DocumentIncarnation']
    assert doc2 == doc1 + 1

def test_eventid_uniqueness(client):
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    ids = set()
    for status in scenarios[scenario_name]['EventStatus'].keys():
        client.post('/generate-event', data={'event_status': status})
        resp = client.get('/metadata/scheduledevents')
        data = resp.get_json()
        if data['Events']:
            event_id = data['Events'][0]['EventId']
            assert event_id not in ids
            ids.add(event_id)

def test_single_status_scenario(client):
    # Add a scenario with only one status
    from main import scenarios
    scenarios['SingleStatus'] = {
        "EventId": str(uuid.uuid4()),
        "NotBeforeDelayInMinutes": 5,
        "StartedDurationInMinutes": 2,
        "EventStatus": OrderedDict([
            ("Scheduled", 5)
        ]),
        "EventType": "Test",
        "Description": "Single status test",
        "ScenarioDescription": "Test scenario with one status",
        "EventSource": "TestSource",
        "DurationInSeconds": 1
    }
    client.post('/set-scenario', data={'scenario': 'SingleStatus'})
    client.post('/generate-event', data={'event_status': 'Scheduled'})
    resp = client.get('/metadata/scheduledevents')
    data = resp.get_json()
    assert len(data['Events']) == 1
    event = data['Events'][0]
    assert event['EventStatus'] == 'Scheduled'
    assert event['EventType'] == 'Test'
    assert event['EventSource'] == 'TestSource'
    assert event['Description'] == 'Single status test'
    assert event['NotBefore'] != ''
