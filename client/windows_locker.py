import ctypes
import requests
import time
import subprocess
import threading
import logging
from typing import Optional
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class WindowsLocker:
    def __init__(self, api_url: str, dns_timer_api_url: str):
        self.api_url = api_url
        self.dns_timer_api_url = dns_timer_api_url
        self.is_locked = False
        self.dns_thread = None
        self.stop_dns_thread = False

        # Load Windows API
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32

    def lock_workstation(self) -> bool:
        """Lock the Windows workstation"""
        try:
            result = self.user32.LockWorkStation()
            if result:
                logger.info("Workstation locked successfully")
                self.is_locked = True
                return True
            else:
                logger.error("Failed to lock workstation")
                return False
        except Exception as e:
            logger.error(f"Error locking workstation: {e}")
            return False

    def check_unlock_condition(self) -> bool:
        """Check API for unlock condition"""
        try:
            response = requests.get(self.api_url, timeout=5)
            response.raise_for_status()
            data = response.json()

            # Assuming API returns {"unlock": true/false} or similar
            should_unlock = data.get("unlock", False)
            logger.info(f"Unlock condition: {should_unlock}")
            return should_unlock

        except requests.RequestException as e:
            logger.error(f"Error checking unlock condition: {e}")
            return False
        except Exception as e:
            logger.error(f"Error parsing unlock response: {e}")
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

    def run(self):
        """Main application loop"""
        logger.info("Starting Windows Locker application")

        # Start DNS manager
        self.start_dns_manager()

        try:
            while True:
                # Check if we should unlock
                if self.is_locked and self.check_unlock_condition():
                    logger.info("Unlock condition met, keeping workstation unlocked")
                    self.is_locked = False
                    time.sleep(10)  # Wait before next check
                    continue

                # If not locked, lock it
                if not self.is_locked:
                    self.lock_workstation()

                # Wait before next check
                time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Application stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
        finally:
            self.stop_dns_manager()


def main():
    import sys

    # Get client name from command line or use hostname
    if len(sys.argv) > 1:
        client_name = sys.argv[1]
    else:
        import socket

        client_name = socket.gethostname()
        logger.info(f"No client name provided, using hostname: {client_name}")

    # Configuration - update these URLs
    SERVER_URL = "http://localhost:8000"
    API_URL = f"{SERVER_URL}/client/{client_name}/unlock-status"
    DNS_TIMER_API_URL = f"{SERVER_URL}/client/{client_name}/youtube-timer"

    logger.info(f"Starting client '{client_name}' connecting to {SERVER_URL}")

    # Check if running as administrator for DNS operations
    try:
        import ctypes.wintypes

        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if not is_admin:
            logger.warning("Not running as administrator. DNS modifications may fail.")
    except:
        logger.warning("Unable to check administrator status")

    # Create and run the locker
    locker = WindowsLocker(API_URL, DNS_TIMER_API_URL)
    locker.run()


if __name__ == "__main__":
    main()
