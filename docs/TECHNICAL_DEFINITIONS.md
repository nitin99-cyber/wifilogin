# Technical Definitions & Core Concepts

This document outlines the core technical concepts and libraries used in the architecture of WiFi Auto Login v3.0, explaining their purpose and how they integrate into the system.

## 1. psutil
`psutil` (Python system and process utilities) is a cross-platform library used for retrieving information on running processes and system utilization (CPU, memory, disks, network, sensors).
**Why it is used here:** In the WiFi Auto Login v3.0 project, `psutil` is specifically utilized to fetch real-time network interface statistics via `psutil.net_io_counters()`. By comparing the bytes sent and received every second, the application can calculate live download and upload throughput without wasting bandwidth on active internet speed tests.

## 2. ctypes
`ctypes` is a built-in Python library that provides C compatible data types and allows calling functions in DLLs (Dynamic Link Libraries) or shared libraries.
**Why it is used here:** It acts as a bridge between Python and low-level Windows APIs. For WiFi Auto Login, `ctypes` allows the application to directly invoke specific Windows OS functions (such as DPI awareness or window rendering hooks) that are not natively exposed by standard Python libraries.

## 3. icmp (Ping)
ICMP (Internet Control Message Protocol) is a network layer protocol used by network devices to diagnose network communication issues. The "Ping" utility relies on ICMP Echo Request and Echo Reply messages.
**Why it is used here:** The application uses ICMP pings as a highly reliable, lightweight health check to verify latency and true internet connectivity (e.g., pinging a reliable server like `8.8.8.8`). Checking if a WiFi network is connected is not enough; ICMP pings determine if traffic can actually reach the outside world, distinguishing between being stuck behind a captive portal versus having full internet access.

## 4. win32gui and win32con (Win32 API)
These are components of the `pywin32` package that expose the native Windows API (Win32) graphical and console functionalities to Python. `win32gui` provides functions to manipulate windows, and `win32con` contains constant definitions.
**Why they are used here:** They are used to programmatically hook into Windows OS events. Most critically in v3.0, they are used to listen to the Windows Power Management API for `WM_POWERBROADCAST` messages—specifically `PBT_APMRESUMEAUTOMATIC`. This allows the application to instantly detect when the laptop wakes up from sleep and trigger the network recovery workflow.

## 5. Tkinter Event Loop and root.after()
Tkinter is Python's standard GUI framework. The "Event Loop" (`mainloop()`) is a continuous loop that waits for and dispatches events or messages (like mouse clicks or keyboard presses). `root.after(delay_ms, callback)` is a Tkinter method that schedules a function to be called after a given time delay without blocking the event loop.
**Why it is used here:** The application needs to run periodic background checks (like connection monitoring, pinging, or state transitions) while simultaneously keeping the user interface responsive. The background worker threads send updates, and `root.after()` is used to safely schedule UI updates (like the new network speed) on the main thread, ensuring the app remains snappy and doesn't freeze or crash.

## 6. Finite State Machines (FSM)
A Finite State Machine is a computational model consisting of a finite number of states, transitions between those states, and actions. An FSM can be in exactly one of its states at any given time.
**Why it is used here:** Managing a network connection involves distinct, mutually exclusive phases (e.g., `IDLE`, `NETWORK_DETECTING`, `PORTAL_CHECK`, `AUTHENTICATING`, `CONNECTED`). Implementing the login and monitoring logic as an FSM ensures that the application behaves predictably. It prevents logical errors like attempting to log in twice concurrently, and ensures clean recovery paths if the network drops midway through authentication.
