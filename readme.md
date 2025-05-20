# Scheduled Events Responder

A Flask-based web application for simulating Azure Scheduled Events and IMDS (Instance Metadata Service) event flows. This tool is designed for testing and development scenarios where you want to emulate Azure platform events, such as Live Migration, User Reboot, Maintenance, and more.

## Features

- Select from multiple predefined scenarios (Live Migration, User Reboot, Redeploy, etc.)
- Manually generate events for each scenario state (Scheduled, Started, Completed, etc.)
- Automatically run a scenario through all its states with realistic timing
- Set custom resources for each event (default: `vmss_vm1`)
- Endpoint simulates the IMDS endpoint `/metadata/scheduledevents` and can be called from  within our outside of the test  VM  
- Supports simulating event approvals  via IMDS POST 

## Getting Started

### Prerequisites

- Python 3.8+
- `pip` (Python package manager)

### Installation

1. Clone this repository:
    ```sh
    git clone https://github.com/your-org/ScheduledEventsResponder.git
    cd ScheduledEventsResponder
    ```

2. Install dependencies:
    ```sh
    python -m venv .venv    
    .\.venv\Bin\Activate.ps1 #On PowerShell
    pip install -r requirements.txt
    ```

3. Run the application:
    ```sh
    python main.py
    ```

4. Open your browser and navigate to [http://localhost](http://localhost)

## Usage

### Selecting and Running Scenarios

1. **Select a Scenario**
    - Use the dropdown at the top of the page to select a scenario (e.g., Live Migration, User Reboot).
    - Click **Set Scenario** to activate it.

2. **Set Resources (Optional)**
    - Under "Run Scenario", enter a comma-separated list of resource names in the **Resources** field.
    - Default is `vmss_vm1`.

3. **Generate Events Manually**
    - Select an event status from the dropdown (e.g., Scheduled, Started).
    - Click **Generate Event** to create an event in that state.

4. **Automatically Run Scenario**
    - Click **Automatically Run Scenario** to progress through all states with realistic timing.
    - A countdown timer will appear showing time until the next event state.

5. **Stop Playback**
    - Click **Stop Playback** to halt automatic progression.

6. **View Last Event**
    - The "Last Event" section displays the most recent event in IMDS format.

### IMDS Endpoint

- The app exposes `/metadata/scheduledevents` for both GET and POST.
- **GET** returns the current event(s) in IMDS format.
- **POST** with a JSON body containing `StartRequests` and a matching `EventId` will immediately advance the event to the next state (simulating event approval).

    Example:
    ```sh
    curl -H "Metadata:true" -X POST -d '{"StartRequests": [{"EventId": "YOUR_EVENT_ID"}]}' http://localhost:5000/metadata/scheduledevents?api-version=2020-07-01
    ```

- For more information on Azure Scheduled Events and the IMDS API, see the [Azure Scheduled Events documentation](https://learn.microsoft.com/en-us/azure/virtual-machines/windows/scheduled-events).

## Customization

- A few common scenarios are defined in `main.py` in the `scenarios` dictionary.
- You can add or modify scenarios as needed. 

## License

MIT License

---

*This tool is for development and testing purposes only and is not intended for production use.*