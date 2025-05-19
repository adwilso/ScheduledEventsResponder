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

def test_resources_field_default_and_custom(client):
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})

    # Default resources
    client.post('/generate-event', data={'event_status': 'Scheduled'})
    resp = client.get('/metadata/scheduledevents')
    data = resp.get_json()
    if data['Events']:
        assert data['Events'][0]['Resources'] == ['vmss_vm1']

    # Custom resources
    custom_resources = "vmss_vm2, vmss_vm3"
    client.post('/generate-event', data={'event_status': 'Scheduled', 'resources': custom_resources})
    resp = client.get('/metadata/scheduledevents')
    data = resp.get_json()
    if data['Events']:
        assert data['Events'][0]['Resources'] == ['vmss_vm2', 'vmss_vm3']

def test_resources_field_trimming_and_empty(client):
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})

    # Whitespace trimming
    custom_resources = "  vmss_vm4  ,   vmss_vm5 "
    client.post('/generate-event', data={'event_status': 'Scheduled', 'resources': custom_resources})
    resp = client.get('/metadata/scheduledevents')
    data = resp.get_json()
    if data['Events']:
        assert data['Events'][0]['Resources'] == ['vmss_vm4', 'vmss_vm5']

    # Empty resources
    client.post('/generate-event', data={'event_status': 'Scheduled', 'resources': ''})
    resp = client.get('/metadata/scheduledevents')
    data = resp.get_json()
    if data['Events']:
        assert data['Events'][0]['Resources'] == ['vmss_vm1']


def test_imds_contract_fields(client):
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    for status in scenarios[scenario_name]['EventStatus'].keys():
        client.post('/generate-event', data={'event_status': status})
        resp = client.get('/metadata/scheduledevents')
        data = resp.get_json()
        if data['Events']:
            event = data['Events'][0]
            # Required IMDS fields
            assert 'EventId' in event
            assert 'EventStatus' in event
            assert 'EventType' in event
            assert 'ResourceType' in event
            assert 'Resources' in event
            assert 'EventSource' in event
            assert 'NotBefore' in event
            assert 'Description' in event
            assert 'DurationInSeconds' in event
            assert isinstance(event['Resources'], list)


def test_generate_event_with_invalid_status(client):
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    resp = client.post('/generate-event', data={'event_status': 'NotAStatus'})
    assert resp.status_code == 302
    resp = client.get('/metadata/scheduledevents')
    data = resp.get_json()
    assert data['Events'] == []


def test_completed_canceled_event_returns_empty(client):
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    for status in ['Completed', 'Canceled']:
        if status in scenarios[scenario_name]['EventStatus']:
            client.post('/generate-event', data={'event_status': status})
            resp = client.get('/metadata/scheduledevents')
            data = resp.get_json()
            assert data['Events'] == []

def test_autorun_post_advance_integration(client):
    """Test that POST to /metadata/scheduledevents with StartRequests advances state immediately and auto-run continues."""
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    # Start with Scheduled
    client.post('/generate-event', data={'event_status': 'Scheduled'})
    resp = client.get('/metadata/scheduledevents')
    data = resp.get_json()
    if not data['Events']:
        pytest.skip("No event to advance")
    event_id = data['Events'][0]['EventId']
    # POST to advance state
    resp = client.post(
        '/metadata/scheduledevents',
        json={"StartRequests": [{"EventId": event_id}]},
        headers={"Metadata": "true"}
    )
    data2 = resp.get_json()
    assert resp.status_code == 200
    assert data2['Events'][0]['EventStatus'] != 'Scheduled'
    # Auto-run should still be able to advance to next state
    # Simulate next auto-run step
    client.post('/generate-event', data={'event_status': data2['Events'][0]['EventStatus']})
    resp3 = client.get('/metadata/scheduledevents')
    data3 = resp3.get_json()
    assert data3['Events'][0]['EventStatus'] == data2['Events'][0]['EventStatus']


def test_multiple_autorun_requests(client):
    """Test that starting auto-run multiple times does not create multiple threads or corrupt state."""
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    # Simulate multiple auto-run requests
    for _ in range(3):
        resp = client.post('/auto-run-scenario')
        assert resp.status_code in (200, 302)
    # Generate event and check state is valid
    client.post('/generate-event', data={'event_status': 'Scheduled'})
    resp = client.get('/metadata/scheduledevents')
    data = resp.get_json()
    assert data['Events'][0]['EventStatus'] == 'Scheduled'

def test_invalid_startrequests_eventid(client):
    """Test that POST with invalid EventId does not advance state."""
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    client.post('/generate-event', data={'event_status': 'Scheduled'})
    resp = client.post(
        '/metadata/scheduledevents',
        json={"StartRequests": [{"EventId": str(uuid.uuid4())}]},
        headers={"Metadata": "true"}
    )
    data = resp.get_json()
    # Should still be in Scheduled state
    assert data['Events'][0]['EventStatus'] == 'Scheduled'

def test_empty_eventstatus_scenario(client):
    """Test that a scenario with empty EventStatus dict is handled gracefully."""
    from main import scenarios
    scenarios['EmptyStatus'] = {
        "EventId": str(uuid.uuid4()),
        "NotBeforeDelayInMinutes": 5,
        "StartedDurationInMinutes": 2,
        "EventStatus": OrderedDict([]),
        "EventType": "Test",
        "Description": "Empty status test",
        "ScenarioDescription": "Test scenario with no status",
        "EventSource": "TestSource",
        "DurationInSeconds": 1
    }
    client.post('/set-scenario', data={'scenario': 'EmptyStatus'})
    resp = client.post('/generate-event', data={'event_status': 'Scheduled'})
    # Should redirect with error
    assert resp.status_code == 302
    resp = client.get('/metadata/scheduledevents')
    data = resp.get_json()
    assert data['Events'] == []

def test_no_new_events_after_completed(client):
    """Test that after last state, further auto-run or POSTs do not create new events."""
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    # Move to Completed
    for status in scenarios[scenario_name]['EventStatus'].keys():
        client.post('/generate-event', data={'event_status': status})
    # Try to advance again
    resp = client.post(
        '/metadata/scheduledevents',
        json={"StartRequests": [{"EventId": str(uuid.uuid4())}]},
        headers={"Metadata": "true"}
    )
    data = resp.get_json()
    assert data['Events'] == []

def test_notbefore_consistency(client):
    """Test that NotBefore is consistent for a given event and does not change unexpectedly."""
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    client.post('/generate-event', data={'event_status': 'Scheduled'})
    resp1 = client.get('/metadata/scheduledevents')
    data1 = resp1.get_json()
    notbefore1 = data1['Events'][0]['NotBefore']
    # Fetch again, should be the same
    resp2 = client.get('/metadata/scheduledevents')
    data2 = resp2.get_json()
    notbefore2 = data2['Events'][0]['NotBefore']
    assert notbefore1 == notbefore2

def test_resources_persistence_across_states(client):
    """Test that Resources field persists across all state transitions."""
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    custom_resources = "vmss_vm10,vmss_vm11"
    client.post('/generate-event', data={'event_status': 'Scheduled', 'resources': custom_resources})
    for status in scenarios[scenario_name]['EventStatus'].keys():
        client.post('/generate-event', data={'event_status': status, 'resources': custom_resources})
        resp = client.get('/metadata/scheduledevents')
        data = resp.get_json()
        if data['Events']:
            assert data['Events'][0]['Resources'] == ['vmss_vm10', 'vmss_vm11']

def test_api_version_query_param(client):
    """Test that api-version query param is accepted and does not affect logic."""
    scenario_name = list(scenarios.keys())[0]
    client.post('/set-scenario', data={'scenario': scenario_name})
    client.post('/generate-event', data={'event_status': 'Scheduled'})
    resp = client.get('/metadata/scheduledevents?api-version=2020-07-01')
    data = resp.get_json()
    assert 'DocumentIncarnation' in data
    assert 'Events' in data
