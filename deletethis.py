#FOLLOW THIS CYNICALLY, WITHOUT DEVIATIONS. IF YOU SEE OTHER PROBLEMS IN THE CODE, WRITE DOWN THE PROBLEMATIC METHOD IN A NOTEPAD, AND MOVE ON! REMOVE ALL TRY/EXCEPTS AND RAISE THAT CAN'T DO ANYTHING ABOUT THE PROBLEM, DON'T RERAISE DUE TO FAILED RECOVERY, OR ARE'NT VERY ESSENTIAL FOR LOGGING, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS. REMOVE ALL LEVEL COMMENTS EXCEPT FROM LEVEL 1. MAP ALL LEVEL 1, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS. REPLACE EVERY EXCEPTION TYPE WHERE SENSIBLE, IF IT'S RERAISE OR NOT, WITH CUSTOM EXCEPTIONS, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS. TRACK EVERY EXCEPTION TYPE, IF IT'S RERAISE OR NOT, TO WRITE WHERE THEY END UP IN OTHER TRY/EXCEPTS, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS. CHECK WHERE I GET DUPLICATE EXCEPTION TYPES AND REPLACE WITH CUSTOM EXCEPTIONS, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS.

import re
import time
from datetime import datetime
from collections import namedtuple
import asyncio
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
    
    def check_nested_error(e, exception):
        #Check if the string for the requested nested error is in the exception
        exception_string = exception.__name__
        return True if exception_string in str(e) else False

class TimeManager:
    time_string_format = "%m/%d/%Y %H:%M:%S"

    class Timer:
        def __init__(self, duration_ms):
            self.duration_ms = duration_ms
            self.last_blocking_timer_call = time.monotonic()

            self.start_time = 0

            if not isinstance(self.duration_ms, (int)):
                raise TypeError(f"duration is of type {type(self.duration)}, expected int") #Level 1
            
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

    messages = {
    "ping_sending": MessageStruct("1", "1"),
    "ping_receiving": MessageStruct("1", "2"),
    "temperature_reading": MessageStruct("2", "1"),
    "force_emergency_stop": MessageStruct("4", "0"),
    "emergency_alarm": MessageStruct("9, 0"),
    "thermocouple_error": MessageStruct("9", "1"),
    "watchog_sr_frozen": MessageStruct("9", "2"),
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

        self.recent_port_name = self.port_name #Compared with self.port_name to check port name change
        self.connect_in_progress = False

        self.lock = asyncio.Lock()
        self.gui_queue = gui_queue # Optional: For GUI updates

        if not isinstance(self.port_name, (str, int)):
            raise TypeError(f"port_name must be a string or int, got {type(self.port_name)}")

        if isinstance(self.port_name, int):
            if self.port_name < 0:
                raise ValueError(f"port_name cannot be negative, got {self.port_name}")
            self.port_name = "COM" + str(self.port_name)
        elif isinstance(self.port_name, str):
            if not re.fullmatch(r"(COM\d+|\d+)", self.port_name):
                raise ValueError("port_name must be 'COM' followed by a number (e.g., COM18), or just a number (e.g., 18)")
            if self.port_name.isdigit():
                self.port_name = "COM" + str(self.port_name)

        #Level 1
        if not isinstance(baud_rate, int):
            print(f"Baudrate {self.baud_rate} not an integer")
            raise TypeError(f"Baudrate {self.baud_rate} not an integer")
        #Level 1
        if not isinstance(timeout, (int, float)):
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
        except Exception as e:
            self.serial_loss = True
            raise

        self.serial_message_handler.find_message("ping_sending", purge=True)

        connection_success = False
        while not connection_success:
            if not self.port_name == self.recent_port_name:
                try:
                    await self.initialize_port()
                    self.recent_port_name == self.port_name
                except:
                    self.serial_loss = True
                    raise
            # Attempt to connect to the specified port
            try:
                connection_success = await self.attempt_connection()
            except:
                self.serial_loss = True
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

    #This
    async def clean_connection(self):
        await self.close_connection()
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
                self.gui_queue.put({"serial_error": "connect device, or set correct COM port as seen in device manager"})
            elif ErrorTools.check_nested_error(e, "FileNotFound"):
                self.gui_queue.put({"serial_error": "verify that nothing else is using the COM port, or set correct COM port as seen in device manager"})
            elif isinstance(e, NoPingResponseTimeoutError):
                self.gui_queue.put({"serial_error": "Check that the device is connected to the set COM port as seen in device manager, and verify it's working."})
            self.gui_queue.put({"serial_status": "serial connection lost"})

    #This
    def get_connection_info(self):
        return {
            'serial_loss': self.serial_loss,
            'port_name': self.port_name,
            'baud_rate': self.baud_rate,
            'timeout': self.timeout,
            'COM_description': self.serial_port.description,
            'port_open': True if self.serial_port.is_open else False
        }


class SerialMessageHandler:

    def __init__(self, serial_connection_manager, string_message_handler, serial_readings_interval = 0.2):
        self.serial_connection_manager = serial_connection_manager
        self.string_message_handler = string_message_handler

        self.serial_readings_interval = serial_readings_interval

        self.received_message_buffer = [] #Using array, because event queues don't allow checking without removing from it. Simpler and more robust.

        self.serial_readings_task = None

        self.lock = asyncio.Lock()

        if not isinstance(self.serial_readings_interval, (int, float)):
            raise TypeError(f"serial_readings_interval must be an int or float, got {type(self.serial_readings_interval)}")
    
    #This
    def get_messages(self):
        return self.received_message_buffer

    def find_message(self, message, purge = False):
        if message not in self.string_message_handler.messages.keys():
            raise KeyError(f"Message type '{message}' does not exist. Valid messages are: {self.string_message_handler.valid_messages}") #Level 1
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
                except Exception as e:
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

    #This
    async def pass_message_async(self, message, value=None, timestamp=None):
        if message not in self.string_message_handler.messages.keys():
            raise KeyError(f"Message type '{message}' does not exist. Valid messages are: {self.string_message_handler.valid_messages}") #Level 1

        if not isinstance(timestamp, (datetime, type(None))):
            raise TypeError(f"Timestamp is of type {type(timestamp).__name__}; expected datetime or None") #Level 1

        full_message = self.string_message_handler.FullMessage(message, value, timestamp)
        try:
            encoded_message = self.string_message_handler.encode_message(full_message)
        except InvalidTimestampTypeError:
            raise InvalidTimestampTypeError(f"Timestamp is of type {type(timestamp).__name__}; expected datetime or None")
        built_message = self.string_message_handler.build_message(encoded_message)

        try:
            await self.send_message_async(built_message)
        except Exception as e:
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
        if not isinstance(message, str):
            raise TypeError("Message is not a string") #Level 1

        loop = asyncio.get_running_loop()

        async with self.lock:
            try:
                await loop.run_in_executor(None, self.serial_connection_manager.serial_port.write, (message + '\n').encode('utf-8'))
            except (serial.SerialException, Exception) as e:
                print(f"Message not sent: {e}")
                if ErrorTools.check_nested_error(e, FileNotFoundError):
                    raise FileNotFoundError #Level 1
                elif ErrorTools.check_nested_error(e, PermissionError):
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
                    raise FileNotFoundError #Level 1
                elif ErrorTools.check_nested_error(e, PermissionError):
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
            self.serial_connection_manager.update_for_serial_error(e)
        except asyncio.CancelledError:
            print("Serial reading loop cancelled.")

class SerialHandshakeHandler:

    def __init__(self, serial_connection_manager, serial_message_handler, handshake_message="ping_sending", handshake_response = "ping_receiving", ping_interval = 5, ping_timeout = 2, no_ping_response_timeout = 15, gui_queue=None):
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
            raise TypeError(f"handshake_message must be a string, got {type(self.handshake_message)}")
        elif not self.handshake_message in self.string_message_handler.messages.keys():
            raise KeyError(f"handshake_message message type '{self.handshake_message}' does not exist. Valid messages are: {self.string_message_handler.valid_messages}") #Level 1
        elif not type(self.handshake_response) is str:
            raise TypeError(f"handshake_response must be a string, got {type(self.handshake_response)}")
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
    """
    Central manager for all serial communication functionalities.
    Encapsulates connection management, message handling, and handshake processes.
    """

    def __init__(self, gui_queue = None):
        self.port_name = None
        self.baud_rate = None
        self.timeout = None
        self.serial_readings_interval = None
        self.handshake_message = None
        self.handshake_response = None
        self.ping_interval = None

        self.gui_queue = gui_queue

        self.string_message_handler = None
        self.serial_connection_manager = None
        self.serial_message_handler = None
        self.serial_handshake_handler = None

        self.serial_connection_manager.serial_handshake_handler = self.serial_handshake_handler #Working around circular dependencies. This is sketchy, sorry, it works though
        self.serial_connection_manager.serial_message_handler = self.serial_message_handler

        self.loop = asyncio.new_event_loop() # Create a new event loop

        self.lock = asyncio.Lock()


    async def begin(self, port_name, baud_rate=9600, serial_reading_timeout=2, serial_readings_interval = 0.2, handshake_message="ping_sending", handshake_response = "ping_receiving", ping_interval = 5, ping_timeout = 2, no_ping_response_timeout = 15):
        self.port_name = port_name
        self.baud_rate = baud_rate
        self.timeout = serial_reading_timeout
        self.serial_readings_interval = serial_readings_interval
        self.handshake_message = handshake_message
        self.handshake_response = handshake_response
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.no_ping_respone_timeout = self.no_ping_respone_timeout

        self.string_message_handler = StringMessageHandler()
        self.serial_connection_manager = SerialConnectionManager(self.port_name, self.baud_rate, self.timeout, gui_queue=self.gui_queue)
        self.serial_message_handler = SerialMessageHandler(self.serial_connection_manager, self.string_message_handler)
        self.serial_handshake_handler = SerialHandshakeHandler(self.serial_connection_manager, self.serial_message_handler, self.handshake_message, self.handshake_response, self.ping_interval, self.ping_timeout, self.no_ping_respone_timeout, gui_queue=self.gui_queue)

    async def setup_serial(self):
        try:
            await self.serial_connection_manager.setup_COM()
        except Exception as e:
            print("Setup failed. Failed to complete handshake.")
            if not self.gui_queue is None:
                self.gui_queue.put("Setup failed. Failed to complete handshake.")
            return
        self.serial_message_handler.start_serial_readings()
        if not self.gui_queue is None:
            self.gui_queue.put("Setup complete.")

    async def attempt_reconnect(self):
        try:
            await self.setup_serial()
        except:
            pass

    def get_connection_info(self):
        return self.serial_connection_manager.get_connection_info()

    def shutdown(self):
        """
        Gracefully shutdown the asyncio event loop and close serial connections.
        """
        self.serial_handshake_handler.stop_ping_loop()
        self.serial_message_handler.stop_serial_readings()
        # Schedule the clean_connection coroutine in the event loop
        asyncio.run_coroutine_threadsafe(
            self.serial_connection_manager.clean_connection(),
            self.loop
        )
        self.loop.call_soon_threadsafe(self.loop.stop())


class GUI:

    gui_update_interval = 100

    def __init__(self):
        self.serial_manager = None #Working around circular dependencies. Will be set to SerialManager by shared reference after GUI's instanciation.
        self.serial_handshake_handler = None

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

        self.serial_manager.gui_queue = self.gui_queue

        # Start the update loop for real-time updates
        self.root.after(self.gui_update_interval, self.check_queue)

    def begin(self, serial_manager):
        self.serial_manager = serial_manager
        self.serial_handshake_handler = self.serial_manager.serial_handshake_handler

    def start_serial(self):
        if not self.serial_manager.loop.is_running():
            self.serial_manager.begin(port_name) #Needs an input field for COM number when button is clicked. Also, serial_manager.begin() needs value verifications.

    def send_ping(self):
        # Schedule the coroutine in the event loop
        if self.serial_manager.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.serial_handshake_handler.ping_handshake(),
                self.serial_manager.loop
            )
            self.update_status_label("Status: Ping sent!")
        else:
            self.update_status_label("Status: Event loop not running.")

    def retry_connection(self):
        # Schedule the setup_serial coroutine in the event loop
        if self.serial_manager.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.serial_manager.setup_serial(),
                self.serial_manager.loop
            )
            self.update_status_label("Status: Retrying connection...")
        else:
            self.update_status_label("Status: Event loop not running.")

    def update_status_label(self, message):
        # Thread-safe update of the status label
        self.status_label.config(text=message)

    def check_queue(self):
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


class Interface:

    def __init__(self, serial_manager, gui_queue = None):
        self.serial_manager = serial_manager
        self.gui_queue = gui_queue

        self.main_task = None
    
    def 

    def begin(self):
        pass #In case parameters need to be set after instanciation.

    def start_main(self):
        self.main_task = asyncio.create_task(self.run_main())

    def stop_main(self):
        # Cancel the serial reading loop task if it's running
        if self.main_task:
            self.main_task.cancel()

    async def run_main(self):
        try:
            while True:
                connection_info = self.serial_manager.get_connection_info()
                serial_loss = connection_info["serial_loss"]
                if serial_loss:
                    await self.serial_manager.setup_serial()
        except asyncio.CancelledError:
            print("Serial reading loop cancelled.")

class ProcessManager:
    """
    Encapsulates overall procedures for managing processes
    """

    def __init__(self, use_gui):
        self.use_gui = use_gui

        self.gui = None
        self.serial_manager = None

        self.asyncio_thread = None

    # Boots up the system
    def startup(self):
        # Start asyncio event loop in a separate thread
        self.asyncio_thread = threading.Thread(target=self.run_asyncio_loop, daemon=True)
        self.asyncio_thread.start()

        try:
            if self.use_gui:
                self.gui = GUI()
                self.serial_manager = SerialManager(self.gui.gui_queue)
                print("Starting system with GUI")
                self.gui.begin(self.serial_manager)
                # Run the GUI in the main thread
                self.gui.run()
            else:
                print("Startung system without GUI")
                self.serial_manager = SerialManager()
        except KeyboardInterrupt: #Fix graceful shutdown and add more shutdown detections
            print("Program interrupted by user.")
            self.full_shutdown()

    def run_asyncio_loop(self):
        asyncio.set_event_loop(self.serial_manager.loop)
        self.serial_manager.loop.run_until_complete(self.serial_manager.setup_serial())
        self.serial_manager.loop.run_forever()

    def full_shutdown(self):
        self.serial_manager.shutdown()
        self.asyncio_thread.join()
        print("Shutdown complete.")


# Initialize SerialManager instance

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