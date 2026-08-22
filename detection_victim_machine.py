# ransomware_detector.py
# script to detect ransomware-like behavior using watchdog,
# identify the  process with psutil, and log events with loguru.
# should run on the "victim" system to monitor for attacks.

import os
import time
import psutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from loguru import logger

# --- Configuration ---
 
WATCH_DIRECTORY = "C:\\Users\\marw\\Downloads\\testfolder"  .
# 
FILE_MOD_THRESHOLD = 10
# 
FILE_RENAME_THRESHOLD = 5
# 
TIME_WINDOW = 5.0
# ---

# --- Loguru Configuration ---
logger.add("detector_log.log", rotation="10 MB", retention="7 days", level="INFO")
# ---

class RansomwareDetector(FileSystemEventHandler):
    """
    A custom event handler that monitors for ransomware-like file system activity.
    """
    def __init__(self):
        super().__init__()
        # Lists to store timestamps of recent events
        self.file_mod_events = []
        self.file_rename_events = []

    def on_modified(self, event):
        """Called by watchdog when a file is modified."""
        if not event.is_directory:
            logger.info(f"File modified: {event.src_path}")
            self.file_mod_events.append(time.time())
            self.check_for_alert()

    def on_moved(self, event):
        """Called by watchdog when a file is moved or renamed."""
        if not event.is_directory and event.dest_path.endswith(".locked"):
            logger.info(f"File renamed to .locked: {event.dest_path}")
            self.file_rename_events.append(time.time())
            self.check_for_alert()

    def check_for_alert(self):
        """Analyzes recent events to see if they cross defined thresholds."""
        current_time = time.time()
        
        # Purge old events outside the time window
        self.file_mod_events = [t for t in self.file_mod_events if current_time - t < TIME_WINDOW]
        self.file_rename_events = [t for t in self.file_rename_events if current_time - t < TIME_WINDOW]

        # Check if the number of recent events has exceeded our security thresholds
        if len(self.file_mod_events) >= FILE_MOD_THRESHOLD or len(self.file_rename_events) >= FILE_RENAME_THRESHOLD:
            self.trigger_alert()
            # Clear event lists after an alert to prevent continuous alerts
            self.file_mod_events.clear()
            self.file_rename_events.clear()

    def find_culprit_process(self):
        """
        Uses psutil to find the process with the highest I/O write activity,
        which is a strong indicator of a ransomware process.
        """
        suspicious_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'io_counters', 'username', 'cmdline']):
            try:
                # Check for high write operations
                if proc.info['io_counters'] and proc.info['io_counters'].write_bytes > 1024 * 1024: # > 1MB
                     suspicious_processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Sort by the most write bytes to find the most likely culprit
        suspicious_processes.sort(key=lambda x: x['io_counters'].write_bytes, reverse=True)
        return suspicious_processes[0] if suspicious_processes else None


    def trigger_alert(self):
        """
        Logs a critical security alert and uses psutil to find and log
        details about the suspected malicious process.
        """
        culprit = self.find_culprit_process()
        
        log_message = (
            "POSSIBLE RANSOMWARE ACTIVITY DETECTED!\n"
            f"Directory: '{WATCH_DIRECTORY}'\n"
            f"Reason: High frequency of file modifications and/or renames observed."
        )

        if culprit:
            log_message += (
                "\n\n--- Suspicious Process Identified ---\n"
                f"PID: {culprit['pid']}\n"
                f"Name: {culprit['name']}\n"
                f"Username: {culprit['username']}\n"
                f"I/O Write Bytes: {culprit['io_counters'].write_bytes / (1024*1024):.2f} MB\n"
                f"Command: {' '.join(culprit['cmdline']) if culprit['cmdline'] else 'N/A'}"
            )
        else:
            log_message += "\nCould not identify a specific culprit process based on I/O."

        logger.critical(log_message)
        logger.warning("In a real system, this would trigger defensive actions like isolating the machine.")


if __name__ == "__main__":
    # Ensure the directory to be watched exists before starting
    if not os.path.isdir(WATCH_DIRECTORY):
        logger.error(f"The directory '{WATCH_DIRECTORY}' does not exist.")
        logger.error("Please create it or change the WATCH_DIRECTORY variable in the script.")
    else:
        logger.success(f"Starting security monitor on directory: '{WATCH_DIRECTORY}'")
        logger.info("Press Ctrl+C to stop.")

        event_handler = RansomwareDetector()
        observer = Observer()
        observer.schedule(event_handler, WATCH_DIRECTORY, recursive=True)
        
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            logger.info("Detector stopped by user.")
        observer.join()
