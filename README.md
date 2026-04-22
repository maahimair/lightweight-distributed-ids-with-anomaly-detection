# lightweight-distributed-ids-with-anomaly-detection

## Overview
This project focuses on building a lightweight Intrusion Detection System (IDS) for IoT networks. It uses Snort for rule-based detection, Python to simulate IoT traffic, and Wireshark for analyzing packets. The goal was to create a simple and efficient system that can detect suspicious activity even in low-resource environments.

## Key Features
- Monitors network traffic in real time  
- Uses custom Snort rules to detect abnormal behavior  
- Simulates IoT sensor data (temperature and humidity)  
- Supports packet-level analysis using Wireshark  
- Designed to run in resource-constrained environments  

## Tech Stack
- Python  
- Snort  
- Wireshark  

## Project Structure
- `ids_monitor.py` – Handles traffic monitoring and detection  
- `temperature_sensor.py` – Simulates temperature sensor data  
- `humidity_sensor.py` – Simulates humidity sensor data  
- `commands_on_terminal_for_local.rules.pdf` – Contains Snort rules and setup commands  

## How It Works
The system monitors incoming traffic using Snort and applies custom rules to detect unusual patterns. To test the system, Python scripts generate simulated IoT traffic. Wireshark is used to inspect packets and verify how effectively the system detects potential threats.

## What I Learned
- How intrusion detection systems work in practice  
- Writing and testing custom Snort rules  
- Basics of packet analysis using Wireshark  
- Simulating network traffic for security testing  

## Future Improvements
- Add anomaly detection using machine learning  
- Build a simple dashboard for alerts  
- Improve rule accuracy to reduce false positives  
- Expand detection for more IoT-related attacks  
