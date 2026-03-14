import ctypes
import requests
import time
import subprocess
import threading
import logging
import platform
from typing import Optional, List
import os
import socket
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class USBMonitor:
    def __init__(self, allowed_serials: List[str], polling_interval: int = 5):
        self.allowed_serials = [s.strip() for s in allowed_serials if s.strip()]
        self.polling_interval = polling_interval
        self.is_usb_present = False
        self._monitor_thread = None
        self._stop_event = threading.Event()
        self._initial_check_done = threading.Event()

    def _get_connected_usb_serials(self) -> List[str]:
        """Get serial numbers of connected USB drives on Windows."""
        if platform.system() != "Windows":
            return []

        try:
            from win32com.client import GetObject

            wmi = GetObject("winmgmts:")
            usb_devices = wmi.ExecQuery(
                "SELECT * FROM Win32_PnPEntity WHERE Service='USBSTOR'"
            )
            serials = []
            for device in usb_devices:
                device_id = device.DeviceID
                if device_id and ("USBSTOR" in device_id or "USB\\" in device_id) and "\\" in device_id:
                    parts = device_id.split("\\")
                    if len(parts) > 2:
                        serial_candidate = parts[-1]
                        # Remove any suffix like &0 if present
                        if "&" in serial_candidate:
                            serial_candidate = serial_candidate.split("&")[0]
                        if len(serial_candidate) > 4 and not (
                            serial_candidate.startswith("MSFT")
                            or serial_candidate.startswith("GENERIC")
                        ):
                            serials.append(serial_candidate)
            logger.debug(f"Detected USB serials: {serials}")
            return serials
        except ImportError:
            logger.warning("pywin32 not installed. USB monitoring disabled.")
            return []
        except Exception as e:
            logger.error(f"Error getting USB serials: {e}")
            return []

    def _monitor_loop(self):
        logger.info("USB monitoring started")
        while not self._stop_event.is_set():
            try:
                current_serials = self._get_connected_usb_serials()
                allowed_present = any(
                    s in self.allowed_serials for s in current_serials
                )

                if allowed_present and not self.is_usb_present:
                    self.is_usb_present = True
                    logger.info("Allowed USB inserted - PC will stay unlocked")
                elif not allowed_present and self.is_usb_present:
                    self.is_usb_present = False
                    logger.info("Allowed USB removed")

            except Exception as e:
                logger.error(f"Error in USB monitor loop: {e}")

            self._initial_check_done.set()
            time.sleep(self.polling_interval)
        logger.info("USB monitoring stopped")

    def start(self):
        if not self.allowed_serials:
            logger.info("No USB serials configured - USB unlock disabled")
            return

        self._stop_event.clear()
        self._initial_check_done.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        logger.info("Waiting for initial USB check...")
        self._initial_check_done.wait(timeout=10)

    def stop(self):
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

    def is_allowed_usb_inserted(self) -> bool:
        """Check if the allowed USB is currently inserted."""
        return self.is_usb_present


class WindowsLocker:
    def __init__(
        self,
        api_url: str,
        dns_timer_api_url: str,
        allowed_usb_serials: List[str] = None,
    ):
        self.api_url = api_url
        self.dns_timer_api_url = dns_timer_api_url
        self.is_locked = False
        self.dns_thread = None
        self.stop_dns_thread = False

        # Lock pending state
        self.lock_warning_time: Optional[datetime] = None
        self.lock_grace_period_seconds = 300  # 5 minutes
        self.warning_shown = False

        # USB monitor
        self.usb_monitor = USBMonitor(allowed_usb_serials or [])

        # Load Windows API
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32

    def show_warning_toast(self):
        """Show a system-modal Windows MessageBox warning about the impending lock"""
        try:
            def show_message():
                # MB_OK (0) | MB_ICONWARNING (0x30) | MB_SYSTEMMODAL (0x1000) (Stops user and forces on top)
                self.user32.MessageBoxW(0, "Your computer will be locked in 5 minutes. Please save your work.", "Locker Warning", 0x30 | 0x1000)
            
            # Run in a thread so it doesn't block the main enforcement loop
            msg_thread = threading.Thread(target=show_message, daemon=True)
            msg_thread.start()
            logger.info("Displayed 5-minute system-modal lock warning")
        except Exception as e:
            logger.error(f"Failed to show warning notification: {e}")

    def lock_workstation(self) -> bool:
        """Lock the Windows workstation"""
        try:
            result = self.user32.LockWorkStation()
            print("Locking workstation...")
            if result:
                logger.info("Workstation locked successfully")
                self.is_locked = True
                self.lock_warning_time = None
                self.warning_shown = False
                return True
            else:
                logger.error("Failed to lock workstation")
                return False
        except Exception as e:
            logger.error(f"Error locking workstation: {e}")
            return False

    def check_unlock_condition(self) -> bool:
        """Check API for unlock condition"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(self.api_url, timeout=5)
                response.raise_for_status()
                data = response.json()

                # API returns {"unlock": true/false} or similar
                should_unlock = data.get("unlock", False)
                logger.info(f"Unlock condition: {should_unlock}")
                return should_unlock

            except requests.RequestException as e:
                logger.error(
                    f"Error checking unlock condition (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
                    continue
                return False
            except Exception as e:
                logger.error(
                    f"Error parsing unlock response (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
                    continue
                return False
        return False

    def get_dns_timer_value(self) -> Optional[int]:
        """Get timer value from API for DNS operations"""
        try:
            response = requests.get(self.dns_timer_api_url, timeout=5)
            response.raise_for_status()
            data = response.json()

            # Assuming API returns {"timer_seconds": 300} or similar
            timer_value = data.get("timer_seconds")
            if timer_value and isinstance(timer_value, (int, str)):
                return int(timer_value)

            logger.warning("No valid timer value found in API response")
            return None

        except requests.RequestException as e:
            logger.error(f"Error getting DNS timer value: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing DNS timer response: {e}")
            return None

    def flush_dns_cache(self) -> bool:
        """Flush Windows DNS cache"""
        try:
            # Use ipconfig to flush DNS cache
            result = subprocess.run(
                ["ipconfig", "/flushdns"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                logger.info("DNS cache flushed successfully")
                return True
            else:
                logger.error(f"Failed to flush DNS cache: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error flushing DNS cache: {e}")
            return False

    def modify_hosts_file(self) -> bool:
        """Add YouTube domains to hosts file pointing to 127.0.0.1"""
        youtube_domains = [
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
        ]

        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"

        try:
            # Read current hosts file
            with open(hosts_path, "r") as f:
                hosts_content = f.read()

            # Check if YouTube entries already exist
            new_entries = []
            for domain in youtube_domains:
                entry = f"127.0.0.1 {domain}"
                if entry not in hosts_content:
                    new_entries.append(entry)

            if new_entries:
                # Add new entries
                with open(hosts_path, "a") as f:
                    f.write("\n# Added by Windows Locker\n")
                    for entry in new_entries:
                        f.write(entry + "\n")

                logger.info(f"Added {len(new_entries)} YouTube entries to hosts file")
                return True
            else:
                logger.info("YouTube entries already exist in hosts file")
                return True

        except PermissionError:
            logger.error(
                "Permission denied. Run as administrator to modify hosts file."
            )
            return False
        except Exception as e:
            logger.error(f"Error modifying hosts file: {e}")
            return False

    def dns_manager_loop(self):
        """Background thread to manage DNS operations"""
        logger.info("DNS manager thread started")

        while not self.stop_dns_thread:
            try:
                # Get timer value from API
                timer_seconds = self.get_dns_timer_value()

                if timer_seconds:
                    logger.info(
                        f"Waiting {timer_seconds} seconds before DNS operations"
                    )

                    # Wait for the specified time
                    for _ in range(timer_seconds):
                        if self.stop_dns_thread:
                            break
                        time.sleep(1)

                    if not self.stop_dns_thread:
                        # Perform DNS operations
                        logger.info("Performing DNS operations...")
                        self.flush_dns_cache()
                        self.modify_hosts_file()
                else:
                    # Default timer if API fails
                    logger.warning("Using default timer (300 seconds)")
                    time.sleep(300)

            except Exception as e:
                logger.error(f"Error in DNS manager loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

        logger.info("DNS manager thread stopped")

    def start_dns_manager(self):
        """Start the DNS management background thread"""
        if self.dns_thread is None or not self.dns_thread.is_alive():
            self.stop_dns_thread = False
            self.dns_thread = threading.Thread(
                target=self.dns_manager_loop, daemon=True
            )
            self.dns_thread.start()
            logger.info("DNS manager thread started")

    def stop_dns_manager(self):
        """Stop the DNS management background thread"""
        self.stop_dns_thread = True
        if self.dns_thread and self.dns_thread.is_alive():
            self.dns_thread.join(timeout=5)
            logger.info("DNS manager thread stopped")

    def is_workstation_locked(self) -> bool:
        """Check if the workstation is currently locked"""
        try:
            # Use a more reliable method to detect if workstation is locked
            # Check if there's any foreground window - if not, likely locked
            hwnd = self.user32.GetForegroundWindow()
            return hwnd == 0
        except Exception as e:
            logger.error(f"Error checking workstation lock state: {e}")
            return False

    def enforce_lock_state(self, should_be_unlocked: bool):
        """Enforce the server's lock state on the workstation"""
        is_currently_locked = self.is_workstation_locked()
        usb_enabled = len(self.usb_monitor.allowed_serials) > 0

        # Determine target state based on USB and Server
        target_unlock = should_be_unlocked
        
        # If USB is configured and inserted, it ALWAYS overrides the server value to keep unlocked
        if usb_enabled and self.usb_monitor.is_allowed_usb_inserted():
            target_unlock = True
            
        if target_unlock:
            # Cancel any pending lock if we are now allowed to stay unlocked
            if self.lock_warning_time is not None:
                logger.info("Unlock condition met. Cancelling impending lock.")
                self.lock_warning_time = None
                self.warning_shown = False

            if is_currently_locked:
                logger.info(
                    "Workstation should be unlocked, but is currently locked (user must unlock manually)"
                )
            else:
                logger.info("Keeping workstation unlocked")
            self.is_locked = False
        else:
            # We need to be locked
            if not is_currently_locked:
                # If we were previously fully locked (e.g. grace period expired and we locked the PC),
                # but the user manually unlocked it somehow, DO NOT give another 5 minutes. Lock immediately.
                if self.is_locked:
                    logger.warning("Workstation was manually unlocked during a required lock state. Locking immediately.")
                    self.lock_workstation()
                # Otherwise, if we aren't locked yet and weren't previously fully locked, start or check the grace period
                elif self.lock_warning_time is None:
                    # Start the countdown
                    logger.info("Starting 5-minute grace period before locking")
                    self.lock_warning_time = datetime.now()
                    self.show_warning_toast()
                    self.warning_shown = True
                else:
                    # Check if countdown has expired
                    elapsed = (datetime.now() - self.lock_warning_time).total_seconds()
                    remaining = int(self.lock_grace_period_seconds - elapsed)
                    if remaining <= 0:
                        logger.info("Grace period expired. Locking now.")
                        self.lock_workstation()
                    else:
                        if remaining % 60 < 5:  # Log roughly every minute
                            logger.info(f"Locking in {remaining} seconds...")
            else:
                logger.info("Workstation is locked - correct state")
                self.is_locked = True
                self.lock_warning_time = None
                self.warning_shown = False


    def run(self):
        """Main application loop"""
        logger.info("Starting Windows Locker application")

        # Start USB monitor
        self.usb_monitor.start()

        # Start DNS manager
        self.start_dns_manager()

        consecutive_errors = 0
        max_consecutive_errors = 5

        try:
            while True:
                try:
                    # Always check the server for the current state
                    should_be_unlocked = self.check_unlock_condition()

                    # Reset error counter on successful check
                    consecutive_errors = 0

                    # Enforce the server's lock state
                    self.enforce_lock_state(should_be_unlocked)

                    # Wait before next check
                    time.sleep(5)

                except Exception as e:
                    consecutive_errors += 1
                    logger.error(
                        f"Error in main loop (consecutive errors: {consecutive_errors}): {e}"
                    )

                    if consecutive_errors >= max_consecutive_errors:
                        usb_enabled = len(self.usb_monitor.allowed_serials) > 0
                        if usb_enabled and self.usb_monitor.is_allowed_usb_inserted():
                            logger.error(f"Too many consecutive errors ({max_consecutive_errors}), but allowed USB is inserted. Keeping workstation unlocked.")
                        else:
                            logger.error(
                                f"Too many consecutive errors ({max_consecutive_errors}), locking workstation for safety"
                            )
                            self.lock_workstation()
                        consecutive_errors = 0  # Reset after taking safety action

                    # Wait longer after errors
                    time.sleep(10)

        except KeyboardInterrupt:
            logger.info("Application stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
        finally:
            self.stop_dns_manager()
            self.usb_monitor.stop()


def main():
    import sys

    client_name = os.environ.get("CLIENT_NAME") or (len(sys.argv) > 1 and sys.argv[1])

    if client_name is None:
        client_name = socket.gethostname()
        logger.info(f"No client name provided, using hostname: {client_name}")

    server_url = os.environ.get("SERVER_URL") or "http://localhost:8000"
    API_URL = f"{server_url}/client/{client_name}/unlock-status"
    DNS_TIMER_API_URL = f"{server_url}/client/{client_name}/youtube-timer"

    # Parse allowed USB serials from environment (comma-separated)
    usb_serials_env = os.environ.get("ALLOWED_USB_SERIALS", "")
    print(usb_serials_env)
    allowed_usb_serials = [s.strip() for s in usb_serials_env.split(",") if s.strip()]

    if allowed_usb_serials:
        logger.info(f"USB unlock enabled for: {allowed_usb_serials}")
    else:
        logger.info("No USB serials configured - USB unlock disabled")

    logger.info(f"Starting client '{client_name}' connecting to {server_url}")

    # Check if running as administrator for DNS operations
    try:
        import ctypes.wintypes

        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if not is_admin:
            logger.warning("Not running as administrator. DNS modifications may fail.")
    except:
        logger.warning("Unable to check administrator status")

    # Create and run the locker
    locker = WindowsLocker(API_URL, DNS_TIMER_API_URL, allowed_usb_serials)
    locker.run()


if __name__ == "__main__":
    main()
