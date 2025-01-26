#FOLLOW THIS CYNICALLY, WITHOUT DEVIATIONS. IF YOU SEE OTHER PROBLEMS IN THE CODE, WRITE DOWN THE PROBLEMATIC METHOD IN A NOTEPAD, AND MOVE ON! REMOVE ALL TRY/EXCEPTS AND RAISE THAT CAN'T DO ANYTHING ABOUT THE PROBLEM, DON'T RERAISE DUE TO FAILED RECOVERY, OR ARE'NT VERY ESSENTIAL FOR LOGGING, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS. REMOVE ALL LEVEL COMMENTS EXCEPT FROM LEVEL 1. MAP ALL LEVEL 1, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS. REPLACE EVERY EXCEPTION TYPE WHERE SENSIBLE, IF IT'S RERAISE OR NOT, WITH CUSTOM EXCEPTIONS, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS. TRACK EVERY EXCEPTION TYPE, IF IT'S RERAISE OR NOT, TO WRITE WHERE THEY END UP IN OTHER TRY/EXCEPTS, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS. CHECK WHERE I GET DUPLICATE EXCEPTION TYPES AND REPLACE WITH CUSTOM EXCEPTIONS, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS.

import re
import time
from datetime import datetime
from collections import namedtuple
import asyncio
from concurrent.futures import Future
import serial
import serial.tools.list_ports
import threading
import queue

import tkinter as tk
from tkinter import ttk

from dataclasses import dataclass
from typing import Any, Optional


class NoPingResponseTimeoutError(Exception):
    "Raised when the device haven't given a ping response for the set amount of time"
    pass

class PortNotInitializedError(Exception):
    """Raised when trying to use an unitialized serial port."""
    pass

class InvalidTimestampTypeError(Exception):
    """Raised when a datetime timestamp is expected, but got something else."""
    pass

class ErrorTools:
    def get_origin_method(exception):
        """
        Extracts the name of the origin method where the exception occurred.

        Args:
        exception (Exception): The exception object.

        Returns:
        str: The name of the origin method where the error occurred.
        """
        tb = exception.__traceback__

        #Traverse to the last traceback in the chain
        while tb.tb_next:
            tb = tb.tb_next

        #Extract the function name from the last frame
        origin_function = tb.tb_frame.f_code.co_name
        return origin_function
    
    def check_nested_error(e,  exception):
        #Check if the string for the requested nested error is in the exception
        exception_string = exception.__name__
        return True if exception_string in str(e) else False

class TimeManager:
    time_string_format = "%m/%d/%Y %H:%M:%S"

    class Timer:
        def __init__(self, duration_ms = None):
            self.duration_ms = duration_ms
            self.last_blocking_timer_call = time.monotonic()

            self.start_time = 0

            if not isinstance(self.duration_ms, (int, None)):
                raise TypeError(f"duration is of type {type(self.duration).__name__}, expected int") #Level 1
            
            self.start_time = time.monotonic()

        def get_elapsed_time_milliseconds(self):
            elapsed_time = self.get_elapsed_time()
            return elapsed_time * 1000

        def get_elapsed_time(self):
            current_time = time.monotonic()
            elapsed_time = current_time - self.start_time #Subtracting two datetime objects gives a datetime.deltatime object
            return elapsed_time
        def timed_out(self):
            return self.get_elapsed_time_milliseconds() >= self.duration_ms
        def reset_timer(self):
            self.start_time = time.monotonic()

        async def wait_until_duration(self, iteration_start):
            """
            Ensures that total elapsed time since 'iteration_start' is
            at least 'self.duration_ms' milliseconds.

            Returns the total elapsed time in seconds.
            """
            so_far = time.monotonic() - iteration_start
            required_seconds = self.duration_ms / 1000.0 # convert ms -> s

            # If the iteration so far is less than required_seconds, sleep the difference
            if so_far < required_seconds:
                asyncio.sleep(required_seconds - so_far)

            # Compute and return the final total
            iteration_end = time.monotonic()
            return iteration_end - iteration_start
        
    def string_to_datetime(self, datetime_string):
        """
        Convert a date string into a datetime object using the provided format.

        :param date_string: The date string to be converted, e.g. "12/31/2024 23:59:59".
        :param time_string_format: The datetime format, default "%m/%d/%Y %H:%M:%S".
        :return: A datetime object if parsing is successful.
        :raises ValueError: If the date string does not match the format.
        """
        try:
            return datetime.strptime(datetime_string, self.time_string_format)
        except ValueError:
            raise ValueError

    def datetime_to_string(self, datetime):
        """
        Convert a datetime object into a formatted string using the provided format.

        :param dt_obj: The datetime object to be converted.
        :param time_string_format: The datetime format, default "%m/%d/%Y %H:%M:%S".
        :return: A date string in the specified format.
        :raises ValueError: If the format string is invalid.
        """
        try:
            return datetime.strftime(self.time_string_format)
        except ValueError:
            raise ValueError

class StringMessageHandler:

    MessageStruct = namedtuple('MessageStruct', ['category', 'message']) #Categories, enforce, structure! See "signals" in the "official documentation" file.

    #If the serial part of this system was a library, these should really be set by Serial Manager as a class attribute
    messages = {
        "ping_pc_arduino": MessageStruct("1", "1"),
        "ping_arduino_pc": MessageStruct("1", "2"),
        "temperature_reading": MessageStruct("2", "1"),
        "force_emergency_stop": MessageStruct("4", "0"),
        "emergency_alarm": MessageStruct("9", "0"),
        "thermosensor_error": MessageStruct("9", "1"),
        "watchog_pwm_frozen": MessageStruct("9", "2"),
        "furnace_overheat": MessageStruct("9", "3"),
    }

    valid_messages = ", ".join(messages.keys())

    message_part_separator = ","

    @dataclass
    class FullMessage:
        message_key: str
        value: Optional[Any] = None
        timestamp: Optional[datetime] = None
        message_valid: bool = False

    def build_message(self, full_message):
        # Build the full message string to be sent
        outgoing_parts = []

        # Construct the full message string
        message = full_message.message_key #No need
        outgoing_parts.append(message)
        outgoing_parts.append(full_message.value if full_message.value is not None else "NaN")
        outgoing_parts.append(full_message.timestamp if full_message.timestamp is not None else "NaN")

        # Join all parts with the part separator character
        outgoing = self.message_part_separator.join(outgoing_parts)

        return outgoing

    def parse_message(self, message_str):
        message_valid = False
        expected_parts = 3

        # Split the message string into parts
        incoming_parts = message_str.split(self.message_part_separator)

        # Check if the message has the correct number of parts
        if len(incoming_parts) != expected_parts:
            print(f"Message '{message_str}' has an unexpected number of parts. Expected {expected_parts}.")
        else:
            message_valid = True

        if message_valid:
            parsed = {
                'message_category': incoming_parts[0],
                'value': incoming_parts[1],
                'timestamp': incoming_parts[2],
                'message_valid': True
            }
        else:
            parsed = {
                'message_category': None,
                'value': None,
                'timestamp': None,
                'message_valid': False
            }

        return parsed

    #Level 2
    def encode_message(self, full_message):
        # Get the message type value
        message_value = self.messages[full_message.message_key]

        string_message_key = self.message_part_separator.join([
            str(message_value.category),
            str(message_value.message)
        ])
        full_message.message_key = string_message_key

        # Add value if required
        if full_message.value is not None:
            full_message.value = str(full_message.value)
        else:
            full_message.value = "NaN"

        # Add the timestamp if required
        if full_message.timestamp is not None:
            try:
                formatted_timestamp = TimeManager.datetime_to_string(full_message.timestamp) #Level 2
            except ValueError:
                print(f"Format is incorrect, expected {TimeManager.time_string_format}. Big letters can include a zero as first digit, like 05, small letters cannot.")
                raise
            full_message.timestamp = str(formatted_timestamp)
        else:
            full_message.timestamp = "NaN"
        return full_message

    #Level 2
    def decode_message(self, parsed):
        # Try to find the message key based on category and message
        message_valid = False
        message_key = None
        value = None
        timestamp = None

        if parsed["message_valid"]:
            for key, msg_val in self.messages.items():
                category, message = parsed['message_category'].split(self.message_part_separator)
                if msg_val.category == category and msg_val.message == message:
                    message_key = key
                    break
            if message_key is None:
                print(f"Unknown message type for category '{parsed['message_category']}'. Setting to None, the message to invalid, and moving on.")
            else:
                message_valid = True

            value = parsed["value"] if parsed["value"] != "NaN" else None
            timestamp = parsed["timestamp"] if parsed["timestamp"] != "NaN" else None

            if timestamp is not None:
                try:
                    converted_datetime = TimeManager.string_to_datetime(timestamp)
                except ValueError:
                    print(f"Format is incorrect, expected {self.time_manager.time_string_format}. Big letters can include a zero as first digit, like 05, small letters cannot. Setting to None, the message to invalid, and moving on.")
                    converted_datetime = None
                    message_valid = False
                timestamp = converted_datetime

        return self.FullMessage(message_key, value, timestamp, message_valid)


class SerialConnectionManager:

    port_initialization_time = 1.6

    def __init__(self, port_name, baud_rate=9600, timeout=2, gui_queue=None):
        self.serial_handshake_handler = None #Needs instanciation of SerialHandshakeHandler at a higher level before being set due to circular dependencies
        self.serial_message_handler = None #Same, but for SerialMessageHandler
        
        self.port_name = port_name # Store the COM port name (like COM18)
        self.baud_rate = baud_rate # Store the baud rate
        self.timeout = timeout # Store the timeout

        self.serial_port = None
        self.serial_loss = True

        self.all_serial_ports = []

        self.recent_port_name = self.port_name #Compared with self.port_name to check port name change
        self.connect_in_progress = False

        self.lock = asyncio.Lock()
        self.gui_queue = gui_queue # Optional: For GUI updates

        try:
            self.set_port_name()
        except:
            raise

        if not isinstance(self.baud_rate, int):
            print(f"Baudrate {self.baud_rate} not an integer")
            raise TypeError(f"Baudrate {self.baud_rate} not an integer")

        elif not isinstance(self.timeout, (int, float)):
            print(f"Timeout {self.timeout} not an integer or float")
            raise TypeError(f"Timeout {self.timeout} not an integer or float")

    async def setup_COM(self):
        # Setup serial connection
        if self.connect_in_progress or not self.serial_loss:
            return # Avoid multiple reconnection attempts at once. Also, avoids deadlocks between this method and pass_message.
        self.connect_in_progress = True

        # Avoid ping confusion, can't ping while setting up the port
        self.serial_handshake_handler.stop_ping_loop()
        #Reading serial messsage are done from here, for local error handling and avoiding ping_task from stealing the ping response message
        self.serial_message_handler.stop_serial_readings()

        self.gui_queue.put({"serial_status": "connecting"})

        if not self.port_name == self.recent_port_name:
            self.recent_port_name == self.port_name

        try:
            await self.initialize_port()
        except Exception:
            if not ErrorTools.check_nested_error(e, "PerrmissionError"):
                raise

        self.serial_message_handler.find_message("ping_pc_arduino", purge=True)

        connection_success = False
        while not connection_success:
            if not self.port_name == self.recent_port_name:
                try:
                    await self.initialize_port()
                    self.recent_port_name == self.port_name
                except Exception as e:
                    raise
            # Attempt to connect to the specified port
            try:
                connection_success = await self.attempt_connection()
            except Exception as e:
                raise
            #No success? Wrong! Do it again! (No dark sarcasm in the classroom)
        
        self.serial_loss = False #Got this far? Serial port is confirmed.
        self.gui_queue.put({"serial_error": "running smoothy"})
        self.gui_queue.put({"serial_status": "serial connection established"})
        
        #Success, start or resume periodic serial processes
        self.serial_message_handler.start_serial_readings()
        self.serial_handshake_handler.start_ping_loop()
        self.connect_in_progress = False

    async def attempt_connection(self):
        try:
            handshake_result = await self.serial_handshake_handler.ping_handshake()
        except:
            raise
        if handshake_result:
            print(f"Handshake completed on port {self.serial_port.name} at {self.serial_port.baudrate} baud.")
            return True
        else:
            return False

    async def initialize_port(self):
        loop = asyncio.get_running_loop()

        try:
            # Open serial port in executor to prevent blocking
            async with self.lock:
                self.serial_port = await loop.run_in_executor(
                    None,
                    lambda: serial.Serial(self.port_name, self.baud_rate, timeout=self.timeout)
                )
        except (serial.SerialException) as e:
            print(f"Error setting up port: {e}")
            if ErrorTools.check_nested_error(e, FileNotFoundError):
                    raise FileNotFoundError #Level 1
            elif ErrorTools.check_nested_error(e, PermissionError):
                    raise PermissionError #Level 1

        await asyncio.sleep(self.port_initialization_time) # Wait for the serial port to initialize

    async def clean_connection(self):
        try:
            await self.close_connection()
        except:
            print(f"Serial port is not initialized.") #Then there's no problem!
        self.serial_port = None

    async def close_connection(self):
        if not self.serial_port:
            print(f"Serial port is not initialized.")
            raise PortNotInitializedError()

        if not self.serial_port.is_open:
            print(f"Serial connection on {self.serial_port} is already closed.")
            return #This can pass silently

        try:
            async with self.lock:
            # Close serial port in executor to prevent blocking
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.serial_port.close)
                print(f"Serial connection on {self.serial_port.name} closed.")
        except (serial.SerialException) as e:
            print(f"Serial exception when attempting to close port {self.serial_port.name}.")
            raise e

    def update_for_serial_error(self, e):
        self.serial_loss = True
        
        if not self.gui_queue is None:
            if ErrorTools.check_nested_error(e, "FileNotFound"):
                self.gui_queue.put({"serial_error": "Serial COM port not found. Connect device, or set correct COM port as seen in device manager"})
            elif ErrorTools.check_nested_error(e, "PermissionError"):
                self.gui_queue.put({"serial_error": "Serial COM port allready in use or denied. Verify that nothing else is using the COM port, or set correct COM port as seen in device manager"})
            elif isinstance(e, NoPingResponseTimeoutError):
                self.gui_queue.put({"serial_error": "No communication with Arduino. Check that the device is connected to the set COM port as seen in device manager, and verify it's working."})
            self.gui_queue.put({"serial_status": "serial connection lost"})

    def get_connection_info(self):
        return {
            'serial_loss': self.serial_loss,
            'port_name': self.port_name,
            'baud_rate': self.baud_rate,
            'timeout': self.timeout,
            'COM_description': self.serial_port.description,
            'port_open': True if self.serial_port.is_open else False
        }

    def set_port_name(self, port_name):
        if not isinstance(port_name, (str, int)):
            raise TypeError(f"port_name must be a string or int, got {type(port_name).__name__}")

        elif isinstance(port_name, int):
            if port_name < 0:
                raise ValueError(f"port_name cannot be negative, got {port_name}")
            self.port_name = "COM" + str(port_name)
        elif isinstance(port_name, str):
            if not re.fullmatch(r"(COM\d+|\d+)", port_name):
                raise ValueError(f"port_name must be 'COM' followed by a number (e.g., COM18), or just a number (e.g., 18). Got {port_name}")
            elif port_name.isdigit():
                self.self.port_name = "COM" + str(port_name)


class SerialMessageHandler:

    def __init__(self, serial_connection_manager, string_message_handler, serial_readings_interval = 0.2):
        self.serial_connection_manager = serial_connection_manager
        self.string_message_handler = string_message_handler

        self.serial_readings_interval = serial_readings_interval

        self.received_message_buffer = [] #Using array, because event queues don't allow checking without removing from it. Simpler and more robust.

        self.serial_readings_task = None

        self.lock = asyncio.Lock()

        if not isinstance(self.serial_readings_interval, (int, float)):
            raise TypeError(f"serial_readings_interval must be an int or float, got {type(self.serial_readings_interval).__name__}")
    
    def get_receieved_messages(self):
        return self.received_message_buffer

    def find_message(self, message, purge = False):
        if message not in self.string_message_handler.messages.keys():
            raise KeyError(f"Message type '{message}' does not exist. Valid messages are: {self.string_message_handler.valid_messages}")
        for i in self.received_message_buffer:
            if i.message_key == message:
                self.received_message_buffer.pop(self.received_message_buffer.index(i))
                if not purge:
                    return i
        return None
    
    def find_message_with_timeout(self, timer, message):
        status = {
            "timed_out": False,
            "message": None
        }

        found_message = self.find_message(message)

        if not isinstance is None:
            status["timed_out"] = False
            status["message"] = found_message
        if timer.timed_out():
            status["timed_out"] = True
        return status

    async def find_message_with_blocking_timeout(self, message, timeout, pull=False):
        """
        Finds a message with a blocking timeout.

        Parameters:
            message: The message to find.
            timeout: The maximum time to search for the message (in seconds).
            pull: If True, stores all messages from the buffer during each iteration.

        Returns:
            The found message, or None if not found within the timeout.
        """
        timer = TimeManager.Timer(timeout * 1000)
        while not timer.timed_out():
            if pull:
                try:
                    await self.serial_message_handler.store_all_messages_async()
                except (FileNotFoundError, PermissionError) as e:
                    raise e

            found_message = self.find_message(message)
            if found_message is not None:
                return found_message

        return None
    
    async def store_all_messages_async(self):
        try:
            while self.serial_connection_manager.serial_port.in_waiting():
                message = await self.get_message_async()
                if message.message_valid:
                    self.received_message_buffer.append(message)
        except:
            raise

    async def pass_message_async(self, message, value=None, timestamp=None):
        if not isinstance(message, str):
                raise TypeError("Message is not a string") #Level 1

        if message not in self.string_message_handler.messages.keys():
            raise KeyError(f"Message type '{message}' does not exist. Valid messages are: {self.string_message_handler.valid_messages}") #Level 1

        if not isinstance(timestamp, (datetime, type(None))):
            raise InvalidTimestampTypeError(f"Timestamp is of type {type(timestamp).__name__}; expected datetime or None") #Level 1

        full_message = self.string_message_handler.FullMessage(message, value, timestamp)
        encoded_message = self.string_message_handler.encode_message(full_message)
        built_message = self.string_message_handler.build_message(encoded_message)

        try:
            await self.send_message_async(built_message)
        except (FileNotFoundError, PermissionError) as e:
            print(f"Error sending message: {e}")
            raise

    async def get_message_async(self):
        try:
            message_str = await self.receive_message_async()
        except Exception as e:
            print(f"Error receiving message: {e}")
            raise
        parsed = self.string_message_handler.parse_message(message_str)
        decoded_message = self.string_message_handler.decode_message(parsed)
        return decoded_message

    async def send_message_async(self, message):
        loop = asyncio.get_running_loop()

        async with self.lock:
            try:
                await loop.run_in_executor(None, self.serial_connection_manager.serial_port.write, (message + '\n').encode('utf-8'))
            except (serial.SerialException, Exception) as e:
                print(f"Message not sent: {e}")
                if ErrorTools.check_nested_error(e, FileNotFoundError):
                    self.serial_connection_manager.update_for_serial_error(FileNotFoundError)
                    raise FileNotFoundError #Level 1
                elif ErrorTools.check_nested_error(e, PermissionError):
                    self.serial_connection_manager.update_for_serial_error(PermissionError)
                    raise PermissionError #Level 1

        print(f"Sent: {message.encode('utf-8')}")

    async def receive_message_async(self):
        loop = asyncio.get_running_loop()

        message_decoded = ""

        async with self.lock:
            try:
                message = await loop.run_in_executor(None, self.serial_connection_manager.serial_port.readline())
                message_decoded = message.decode('utf-8').strip()
            except (serial.SerialException, Exception) as e:
                print(f"Message not sent: {e}")
                if ErrorTools.check_nested_error(e, FileNotFoundError):
                    self.serial_connection_manager.update_for_serial_error(FileNotFoundError)
                    raise FileNotFoundError #Level 1
                elif ErrorTools.check_nested_error(e, PermissionError):
                    self.serial_connection_manager.update_for_serial_error(PermissionError)
                    raise PermissionError #Level 1

        print(f"Received: {message_decoded}")
        return message_decoded
    
    def start_serial_readings(self, interval=None):
        if interval is None:
            interval = self.serial_readings_interval
        self.serial_readings_task = asyncio.create_task(self.run_serial_readings(interval))

    def stop_serial_readings(self):
        # Cancel the serial reading loop task if it's running
        if self.serial_readings_task:
            self.serial_readings_task.cancel()

    async def run_serial_readings(self, interval):
        try:
            while True:
                self.store_all_messages_async()
                await asyncio.sleep(interval)
        except (FileNotFoundError, PermissionError) as e:
            print(f"Serial readings failed: {e}")
        except asyncio.CancelledError:
            print("Serial reading loop cancelled.")

class SerialHandshakeHandler:

    def __init__(self, serial_connection_manager, serial_message_handler, handshake_message="ping_pc_arduino", handshake_response = "ping_arduino_pc", ping_interval = 5, ping_timeout = 2, no_ping_response_timeout = 15, gui_queue=None):
        self.serial_message_handler = serial_message_handler
        self.string_message_handler = self.serial_message_handler.string_message_handler
        self.serial_connection_manager = serial_connection_manager

        self.handshake_message = handshake_message
        self.handshake_response = handshake_response
        self.ping_interval= ping_interval
        self.ping_timeout = ping_timeout
        self.no_ping_response_timeout = no_ping_response_timeout

        self.gui_queue = gui_queue # Optional: For GUI updates

        self.ping_task = None

        self.lock = asyncio.Lock()

        if not type(self.handshake_message) is str:
            raise TypeError(f"handshake_message must be a string, got {type(self.handshake_message).__name__}")
        elif not self.handshake_message in self.string_message_handler.messages.keys():
            raise KeyError(f"handshake_message message type '{self.handshake_message}' does not exist. Valid messages are: {self.string_message_handler.valid_messages}") #Level 1
        elif not type(self.handshake_response) is str:
            raise TypeError(f"handshake_response must be a string, got {type(self.handshake_response).__name__}")
        elif not self.handshake_response in self.string_message_handler.messages.keys():
            raise KeyError(f"handshake_response message type '{self.handshake_response}' does not exist. Valid messages are: {self.string_message_handler.valid_messages}") #Level 1

    async def ping_handshake(self):
        # Perform the handshake asynchronously
        try:
            await self.serial_message_handler.pass_message_async(self.handshake_message)
            print("Sent handshake ping.")
        except Exception as e:
            print(f"Error during ping handshake: {e}")
            raise

        timer = TimeManager.Timer(self.ping_timeout * 1000)
        
        try:
            response = await self.serial_message_handler.find_message_with_blocking_timeout(timer, self.ping_timeout, pull = True)
        except Exception as e:
            print(f"Error during ping handshake: {e}")
            raise
        if response is None:
            print("Received valid handshake response.")
            return True
        else:
            print("Did not receive valid handshake response.")
            return False

    async def run_ping_loop(self, interval, no_response_timeout):
        timer = TimeManager.Timer(no_response_timeout * 1000)

        # Ping loop to perform handshake every `interval` seconds
        try:
            while True:
                success = await self.ping_handshake()
                if success:
                    timer.reset_timer()
                elif timer.timed_out:
                    raise NoPingResponseTimeoutError
                await asyncio.sleep(interval)
        except NoPingResponseTimeoutError as e:
            self.serial_connection_manager.update_for_serial_error(e)
            print(f"Arduino didn't respond to ping for {no_response_timeout} seconds.")
        except (FileNotFoundError, PermissionError) as e:
            print(f"Ping failed: {e}")
        except asyncio.CancelledError: #Level 1
            print("Ping loop cancelled.")

    def start_ping_loop(self, interval=None, no_response_timeout = None):
        if interval is None:
            interval = self.ping_interval
        if no_response_timeout is None:
            no_response_timeout = self.no_ping_response_timeout
        self.ping_task = asyncio.create_task(self.run_ping_loop(interval, no_response_timeout))

    def stop_ping_loop(self):
        # Cancel the ping loop task if it's running
        if self.ping_task:
            self.ping_task.cancel()


class SerialManager():
    #See comment in interface class
    """
    Central manager for all serial communication functionalities.
    Encapsulates connection management, message handling, and handshake processes.
    """

    def __init__(self, gui_queue = None):
        self.gui_queue = gui_queue
        
        self.port_name = ""
        self.baud_rate = 0
        self.timeout = 0
        self.serial_readings_interval = 0
        self.handshake_message = ""
        self.handshake_response = ""
        self.ping_interval = 0

        self.string_message_handler = None
        self.serial_connection_manager = None
        self.serial_message_handler = None
        self.serial_handshake_handler = None

        self.messages = {}
        self.valid_messages = ""

        self.lock = asyncio.Lock()


    async def begin(self, port_name, baud_rate=9600, serial_reading_timeout=2, serial_readings_interval = 0.2, handshake_message="ping_pc_arduino", handshake_response = "ping_arduino_pc", ping_interval = 5, ping_timeout = 2, no_ping_response_timeout = 15):
        self.port_name = port_name
        self.baud_rate = baud_rate
        self.timeout = serial_reading_timeout
        self.serial_readings_interval = serial_readings_interval
        self.handshake_message = handshake_message
        self.handshake_response = handshake_response
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.no_ping_respone_timeout = self.no_ping_respone_timeout

        try:
            #Input from GUI or unimplemented Labview starts serial processes when values like the COM port is known.
            self.string_message_handler = StringMessageHandler(self.messages)
            self.serial_connection_manager = SerialConnectionManager(self.port_name, self.baud_rate, self.timeout, gui_queue=self.gui_queue)
            self.serial_message_handler = SerialMessageHandler(self.serial_connection_manager, self.string_message_handler)
            self.serial_handshake_handler = SerialHandshakeHandler(self.serial_connection_manager, self.serial_message_handler, self.handshake_message, self.handshake_response, self.ping_interval, self.ping_timeout, self.no_ping_respone_timeout, gui_queue=self.gui_queue)
        except (ValueError, TypeError, KeyError): #This is an entry point, but copy-pasting 50 lines of code is avoided.
            raise
        
        #If the serial part of this system was a library, these should really be set in serial manager as a class attribute
        self.messages = self.string_mesage_handler.messages
        self.valid_messages = self.string_message_handler.valid_messages

    async def setup_serial(self):
        try:
            await self.serial_connection_manager.setup_COM()
        except asyncio.CancelledError:
            await self.clean_connection()
            print("Setup cancelled.")
        except Exception as e:
            print("Setup failed.")
            raise

    async def attempt_reconnect(self):
        try:
            await self.setup_serial()
        except:
            print("Reconnection attempt failed.")
            raise

    async def pass_message_async(self, message, value=None, timestamp=None):
        if not isinstance(message, str):
                raise TypeError("Message is not a string")
        if message not in self.messages.keys():
            raise KeyError(f"Message type '{message}' does not exist. Valid messages are: {self.valid_messages}") #Level 1
        if not isinstance(timestamp, (datetime, type(None))):
            raise InvalidTimestampTypeError(f"Timestamp is of type {type(timestamp).__name__}; expected datetime or None") #Level 1

        try:
            await self.serial_message_handler.pass_message_async(message, value, timestamp)
        except (FileNotFoundError, PermissionError) as e:
            print(f"Error sending message: {e}")
            raise
        
    def find_message(self, message):
        if not isinstance(message, str):
            raise TypeError(f"message needs to be of type str, got {type(message).__name__}.")
        if message not in self.messages.keys():
            raise KeyError(f"Message type '{message}' does not exist. Valid messages are: {self.valid_messages}")
        return self.find_message(message)

    def find_message_with_timeout(self, timer, message):
        if not isinstance(timer, TimeManager.Timer):
            raise TypeError(f"timer needs to be of type TimeManager.Timer, got {type(timer).__name__}.")
        if not isinstance(message, str):
            raise TypeError(f"message needs to be of type str, got {type(message).__name__}.")
        return self.serial_message_handler.find_message_with_timeout(timer, message)

    def set_port_name(self, port_name):
        try:
            self.serial_connection_manager.set_port_name(port_name)
        except:
            raise

    def get_messages(self):
        return self.serial_message_handler.get_receieved_messages()

    def get_connection_info(self):
        return self.serial_connection_manager.get_connection_info()

    async def clean_connection(self):
        await self.serial_connection_manager.clean_connection()

    async def shutdown(self):
        """
        Gracefully shutdown the asyncio event loop and close serial connections.
        """
        self.serial_handshake_handler.stop_ping_loop()
        self.serial_message_handler.stop_serial_readings()
        # Schedule the clean_connection coroutine in the event loop
        asyncio.run_coroutine_threadsafe(
            await self.serial_connection_manager.clean_connection(),
            self.loop
        )

class FuturesBridge:
    """
    Used when running coroutines from a different event loop.
    Data about each method call (method name, arguments, return data, exception) are stored and can externally be handled when ready, if any.
    Has mechanisms to only allow running a coroutine from one place at a time, if wanted. Simple reject if yes.
    """

    def __init__(self, event_loop):
        self.loop = event_loop
        self.futures_metadata = {} #{Future{"method_name", "params", "done", "return_data", "exception"}}In here will be one or more dictionaries with method call data.
        self.lock = threading.Lock()

    def schedule_coroutine(self, coro, method_name, allow_parallel = False, **params):
        """
        Schedules the passed coroutine coro, and stores it's given and eventual metadata in self.futures_data
        :param corro: The method (can have arguments) to be run in different event loop
        :param method_name: The name of the run method, it's not robust to get the method name dynamically
        :param allow_parallel: Let two methods of the same name run at the same time?
        :param params: Any arguments sent to the called method that should be in the metadata?
        :raises RuntimeError: If the method is allready running with allow_parallel = True
        """

        with self.lock:
            if not allow_parallel:
                #Refuse to run if the method with given passed name is allready running
                for fut, metadata in self.futures_metadata.items():
                    if metadata["method_name"] == method_name and not fut.done():
                        raise RuntimeError(f"Method '{method_name}' is already running") #Rejection!

        fut = asyncio.run_coroutine_threadsafe(coro, self.loop) #Run the coroutine in the given event loop
        info = {
            "method_name": method_name,
            "params": params,
            "done": False,
            "return_data": None,
            "exception": None
        }

        with self.lock:
            self.futures_metadata[fut] = info

    def poll_futures(self):
        """
        Gives the metatdata for any futures for completed methods in a list of dictionaries, one future per index
        The future is tested for any exceptions raaised while running the coroutine, and that is stored in the metadata
        
        return: List with dictionaries, one per completed future, with their metadata method_name, params, return_data, and exception 
        """
        completed = []
        with self.lock:
            remove = [] #Remove these futures if they are going to be put in the return list
            #Get metadata for all active futures
            for fut, metadata in self.futures_metadata.items():
                if fut.done() and not metadata["done"]:
                    metadata["done"] = True #Avoid redundant iterations

                    #Test for exceptions
                    try:
                        return_data = fut.result()
                    except Exception as e:
                        metadata["exception"] = e

                    completed.append({
                        "method_name": metadata["method_name"],
                        "params": metadata["params"],
                        "return_data": metadata["return_data"],
                        "exception": metadata["exception"]
                    })
                    remove.append(fut)

            for fut in remove:
                self.futures_metadata.pop(fut, None) #Gone, no longer needed, bye!

        return completed


class Interface:

    def __init__(self, serial_manager):
        # Direct method calls are used instead of a GUI queue like in the SerialManager.
        # Using a queue system or a thread-safe data structure would likely be more optimal for both.
        # A queue system requires centralized handling since queues operate on a FIFO basis.
        # Currently, a queue is used for the GUI because it simplifies communication to a single destination.
        # Moving queue initialization to the process manager level could centralize storage and resolve circular dependencies 
        # (e.g., the GUI needing to be instantiated before the SerialManager).
        # A unified queue could handle all updates (GUI, status, etc.), sorted into a dictionary by a high-level process.

        self.serial_manager = serial_manager

        self.main_task = None
        self.setup_serial_task = None

        self.emergency_stop_active = False

        #Arduino alarm statuses
        self.thermosensor_error = False
        self.watchdog_pwm_frozen = False
        self.furnace_overheat = False

        self.furnace_temperature = None

        if not isinstance(self.serial_manager, SerialManager):
            raise TypeError(f"serial_manager needs to be a SerialManager object, got {type(self.serial_manager).__name__}")


    def begin(self):
        pass #In case parameters need to be set after instanciation, or something else
    
    def get_furnace_temperature_status(self):
        return self.furnace_temperature

    def get_thermosensor_error_status(self):
        return self.thermosensor_error

    def get_watchdog_pwm_frozen_status(self):
        return self.watchdog_pwm_frozen
    
    def get_furnace_overheat_status(self):
        return self.furnace_overheat

    def send_emergency_stop(self):
        self.emergency_stop_active = True


    def start_main(self):
        self.main_task = asyncio.create_task(self.run_main())

    def stop_main(self):
        # Cancel the serial reading loop task if it's running
        if self.main_task:
            self.main_task.cancel()

    def start_setup_serial(self, port_name):
        self.serial_manager.begin(port_name) #Needs an input field for COM number when button is clicked. Also, serial_manager.begin() needs value verifications.
        self.setup_serial_task = asyncio.create_task(self.serial_manager.setup_serial())
        
    def stop_setup_serial(self):
        # Cancel the serial reading loop task if it's running
        if self.setup_serial_task:
            self.setup_serial_task.cancel()

    async def run_main(self):
        try:
            while True:
                connection_info = self.serial_manager.get_connection_info()
                serial_loss = connection_info["serial_loss"]
                if serial_loss:
                    self.serial_connection_timer = None
                    #Will run while the rest of the code runs
                    if not self.setup_serial_task:
                        self.start_setup_serial()
                
                furnace_temperature_result = self.serial_manager.find_message("temperature_reading")
                self.furnace_temperature = furnace_temperature_result.value if furnace_temperature_result is not None else None

                #The errors are only cleared Arduino-side if the Arduino is restarted. This program will need a restart too, it lackas an error clearance if no error after some time of serial communication.
                thermosensor_error_result = self.serial_manager.find_message("thermosensor_error")
                self.thermosensor_error = True if thermosensor_error_result is not None else None

                watchdog_pwm_frozen_result = self.serial_manager.find_message("watchdog_pwm_frozen")
                self.watchdog_pwm_frozen = True if watchdog_pwm_frozen_result is not None else None

                furnace_overheat_result = self.serial_manager.find_message("furnace_overheat")
                self.furnace_overheat = True if furnace_overheat_result is not None else None
                
                if self.emergency_stop_active:
                    self.serial_manager.pass_message_async("force_emergency_stop") #Hard-coding!
                
        except asyncio.CancelledError:
            print("Serial reading loop cancelled. Running cleanup.")
            self.stop_setup_serial()


class ProcessManager:
    #See comment in interface class
    """
    Encapsulates overall procedures for managing processes
    """

    def __init__(self, use_gui):
        self.use_gui = use_gui

        #GUI will run in the main thread and trigger methods via futures_bridge, the rest will run in a background thread
        #Truly simultaneously running tasks is done with threads, as opposed to event loops...
        # ...They are shortcuts to allowing other processes to run in between each other, automatically switching between async methods (or coroutines) whenever possible (like in between actions or during async sleep())
        #If the GUI and the rest is run in the same thread, the GUI might lag.
        #Locks (async.Lock()) forces a process to wait for accessing places in memory until no other processes do it.
        #Using "with async.lock() means the place in memory will only be locked for as long as it's used at the moment.
        #Threads are required to use event loops, and in turn, coroutines. Tkinter GUIs have to be run in the main thread (what's usually run without multithreading), but does not require an event loop.
        #run_coroutine_threadsafe(coro, event) runs a coroutine (coro) in the given event loop (event). Whatever called run_coroutine_threadsafe continues meanwhile without waiting.
        #When a normal method calls a coroutine (ike via run_coroutine_threadsafe), any errors or return values will only be available after the coroutine finished. Meanwhile, the method allready has finished.
        #That's why the futures_bridge is there. It stores these as so-called futures, that are then accessed afterward when available.

        self.futures_bridge = None

        self.gui = None

        self.serial_manager = None
        self.interface = None

        # The single event loop for all async tasks. GUI has no event loop.
        self.loop = asyncio.new_event_loop()

        # Thread that will run the above loop
        self.asyncio_thread = None

    # Boots up the system
    def startup(self):
        #Instanciate GUI
        if self.use_gui:
            self.gui = GUI()
        else:
            print("Starting system without GUI")
        
        #Used by any top-level class like GUI or Labview functions to interact with coroutines
        self.futures_bridge = FuturesBridge(self.loop)

        #Instanciate async components
        self.serial_manager = SerialManager(gui_queue = self.gui.gui_queue)
        self.interface = Interface(self.serial_manager)

        #Working with circular dependencies. Serial manager needed the GUI for gui_queue first
        if self.gui:
            self.gui.begin(self.futures_bridge, self.serial_manager, self.interface)

        #Start the asyncio event loop in a separate thread. It targets run_asyncio_loop to run it in the thread.
        self.asyncio_thread = threading.Thread(target = self.run_asyncio_loop)
        self.asyncio_thread.start()

        if self.gui:
            self.gui.run()

    def run_asyncio_loop(self):
        #A mew thread targets this method, so it's running there. Start the event loop self.loop in that thread.
        asyncio.set_event_loop(self.loop)
            
        #Keep the event loop running and ready for use
        self.loop.run_forever()

    #Fix and use graceful shutdown and add more shutdown detections. Shutdown is currently not implemented for all classes, but is on good way.
    def full_shutdown(self):
        self.serial_manager.shutdown()
        # Stop event loop
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        # Join the background thread
        if self.asyncio_thread:
            self.asyncio_thread.join()
        print("Shutdown complete.")


class GUI:
    #See comment in the interface class.

    gui_update_interval = 100

    def __init__(self):
        self.futures_bridge = None

        self.serial_manager = None #Working around circular dependencies. Will be set to SerialManager by shared reference after GUI's instanciation.
        self.serial_handshake_handler = None

        self.interface = None #Interface depends on Serial Manager, and can't be set before

        self.lock = threading.Lock()

        self.root = tk.Tk()
        self.root.title("Serial Communication GUI")
        self.root.geometry("400x300")
        self.gui_queue = queue.Queue()

        self.begin_button = ttk.Button(self.root, text="Begin", command=self.start_serial)
        self.begin_button.pack(pady=10)

        self.label = ttk.Label(self.root, text="Serial Communication Active")
        self.label.pack(pady=20)

        self.ping_button = ttk.Button(self.root, text="Send Ping", command=self.send_ping)
        self.ping_button.pack(pady=10)

        self.status_label = ttk.Label(self.root, text="Status: Waiting for setup...")
        self.status_label.pack(pady=10)

        self.retry_button = ttk.Button(self.root, text="Retry Connection", command=self.retry_connection)
        self.retry_button.pack(pady=10)

        # Start the update loop for real-time updates
        self.root.after(self.gui_update_interval, self.check_queue)

    def begin(self, futures_bridge, serial_manager, interface):
        self.futures_bridge = futures_bridge
        
        self.serial_manager = serial_manager
        self.serial_handshake_handler = self.serial_manager.serial_handshake_handler

        self.interface = interface

    def start_setup_serial(self):
        self.gui_thread_interface.start_setup_serial()

    def send_ping(self):
        # Schedule the coroutine in the event loop
        if self.serial_manager.loop.is_running():
            self.serial_handshake_handler.ping_handshake()
            self.update_status_label("Status: Ping sent!")
        else:
            self.update_status_label("Status: Event loop not running.")

    def retry_connection(self):
        # Schedule the setup_serial coroutine in the event loop
        if self.serial_manager.loop.is_running():
            self.serial_manager.setup_serial()
            self.update_status_label("Status: Retrying connection...")
        else:
            self.update_status_label("Status: Event loop not running.")

    def update_status_label(self, message):
        # Thread-safe update of the status label
        self.status_label.config(text=message)

    def check_queue(self):
        #I'm going to poll for the futures.done and futures.result from Serial Manager and Interface here since I'm short on time
        #More optimally: Use callbacks
        #I currently have only COM status in the GUI's queue. Other errors are shown directly. A bit here, a bit there.

        try:
            while True:
                message = self.gui_queue.get_nowait()
                self.update_status_label(f"Status: {message}")
        except queue.Empty:
            pass
        # Schedule the next check
        self.root.after(100, self.check_queue)

    def run(self):
        self.root.mainloop()


use_gui = False

if __name__ == "__main__":
    # Use GUI
    use_gui = True

process_manager = ProcessManager(use_gui)
process_manager.startup()

# if __name__ == "__main__":
# main()

# import tkinter as tk
# from queue import Queue
# import threading
# import time
# import json

# # Worker function to simulate background processing
# def worker(queue):
# for i in range(5):
# # Example data to send (dictionary)
# data = {"id": i, "status": "processing", "value": i * 30}
# queue.put(data) # Send dictionary to the queue
# time.sleep(1) # Simulate processing time
# # Sending a final message
# queue.put({"id": None, "status": "done"})

# # Function to update the GUI
# def update_gui():
# try:
# while not queue.empty():
# data = queue.get_nowait()
# id_text = f"Received: {data['id']}"
# id.config(text=id_text)
# status_text = f"Received: {data['status']}"
# status.config(text=status_text)
# value_text = f"Received: {data['value']}"
# value.config(text=value_text)
# except Exception as e:
# print(f"Error: {e}")
# finally:
# root.after(100, update_gui) # Schedule next check

# # Setup tkinter GUI
# root = tk.Tk()
# root.title("GUI Queue Example")

# id = tk.Label(root, text="Waiting for data...", font=("Arial", 14))
# id.pack(pady=20)
# status = tk.Label(root, text="Waiting for data...", font=("Arial", 14))
# status.pack(pady=20)
# value = tk.Label(root, text="Waiting for data...", font=("Arial", 14))
# value.pack(pady=20)

# queue = Queue() # Thread-safe queue

# # Start worker thread
# thread = threading.Thread(target=worker, args=(queue,))
# thread.daemon = True # Exit thread when main program exits
# thread.start()

# # Start GUI queue polling
# root.after(100, update_gui)

# # Start the tkinter main loop
# root.mainloop()