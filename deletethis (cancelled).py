#FOLLOW THIS CYNICALLY, WITHOUT DEVIATIONS. IF YOU SEE OTHER PROBLEMS IN THE CODE, WRITE DOWN THE PROBLEMATIC METHOD IN A NOTEPAD, AND MOVE ON! REMOVE ALL TRY/EXCEPTS AND RAISE THAT CAN'T DO ANYTHING ABOUT THE PROBLEM, DON'T RERAISE DUE TO FAILED RECOVERY, OR ARE'NT VERY ESSENTIAL FOR LOGGING, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS. REMOVE ALL LEVEL COMMENTS EXCEPT FROM LEVEL 1. MAP ALL LEVEL 1, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS. REPLACE EVERY EXCEPTION TYPE WHERE SENSIBLE, IF IT'S RERAISE OR NOT, WITH CUSTOM EXCEPTIONS, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS. TRACK EVERY EXCEPTION TYPE, IF IT'S RERAISE OR NOT, TO WRITE WHERE THEY END UP IN OTHER TRY/EXCEPTS, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS. CHECK WHERE I GET DUPLICATE EXCEPTION TYPES AND REPLACE WITH CUSTOM EXCEPTIONS, FROM TOP TO BOTTOM, WITHOUT FOLLOWING THE METHOD CALLS.

import math
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

class NoDeviceError(Exception):
    """Raised when no Arduino device is found."""
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
            required_seconds = self.duration_ms / 1000.0  # convert ms -> s

            # If the iteration so far is less than required_seconds, sleep the difference
            if so_far < required_seconds:
                asyncio.sleep(required_seconds - so_far)

            # Compute and return the final total
            iteration_end = time.monotonic()
            return iteration_end - iteration_start

class StringMessageHandler:

    MessageStruct = namedtuple('MessageStruct', ['category', 'message'])

    messages = {
        "ping_sending": MessageStruct("1", "1"),
        "ping_receiving": MessageStruct("1", "2")
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
                    converted_datetime = TimeManager.string_to_datetime(timestamp) #Level 2
                except ValueError:
                    print(f"Format is incorrect, expected {self.time_manager.time_string_format}. Big letters can include a zero as first digit, like 05, small letters cannot. Setting to None, the message to invalid, and moving on.")
                    converted_datetime = None
                    message_valid = False
                timestamp = converted_datetime

        return self.FullMessage(message_key, value, timestamp, message_valid)

class SerialConnectionManager:

    com_description = None
    serial_port = None
    testing_port = None

    port_open = False
    port_accessible = False
    handshake_completed = False
    
    no_port_timeout = 5

    port_initialization_time = 1.6
    connection_attempts = 3
    recovery_timeout = 0.5
    connect_in_progress = False
    heartbeat_task = None
    heartbeat_interval = 0.1  # Default heartbeat interval in seconds

    transmission_attempts = 3
    transmission_attempt_interval = 0.5

    def __init__(self, port_name=None, baud_rate=9600, timeout=2, gui_queue=None):
        self.serial_handshake_handler = None #Needs instanciation of SerialHandshakeHandler at a higher level before being set
        self.serial_message_handler = None #Same

        self.port_name = port_name      # Store the COM port name (like COM18)
        self.baud_rate = baud_rate      # Store the baud rate
        self.timeout = timeout          # Store the timeout

        self.set_port = port_name

        self.port_specified = True if self.port_name is not None else False

        self.lock = asyncio.Lock()
        self.gui_queue = gui_queue  # Optional: For GUI updates

        #Level 1
        if not isinstance(baud_rate, int):
            print(f"Baudrate {self.baud_rate} not an integer")
            raise TypeError(f"Baudrate {self.baud_rate} not an integer")
        #Level 1
        if not isinstance(timeout, (int, float)):
            print(f"Timeout {self.timeout} not an integer or float")
            raise TypeError(f"Timeout {self.timeout} not an integer or float")
        
    def deactivate_current_port(self):
        #Deactivates the port currently trying to be used by python, working or not
        self.testing_port = None if self.serial_port is None else self.serial_port = None

    def get_current_port(self):
        #Gives the port currently trying to be used by Python, working or not
        return self.testing_port if self.serial_port is None else self.serial_port

    #Level 1
    async def check_port_existence(self):
        port = self.get_current_port()

        loop = asyncio.get_running_loop()
        all_ports = await loop.run_in_executor(None, serial.tools.list_ports.comports)
        if any(arduino_port.name == port.name for arduino_port in all_ports):
            return True
        else:
            return False

    #Level 2
    async def check_port_availability(self):
        async with self.lock:
            try:
                original_state = self.port_open
                await self.close_connection()
                await self.open_connection() #Level 2
                if original_state == False:
                    await self.close_connection()
                return True
            except serial.SerialException as e:
                if ErrorTools.check_nested_error(e, PermissionError):
                    print("PermissionError opening ports, returning False")
                    return False #Level 3
                
        #Level 2
    async def handle_port_existence(self):
        # Check the port existence
        port_exists = await self.check_port_existence()
        if not port_exists:
            # Port is disconnected
            self.deactivate_current_port()
            self.port_name = None
            self.com_description = None
            self.port_open = False
            self.port_accessible = False
            if self.gui_queue:
                self.gui_queue.put("Port disconnected.")
        return port_exists #Level 2

    async def handle_port_availability(self):
        # Check the port availability
        port_available = await self.check_port_availability()
        if not port_available:
            # Port is occupied
            self.port_open = False
            self.port_accessible = False
            if self.gui_queue:
                self.gui_queue.put("Port is allready occupied.")
        return port_available #Level 3

    async def recover_COM(self, attempt_setup = True):
        #Check the known port for unsolvable user-caused errors before attempting a reconnect
        port_exists = self.handle_port_existence() #Level 3
        if not port_exists:
            print(f"Port {self.port.name} is disconnected.")
            raise FileNotFoundError #Level 4
        port_available = self.handle_port_availability()
        if not port_available:
            print(f"Port {self.port.name} does not exist.")
            raise PermissionError #Level 4

        #Try reconnection
        if attempt_setup:
            try:
                self.setup_COM()
            except:
                raise
        else:
            raise #Level 2
        
        print("COM recovery successful")

    async def setup_COM(self):
        # Setup serial connection
        if self.connect_in_progress:
            return  # Avoid multiple reconnection attempts at once.
        self.connect_in_progress = True
        # Avoid ping confusion, can't ping while setting up the port
        self.serial_handshake_handler.stop_ping_loop()
        #Same
        self.stop_heartbeat()
        self.serial_message_handler.stop_serial_reading()

        unhandled_errors = [] #The list is a simple and dirty way to allow direct modification from another method, that is passed as a parameter. Only first index is interesting.
        arduino_ports = []  # Initialize arduino_ports

        #Fresh start
        self.clean_connection()

        recovery_timeout = TimeManager.Timer(self.recovery_timeout)
        for i in range(self.connection_attempts):
            if i == 0:
                asyncio.sleep(self.recovery_timeout)

            iteration_start = time.monotonic()

            unhandled_errors.clear() #We only want to get errors from the last attempt. Means persistent error.
            
            ports_timeout_timer = TimeManager.Timer(self.no_port_timeout)
            ports_timed_out = False
            while not ports_timed_out and not arduino_ports == []:
                ports_timed_out = ports_timeout_timer.timed_out()køjljio
                async with self.lock:
                    all_ports = serial.tools.list_ports.comports()
                    arduino_ports = [port for port in all_ports if "Arduino" in port.description]
            
            if self.port_specified:
                # Attempt to connect to the specified port
                success = await self.attempt_connection(unhandled_errors)
                if success:
                    self.serial_port = self.testing_port
                    break
            else:
                for port in arduino_ports:
                    self.port_name = port.name  # Set to currently tested port
                    success = await self.attempt_connection(unhandled_errors)
                    if success:
                        self.serial_port = self.testing_port
                        break
                    #No success? Wrong! Do it again! (No dark sarcasm in the classroom)
            self.testing_port = None

            if self.handshake_completed:
                self.port_open = True
                self.port_accessible = True
                break

            await recovery_timeout.wait_until_duration(iteration_start)
        
        if self.serial_port is None:
            # Handle the situation where we couldn't connect
            await self.clean_connection()  # Await the async method
            self.connect_in_progress = False
            if not arduino_ports:
                raise NoDeviceError("No Arduino connected") #Level 1
            raise unhandled_errors[0]

        else:
            #Success, start or resume periodic serial processes
            self.serial_port = self.testing_port
            self.connect_in_progress = False
            self.serial_message_handler.start_serial_reading()
            self.serial_handshake_handler.start_ping_loop()
            self.start_heartbeat()

    async def attempt_connection(self, unhandled_errors):

        async with self.lock:
            try:
                # Open serial port in executor to prevent blocking
                loop = asyncio.get_running_loop()
                self.testing_port = await loop.run_in_executor(
                    None,
                    lambda: serial.Serial(self.port_name, self.baud_rate, timeout=self.timeout)
                )
            except (serial.SerialException, Exception) as e:
                print(f"Error setting up port: {e}")
                if ErrorTools.check_nested_error(e, FileNotFoundError):
                    unhandled_errors.append(FileNotFoundError)
                elif ErrorTools.check_nested_error(e, PermissionError):
                    unhandled_errors.append(PermissionError)
                else:
                    unhandled_errors.append(e)
                return False

        await asyncio.sleep(self.port_initialization_time)  # Wait for the serial port to initialize

        try:
            #Come back to for error handling
            handshake_result = await self.serial_handshake_handler.initial_handshake() #Come back to for error handling
            if handshake_result:
                self.handshake_completed = True
                print(f"Handshake completed on port {self.testing_port.name} at {self.testing_port.baudrate} baud.")
                return True
            else:
                await self.clean_connection() #Come back to for error handling
                return False
        except Exception as e:
            print(f"Handshake failed: {e}")
            await self.clean_connection() #Come back to for error handling
            return False

    async def clean_connection(self):
        await self.close_connection()
        self.deactivate_current_port()
        self.port_name = self.set_port
        self.com_description = None
        self.serial_port = None
        self.handshake_completed = False

    #Level 1
    async def open_connection(self):
        port = self.get_current_port()

        # Open the serial port using the stored configuration
        if not port:
            raise AttributeError(f"Serial port is not set.")
        if port.is_open:
            print(f"Serial connection on {port.name} is allready open.")
            return

        try:
            async with self.lock:
                # Open serial port in executor to prevent blocking
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, port.open)
                self.port_open = True
                print(f"Serial connection opened on {port.name} at {port.baudrate} baud.")
        except serial.SerialException as e:
            if ErrorTools.check_nested_error(e, FileNotFoundError):
                print(f"Serial port {port.name} does not exist.")
            else:
                print(f"Serial exception when attempting to open port {port.name}: {e}, moving on")
            raise

    async def close_connection(self):
        port = self.get_current_port()

        if not port:
            print(f"Serial port is not set.")
            return  # Exit early to prevent AttributeError

        if not port.is_open:
            print(f"Serial connection on {port} is already closed.")
            return

        try:
            async with self.lock:
                # Close serial port in executor to prevent blocking
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, port.close)
                self.port_open = False
                print(f"Serial connection on {port.name} closed.")
        except (serial.SerialException) as e:
            print(f"Serial exception when attempting to close port {port.name}: {e}, moving on")

    def get_connection_info(self):
        return {
            'port_name': self.port_name,
            'baud_rate': self.baud_rate,
            'timeout': self.timeout,
            'COM_description': self.com_description,
            'port_open': self.port_open
        }

    def start_heartbeat(self, interval=None):
        if interval is None:
            interval = self.heartbeat_interval
        self.heartbeat_task = asyncio.create_task(self.run_heartbeat(interval))

    def stop_heartbeat(self):
        # Cancel the heartbeat loop task if it's running
        if self.heartbeat_task:
            self.heartbeat_task.cancel()

    async def run_heartbeat(self, interval):
        try:
            while True:
                port_exists = await self.handle_port_existence()

                # Check the port availability
                if port_exists:
                    port_available = await self.handle_port_availability()
                    if port_available:
                        # Port is available
                        self.port_open = True
                        self.port_accessible = True

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            print("Heartbeat loop cancelled.")


class SerialMessageHandler:

    serial_reading_task = None
    serial_reading_interval = 0.05

    def __init__(self, serial_connection_manager, string_message_handler):
        self.serial_connection_manager = serial_connection_manager
        self.string_message_handler = string_message_handler

        self.received_message_buffer = [] #Using array, event queues don't allow checking without removing from it. Simpler and more robust.

        self.lock = asyncio.Lock()

    def find_message(self, message):
        if message not in self.string_message_handler.messages.keys():
            raise KeyError(f"Message type '{message}' does not exist. Valid messages are: {self.string_message_handler.valid_messages}") #Level 1
        
        for i in self.received_message_buffer:
            if i.message_key == message:
                self.received_message_buffer.pop(self.received_message_buffer.index(i))
                return i
        return None
    
    def find_message_with_timeout(self, message, timeout):
        

    async def pass_message_async(self, message, value=None, timestamp=None, recovery=False): #recover_COM is only run if recovery is True, to avoid a deadlock
        if message not in self.string_message_handler.messages.keys():
            raise KeyError(f"Message type '{message}' does not exist. Valid messages are: {self.string_message_handler.valid_messages}") #Level 1

        if not isinstance(timestamp, (datetime, type(None))):
            raise TypeError(f"Timestamp is of type {type(timestamp).__name__}; expected datetime or None") #Level 1

        full_message = self.string_message_handler.FullMessage(message, value, timestamp)
        try:
            encoded_message = self.string_message_handler.encode_message(full_message)
        except ValueError:
            raise TypeError(f"Timestamp is of type {type(timestamp).__name__}; expected datetime or None") #Level 3
        built_message = self.string_message_handler.build_message(encoded_message)

        try:
            await self.send_message_async(built_message, recovery = recovery) #Level 5
        except Exception as e:
            print(f"Error sending message: {e}")
            raise

    async def get_message_async(self, recovery = True): #recover_COM is only run if recovery is True, to avoid a deadlock
        try:
            message_str = await self.receive_message_async(recovery = recovery)
        except Exception as e:
            print(f"Error receiving message: {e}")
            raise
        parsed = self.string_message_handler.parse_message(message_str)
        decoded_message = self.string_message_handler.decode_message(parsed)
        return decoded_message

    async def send_message_async(self, message, recovery = True): #recover_COM is only run if recovery is True, to avoid a deadlock
        if not isinstance(message, str):
            raise TypeError("Message is not a string") #Level 1
        
        #Use test temporary test port if the official isn't confirmed yet.
        port = self.serial_connection_manager.get_current_port()
        
        loop = asyncio.get_running_loop()

        unhandled_error = None

        async with self.lock:
            try:
                await loop.run_in_executor(None, port.write, (message + '\n').encode('utf-8'))
            except (serial.SerialException, Exception) as e:
                print(f"Message not sent: {e}")
                if ErrorTools.check_nested_error(e, FileNotFoundError):
                    unhandled_error = FileNotFoundError #Level 1
                elif ErrorTools.check_nested_error(e, PermissionError):
                    unhandled_error = PermissionError #Level 1
                else:
                    unhandled_error = e #Level 1
            
            if unhandled_error: #We only want to recover and possibly raise the error if the error is there
                if recovery:
                    print(f"Persistent error when sending message: {e}, attempting troubleshooting")
                    try:
                        self.serial_connection_manager.recover_COM(attempt_setup = recovery)
                    except Exception as e:
                        raise e

                    #Attempt a resend to get the message through
                    try:
                        await loop.run_in_executor(None, port.write, (message + '\n').encode('utf-8'))
                    except (serial.SerialException, Exception) as e:
                        print(f"Message not sent: {e}")
                        #In the rare event of fallout again, propagate and tell user
                        raise e #Serial connection can't be set up or recovered #Level 1
                else:
                    print(f"Persistent error when sending message: {e}, telling user")
                    raise unhandled_error

        print(f"Sent: {message.encode()}")

    async def receive_message_async(self, recovery = True): #recover_COM is only run if recovery is True, to avoid a deadlock  
        #Use test temporary test port if the official isn't confirmed yet.
        port = self.serial_connection_manager.get_current_port()

        loop = asyncio.get_running_loop()

        message_decoded = ""

        unhandled_error = None

        async with self.lock:
            try:
                message = await loop.run_in_executor(None, port.readline())
                message_decoded = message.decode('utf-8').strip()
            except (serial.SerialException, Exception) as e:
                print(f"Message not sent: {e}")
                if ErrorTools.check_nested_error(e, FileNotFoundError):
                    unhandled_error = FileNotFoundError #Level 1
                elif ErrorTools.check_nested_error(e, PermissionError):
                    unhandled_error = PermissionError #Level 1
                else:
                    unhandled_error = e #Level 1

            if unhandled_error: #We only want to recover and possibly raise the error if the error is there
                if recovery:
                    print(f"Persistent error when receiving message: {e}, attempting troubleshooting")
                    try:
                        self.serial_connection_manager.recover_COM(attempt_setup = recovery)
                    except Exception as e:
                        raise e

                    #Attempt a rereceive to get the message through
                    try:
                        if port.in_waiting:
                            message = await loop.run_in_executor(None, port.readline())
                            message_decoded = message.decode('utf-8').strip()
                    except (serial.SerialException, Exception) as e:
                        print(f"Message not received: {e}")
                        #In the rare event of fallout again, propagate and tell user
                        raise e #Serial connection can't be set up or recovered #Level 1
                else:
                    print(f"Persistent error when receiving message: {e}, telling user")
                    raise unhandled_error

        print(f"Received: {message_decoded}")
        return message_decoded
    
    def start_serial_reading(self, interval=None):
        if interval is None:
            interval = self.serial_reading_interval
        self.serial_reading_task = asyncio.create_task(self.run_serial_reading(interval))

    def stop_serial_reading(self):
        # Cancel the serial reading loop task if it's running
        if self.serial_reading_task:
            self.serial_reading_task.cancel()

    async def run_serial_reading(self, interval):
        try:
            while True:
                message = self.get_message_async()
                if message.message_valid:
                    self.received_message_buffer.append(message)
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            print("Serial reading loop cancelled.")
    

class SerialHandshakeHandler:
    ping_task = None
    #ping_interval * ping_attempts = total time
    ping_interval = 5  # Default ping interval in seconds
    ping_attempts = 3 #Times pinging before connection loss is assumed

    def __init__(self, serial_message_handler, handshake_message, handshake_response, gui_queue=None):
        self.serial_message_handler = serial_message_handler
        self.handshake_message = handshake_message
        self.handshake_response = handshake_response
        self.gui_queue = gui_queue  # Optional: For GUI updates

        self.lock = asyncio.Lock()

    async def ping_handshake(self):
        #Change this to wait for a response via a timer. If no response within timneout, return false, else return true.
        # Perform the handshake asynchronously
        try:
            await self.serial_message_handler.pass_message_async(self.handshake_message)
            print("Sent handshake ping.")
        except Exception as e:
            print(f"Error during ping handshake: {e}")
            raise
        
        try:
            response = await self.serial_message_handler.get_message_async()
        except Exception as e:
            print(f"Error during ping handshake: {e}")
            raise
    
        response_message = response.message_key
        if response_message == self.handshake_response:
            print("Received valid handshake response.")
            return True
        else:
            print("Invalid handshake response.")
            return False

    async def initial_handshake(self):
        # Perform the initial handshake asynchronously
        try:
            await self.serial_message_handler.pass_message_async(self.handshake_message, recovery = False)
            print("Initiated initial handshake.")retreyer
            response = await self.serial_message_handler.get_message_async(recovery = False)
            response_message = response.message_key
            if response_message == self.handshake_response:
                print("Received valid handshake response.")
                return True
            else:
                print("Invalid or no handshake response.")
                return False
        except Exception as e:
            print(f"Error during initial handshake: {e}")
            return False

    async def run_ping_loop(self, interval):
        # Ping loop to perform handshake every `interval` seconds
        try:
            while True:
                await self.ping_handshake()
                await asyncio.sleep(interval)
        except asyncio.CancelledError: #Level 1
            print("Ping loop cancelled.")

    def start_ping_loop(self, interval=None):
        if interval is None:
            interval = self.ping_interval
        self.ping_task = asyncio.create_task(self.run_ping_loop(interval))

    def stop_ping_loop(self):
        # Cancel the ping loop task if it's running
        if self.ping_task:
            self.ping_task.cancel()

class GUI:
    def __init__(self, serial_manager):
        self.serial_manager = serial_manager
        self.serial_handshake_handler = self.serial_manager.serial_handshake_handler

        self.lock = threading.Lock()

        self.root = tk.Tk()
        self.root.title("Serial Communication GUI")
        self.root.geometry("400x300")
        self.gui_queue = queue.Queue()

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
        self.root.after(100, self.check_queue)

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

class SerialManager:
    """
    Central manager for all serial communication functionalities.
    Encapsulates connection management, message handling, and handshake processes.
    """
    gui_queue = None #Will be set to GUI's gui_queue by shared reference after SerialManager's instanciation

    def __init__(self):
        self.string_message_handler = StringMessageHandler()
        self.serial_connection_manager = SerialConnectionManager(gui_queue=self.gui_queue)
        self.serial_message_handler = SerialMessageHandler(self.serial_connection_manager, self.string_message_handler)
        self.serial_handshake_handler = SerialHandshakeHandler(
            self.serial_message_handler, "ping_sending", "ping_receiving"
        )
        self.serial_connection_manager.serial_handshake_handler = self.serial_handshake_handler #This is sketchy, sorry, it works though
        self.serial_connection_manager.serial_message_handler = self.serial_message_handler

        self.loop = asyncio.new_event_loop()  # Create a new event loop

        self.lock = asyncio.Lock()

    async def setup_serial(self):
        try:
            await self.serial_connection_manager.setup_COM()
        except Exception as e:
            print("Setup failed. Failed to complete handshake.")
            if self.gui_queue:
                self.gui_queue.put("Setup failed. Failed to complete handshake.")
            return
        self.serial_message_handler.start_serial_reading()
        if self.gui_queue:
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
        self.serial_connection_manager.stop_heartbeat()
        self.serial_message_handler.stop_serial_reading()
        # Schedule the clean_connection coroutine in the event loop
        asyncio.run_coroutine_threadsafe(
            self.serial_connection_manager.clean_connection(),
            self.loop
        )
        self.loop.call_soon_threadsafe(self.loop.stop())

class ProcessManager:
    """
    Encapsulates overall procedures for managing processes
    """
    asyncio_thread = None

    def __init__(self, serial_manager, gui):
        self.serial_manager = serial_manager
        self.gui = gui

    # Boots up the system
    def startup(self):
        # Start asyncio event loop in a separate thread
        self.asyncio_thread = threading.Thread(target=self.run_asyncio_loop, daemon=True)
        self.asyncio_thread.start()

        # Give the event loop some time to start
        time.sleep(0.1)

        try:
            # Run the GUI in the main thread
            print("Starting GUI...")
            self.gui.run()
        except KeyboardInterrupt:
            print("Program interrupted by user.")
        finally:
            self.full_shutdown()

    def run_asyncio_loop(self):
        asyncio.set_event_loop(self.serial_manager.loop)
        self.serial_manager.loop.run_until_complete(self.serial_manager.setup_serial())
        self.serial_manager.loop.run_forever()

    def full_shutdown(self):
        self.serial_manager.shutdown()
        self.asyncio_thread.join()
        print("Shutdown complete.")

def main():
    # Initialize SerialManager instance
    serial_manager = SerialManager()

    # Initialize GUI
    gui = GUI(serial_manager)

    # Set gui_queue in SerialManager and its components
    serial_manager.gui_queue = gui.gui_queue
    serial_manager.serial_connection_manager.gui_queue = gui.gui_queue
    serial_manager.serial_handshake_handler.gui_queue = gui.gui_queue

    process_manager = ProcessManager(serial_manager, gui)

    process_manager.startup()

if __name__ == "__main__":
    main()
