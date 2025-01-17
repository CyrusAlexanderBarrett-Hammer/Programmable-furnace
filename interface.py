# #SCREAMING IMPORTANCE: Send the original version to github, and then thev new version after. You can go back in history if you don't want the complicated concurrency.
# #ALSO: WRITE DOCUMENTATION BRIEFLY ABOUT THE FUNCTIONALITY OF THE ASYNC SPECIFIC STUFF, ABSTRACTLY FRAMING THE STRUCTURE AND HOW IT OPERATES. IT'S TO EXPLAIN HOW IT WORKS, IGNORING THE REST

# #Global, perpetual peace by 3024?

#TODO: Remove type checks where you can. Keep type checks at entry points only, where it's necessary.
#TODO: Make shure the timestamp is optional in both sending and receiving, Arduino side.
#TODO: Make a single point of reference for reading serial messages that continuously checks for them, done in a background task started initial handshake. The newest item is stored, avoids mix-ups. Every other place taht needs serial messages must be rewritten to use this, including the periodic handshake.
#TODO: Split the program into files to make it tidy, one for communication, and one for task management and front end/user interaction
#TODO: Get rid of for-loops and combine if-else statements with one line per condition
#TODO: Add robustivity and recovery for serial connection
#TODO: Add option for manually set COM
#TODO: Implement checksums for recieving data
#TODO: Sync timestamps and current time between PC and Arduino, after PC's clock. Keep actual PC time though.
#TODO: Write the protocol in the quick notes
#Everything is object oriented of course!

# import time

# from collections import namedtuple

# import asyncio

# import serial
# import serial.tools.list_ports


# class StringMessageHandler:
#     MessageStruct = namedtuple('MessageStruct', ['category', 'message'])
#     messages = {
#         "ping_sending": MessageStruct("1", "1"),
#         "ping_receiving": MessageStruct("1", "2")
#     }

#     #This is currently not used! They can be sent with each message to specify type, avoiding None.
#     message_type_designators = {
#         "category": "01",
#         "message": "02",
#         "value": "03",
#         "timestamp": "04"
#     }

#     def build_message(self, message, value = None, timestamp = True):
#         # Protocol: message type value,message value for type,optional value,optional time stamp. Values are split by comma delimiter.
#         outgoing_parts = []

#         # Try to get the message type value
#         try:
#             message_value = self.messages[message]
#         except KeyError as e:
#             raise ValueError(f"Message type '{message}' does not exist") from e
        
#         message_type_designators_value = self.message_type_designators

#         outgoing_parts.append(message_value.category)
#         outgoing_parts.append(message_value.message)

#         if not value is None:
#             outgoing_parts.append(str(value))
#         else:
#             outgoing_parts.append("NaN")

#         # Add the timestamp if required
#         if timestamp:
#             import time
#             outgoing_parts.append(str(int(time.time())))  # Use actual timestamp
#         else:
#             outgoing_parts.append("NaN")

#         # Join all parts with a comma
#         outgoing = ",".join(outgoing_parts)

#         return(outgoing)

#     def parse_message(self, message_str):
#         # Split the message string into parts
#         incoming_parts = message_str.split(',')

#         # Check if the message has the correct number of parts
#         if len(incoming_parts) != 4:
#             raise ValueError("Invalid message format")

#         # Extract the parts
#         category = incoming_parts[0]
#         message = incoming_parts[1]
#         value = incoming_parts[2] if incoming_parts[2] != 'NaN' else None
#         timestamp = incoming_parts[3] if incoming_parts[3] != 'NaN' else None

#         # Try to find the message key based on category and message
#         message_key = None
#         for key, msg_val in self.messages.items():
#             if msg_val.category == category and msg_val.message == message:
#                 message_key = key
#                 break

#         if message_key is None:
#             raise ValueError(f"Unknown message type for category '{category}' and message '{message}'")

#         # Optionally, convert timestamp to an integer if it's not None
#         if timestamp is not None:
#             timestamp = int(timestamp)

#         return {
#             'message_key': message_key,
#             'value': value,
#             'timestamp': timestamp
#         }

# class SerialConnectionManager:
#     def __init__(self, port = None, baud_rate=9600, timeout=2):
#         self.port = port                # Store the COM port
#         self.baud_rate = baud_rate      # Store the baud rate
#         self.timeout = timeout          # Store the timeout
#         self.com_description = None
#         self.serial_port = None

#         self.handshake_completed = False

#     async def setup_COM(self, serial_handshake_handler):
#         if self.port is None:
#             all_ports = serial.tools.list_ports.comports()
#             arduino_ports = []
#             for i in all_ports:
#                 if "Arduino" in i.description:
#                     arduino_ports.append(i)
#                     #Listen for furnace controller Arduino identifier
#             for i in arduino_ports:
#                 self.port = i.name
#                 self.serial_port = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
#                 self.close_connection()
#                 self.open_connection()
#                 await asyncio.sleep(2)
#                 handshake_result = serial_handshake_handler.initial_handshake()
#                 if handshake_result:
#                     self.handshake_completed = True
#                     print(f"Handshake completed, communicating with Arduino on port {self.port} at {self.baud_rate} {i.description} baud.")
#                     break
#                 else:
#                     self.close_connection()
#                     self.com_description = None
#                     self.serial_port = None
#                     self.handshake_completed = False

#     def open_connection(self):
#         # Open the serial port using the stored configuration
#         self.serial_port.open()
#         print(f"Serial connection opened on {self.port} at {self.baud_rate} baud.")

#     def close_connection(self):
#         # Close the serial port
#         if self.serial_port and self.serial_port.is_open:
#             self.serial_port.close()
#             print(f"Serial connection on {self.port} closed.")

#     def get_connection_info(self):
#         return {
#             'port': self.port,
#             'baud_rate': self.baud_rate,
#             'timeout': self.timeout,
#             'COM_description': self.com_description,
#             'is_open': self.serial_port.is_open if self.serial_port else False
#         }
    
# class SerialHandshakeHandler:
#     def __init__(self, serial_message_handler, handshake_message, handshake_response):
#         self.serial_message_handler = serial_message_handler
#         self.handshake_message = handshake_message
#         self.handshake_response = handshake_response

#     def ping_handshake(self):
#         self.serial_message_handler.pass_message(self.handshake_message)

#     def initial_handshake(self):
#         # Perform the handshake. Only other place than the main loop where serial messages can be read via a read function!
#         self.serial_message_handler.pass_message(self.handshake_message)
#         print("B")
#         response = self.serial_message_handler.get_message()
#         response_message = response["message_key"]
#         return response_message == self.handshake_response
    
#     def ping_handshake(self):
#         self.serial_message_handler.pass_message(self.handshake_message)
    
# class SerialMessageHandler:

#     def __init__(self, serial_connection_manager, string_message_handler):
#         self.serial_connection_manager = serial_connection_manager
#         self.string_message_handler = string_message_handler

#     def pass_message(self, message, value = None, timestamp = True):
#         message = self.string_message_handler.build_message(message, value = None, timestamp = True)
#         self.send_message(message)

#     def get_message(self):
#         message_str = self.receive_message()
#         parsed = self.string_message_handler.parse_message(message_str)
#         return parsed

#     def send_message(self, message):
#         self.serial_connection_manager.serial_port.write((message).encode('utf-8'))
#         print((message).encode())
#         #Add error handling

#     def receive_message(self):
#         #Add error handling
#         return self.serial_connection_manager.serial_port.readline().decode('utf-8').strip()


# serial_connection_manager = SerialConnectionManager()
# string_message_handler = StringMessageHandler()
# serial_message_handler = SerialMessageHandler(serial_connection_manager, string_message_handler)
# serial_handshake_handler = SerialHandshakeHandler(serial_message_handler, "ping_sending", "ping_receiving")

# loop = asyncio.get_event_loop()
# try:
#     loop.run_until_complete(serial_connection_manager.setup_COM(serial_handshake_handler))
# except Exception as e:
#     print(e)
# finally:
#     loop.close()


#Global, perpetual peace by 3024?

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

        # Traverse to the last traceback in the chain
        while tb.tb_next:
            tb = tb.tb_next

        # Extract the function name from the last frame
        origin_function = tb.tb_frame.f_code.co_name
        return origin_function

class TimeManager:
    time_string_format = "%m/%d/%Y %H:%M:%S"

    def datetime_to_string(self, datetime_object):
        if not isinstance(datetime_object, datetime):
            print(f"datetime_object is of type {type(datetime_object)} is not a datetime object")
            raise TypeError(f"datetime_object is of type {type(datetime_object)} is not a datetime object")
        try:
            string = datetime_object.strftime(self.time_string_format)
        except ValueError as e:
            print(f"Format is incorrect, expected {self.time_string_format}. Big letters can include a zero as first digit, like 05, small letters cannot.")
            raise
        return string

    def string_to_datetime(self, string):
        if not isinstance(string, str):
            print(f"string is of type {type(string)} is not a string")
            raise TypeError(f"string is of type {type(string)} is not a string")
        try:
            datetime_object = datetime.strptime(string, self.time_string_format)
        except ValueError:
            print(f"Format is incorrect, expected {self.time_string_format}. Big letters can include a zero as first digit, like 05, small letters cannot.")
            raise
        return datetime_object

class StringMessageHandler:

    MessageStruct = namedtuple('MessageStruct', ['category', 'message'])

    messages = {
        "ping_sending": MessageStruct("1", "1"),
        "ping_receiving": MessageStruct("1", "2")
    }

    valid_messages = ", ".join(messages.keys())

    message_part_separator = ","  # Corrected typo from 'saperator' to 'separator'

    def __init__(self, time_manager):
        self.time_manager = time_manager

    @dataclass
    class FullMessage:

        message_key: str
        value: Optional[Any] = None
        timestamp: Optional[datetime] = None
        message_valid = False

    def build_message(self, full_message):
        # Protocol: message type value,message value for type, optional value, optional timestamp.
        # Parts are separated by the part separator character.

        outgoing_parts = []

        # Construct the full message string, ready to be sent
        message = full_message.message_key
        outgoing_parts.append(message)
        outgoing_parts.append(full_message.value if full_message.value is not None else "NaN")
        outgoing_parts.append(full_message.timestamp if full_message.timestamp is not None else "NaN")

        # Join all parts with the part separator character
        outgoing = self.message_part_separator.join(outgoing_parts)

        return outgoing

    def parse_message(self, message_str):
        message_valid = False
        expected_parts = 4

        # Split the message string into parts
        incoming_parts = message_str.split(self.message_part_separator)

        # Check if the message has the correct number of parts
        if len(incoming_parts) != expected_parts:
            print(f"Message {message_str} has an unexpected number of parts. It has {len(incoming_parts)} parts, expected {expected_parts}. Setting every part to None, the message to invalid, and moving on")
        else:
            message_valid = True

        if message_valid:
            parsed = {
                'message_category': incoming_parts[0],
                'message_value': incoming_parts[1],
                'value': incoming_parts[2],
                'timestamp': incoming_parts[3],
                'message_valid': True
            }
        else:
            parsed = {
                'message_category': None,
                'message_value': None,
                'value': None,
                'timestamp': None,
                'message_valid': False
            }

        # Extract and return all the parts
        return parsed

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
                formatted_timestamp = self.time_manager.datetime_to_string(full_message.timestamp)
            except ValueError:
                print(f"Format is incorrect, expected {self.time_manager.time_string_format}. Big letters can include a zero as first digit, like 05, small letters cannot.")
                raise
            full_message.timestamp = str(formatted_timestamp)
        else:
            full_message.timestamp = "NaN"
        return full_message

    def decode_message(self, parsed):
        # Try to find the message key based on category and message
        message_valid = False
        message_key = None
        value = None
        timestamp = None

        if parsed["message_valid"]:
            message_key = None
            for key, msg_val in self.messages.items():
                if msg_val.category == parsed["message_category"] and msg_val.message == parsed["message_value"]:
                    message_key = key
                    break
            if message_key is None:
                print(f"Unknown message type for message type category '{parsed['message_category']}' and message value '{parsed['message_value']}', setting to None, the message to invalid, and moving on")
            else:
                message_valid = True

            value = parsed["value"] if parsed["value"] != "NaN" else None
            timestamp = parsed["timestamp"] if parsed["timestamp"] != "NaN" else None

            if timestamp is not None:
                try:
                    converted_datetime = self.time_manager.string_to_datetime(timestamp)
                except ValueError:
                    print(f"Format is incorrect, expected {self.time_manager.time_string_format}. Setting to None, the message to invalid, and moving on")
                    converted_datetime = None
                    message_valid = False
                timestamp = converted_datetime

        return self.FullMessage(message_key, value, timestamp, message_valid)

class SerialConnectionManager:

    com_description = None
    serial_port = None

    port_open = False
    port_accessible = False
    handshake_completed = False

    connection_attempts = 5
    heartbeat_task = None
    heartbeat_interval = 1  # Default heartbeat interval in seconds

    def __init__(self, port=None, baud_rate=9600, timeout=2, gui_queue=None):
        self.port = port                # Store the COM port
        self.baud_rate = baud_rate      # Store the baud rate
        self.timeout = timeout          # Store the timeout

        self.set_port = port

        self.port_specified = True if self.port is not None else False

        self.lock = asyncio.Lock()
        self.gui_queue = gui_queue  # Optional: For GUI updates

        if not isinstance(baud_rate, int):
            print(f"Baudrate {self.baud_rate} not an integer")
            raise TypeError(f"Baudrate {self.baud_rate} not an integer")
        if not isinstance(timeout, (int, float)):
            print(f"Timeout {self.timeout} not an integer or float")
            raise TypeError(f"Timeout {self.timeout} not an integer or float")

    async def check_port_existence(self):
        loop = asyncio.get_running_loop()
        all_ports = await loop.run_in_executor(None, serial.tools.list_ports.comports)
        if any(port.name == self.port for port in all_ports):
            return True
        else:
            return False

    async def check_port_availability(self):
        async with self.lock:
            try:
                await self.close_connection()
                await self.open_connection()
                return True
            except PermissionError:
                return False

    async def setup_COM(self, serial_handshake_handler):
        unhandled_errors = []
        arduino_ports = []  # Initialize arduino_ports

        for i in range(self.connection_attempts):
            unhandled_errors.clear()

            if self.port_specified:
                # Attempt to connect to the specified port
                success = await self.attempt_connection(serial_handshake_handler, unhandled_errors)
                if success:
                    break
            else:
                async with self.lock:
                    all_ports = serial.tools.list_ports.comports()
                    arduino_ports = [port for port in all_ports if "Arduino" in port.description]

                for port in arduino_ports:
                    self.port = port.name  # Set to current port
                    success = await self.attempt_connection(serial_handshake_handler, unhandled_errors)
                    if success:
                        break

            if self.handshake_completed:
                self.port_open = True
                self.port_accessible = True
                break

        if self.serial_port is None:
            # Handle the situation where we couldn't connect
            await self.clean_connection()  # Await the async method
            if not arduino_ports and not self.port_specified:
                raise NoDeviceError("No Arduino connected")
            for e in unhandled_errors:
                raise e

    async def attempt_connection(self, serial_handshake_handler, unhandled_errors):
        async with self.lock:
            try:
                # Open serial port in executor to prevent blocking
                loop = asyncio.get_running_loop()
                self.serial_port = await loop.run_in_executor(
                    None,
                    lambda: serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
                )
            except (FileNotFoundError, PermissionError, Exception) as e:
                print(f"User-caused error setting up port: {e}")
                unhandled_errors.append(e)
                return False

        await asyncio.sleep(2)  # Wait for the serial port to initialize

        handshake_result = await serial_handshake_handler.initial_handshake()
        if handshake_result:
            self.handshake_completed = True
            print(f"Handshake completed, communicating with Arduino on port {self.port} at {self.baud_rate} baud.")
            return True
        else:
            await self.clean_connection()
            return False

    async def clean_connection(self):
        await self.close_connection()
        self.port = self.set_port
        self.com_description = None
        self.serial_port = None
        self.handshake_completed = False

    async def open_connection(self):
        # Open the serial port using the stored configuration
        if not self.serial_port:
            print(f"In open_connection: Serial port {self.port} is not set.")
            raise AttributeError(f"Serial port is not set.")
        if self.serial_port.is_open:
            print(f"Serial connection on {self.port} is already open, moving on.")
            return

        try:
            async with self.lock:
                # Open serial port in executor to prevent blocking
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.serial_port.open)
                self.port_open = True
                print(f"Serial connection opened on {self.port} at {self.baud_rate} baud.")
        except FileNotFoundError as e:
            print(f"Serial port {self.port} does not exist")
        except serial.SerialException as e:
            print(f"Serial exception when attempting to open serial port {self.port}")
            raise

    async def close_connection(self):
        if not self.serial_port:
            print(f"In close_connection: Serial port {self.port} is not set, moving on.")
            return  # Exit early to prevent AttributeError

        if not self.serial_port.is_open:
            print(f"Serial connection on {self.port} is already closed, moving on.")
            return

        try:
            async with self.lock:
                # Close serial port in executor to prevent blocking
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.serial_port.close)
                self.port_open = False
                print(f"Serial connection on {self.port} closed.")
        except (serial.SerialException, OSError) as e:
            print(f"Serial exception when attempting to close serial port {self.port}: {e}, moving on")

    def get_connection_info(self):
        return {
            'port': self.port,
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
                # Check the port existence
                port_exists = await self.check_port_existence()
                if not port_exists:
                    # Port is disconnected
                    self.port = None
                    self.com_description = None
                    self.port_open = False
                    self.port_accessible = False
                    if self.gui_queue:
                        self.gui_queue.put("Port disconnected.")
                    break  # Exit the loop
                else:
                    # Port exists
                    self.port_open = True
                    self.port_accessible = True
                    # You may want to update com_description here

                # Check the port availability
                port_available = await self.check_port_availability()
                if not port_available:
                    # Port is occupied
                    self.port_open = False
                    self.port_accessible = False
                    if self.gui_queue:
                        self.gui_queue.put("Port is already occupied.")
                    break  # Exit the loop
                else:
                    # Port is available
                    self.port_open = True
                    self.port_accessible = True

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            print("Heartbeat loop cancelled.")

class SerialMessageHandler:

    def __init__(self, serial_connection_manager, string_message_handler):
        self.serial_connection_manager = serial_connection_manager
        self.string_message_handler = string_message_handler

        self.lock = asyncio.Lock()

    async def pass_message_async(self, message, value=None, timestamp=None):
        print("Pass")
        if message not in self.string_message_handler.messages.keys():
            print(f"Message type '{message}' does not exist. Valid messages are: \n {self.string_message_handler.valid_messages}")
            raise KeyError(f"Message type '{message}' does not exist. Valid messages are: \n {self.string_message_handler.valid_messages}")

        if not isinstance(timestamp, (datetime, type(None))):
            print(f"Time stamp is of type {type(timestamp).__name__}, not datetime")
            raise TypeError(f"Time stamp is of type {type(timestamp).__name__}, not datetime")

        full_message = self.string_message_handler.FullMessage(message, value, timestamp)
        encoded_message = self.string_message_handler.encode_message(full_message)
        built_message = self.string_message_handler.build_message(encoded_message)

        await self.send_message_async(built_message)

    async def get_message_async(self):
        message_str = await self.receive_message_async()
        parsed = self.string_message_handler.parse_message(message_str)
        decoded_message = self.string_message_handler.decode_message(parsed)

        return decoded_message

    async def send_message_async(self, message):
        if not isinstance(message, str):
            raise KeyError("Message is not a string")
        loop = asyncio.get_running_loop()
        async with self.lock:
            await loop.run_in_executor(None, self.serial_connection_manager.serial_port.write, (message + '\n').encode('utf-8'))
            print(f"Sent: {message.encode()}")

    async def receive_message_async(self):
        loop = asyncio.get_running_loop()
        async with self.lock:
            message = await loop.run_in_executor(None, self.serial_connection_manager.serial_port.readline)
            message_decoded = message.decode('utf-8').strip()
            print(f"Received: {message_decoded}")
        return message_decoded

class SerialHandshakeHandler:
    ping_task = None
    ping_interval = 60  # Default ping interval in seconds

    def __init__(self, serial_message_handler, handshake_message, handshake_response, gui_queue=None):
        self.serial_message_handler = serial_message_handler
        self.handshake_message = handshake_message
        self.handshake_response = handshake_response
        self.gui_queue = gui_queue  # Optional: For GUI updates

        self.lock = asyncio.Lock()

    async def ping_handshake(self):
        # Perform the handshake asynchronously
        await self.serial_message_handler.pass_message_async(self.handshake_message)
        print("Sent handshake ping.")
        response = await self.serial_message_handler.get_message_async()
        response_message = response.message_key
        if response_message == self.handshake_response:
            print("Received valid handshake response.")
            if self.gui_queue:
                self.gui_queue.put("Ping handshake successful.")
            return True
        else:
            print("Invalid handshake response.")
            if self.gui_queue:
                self.gui_queue.put("Ping handshake failed.")
            return False

    async def initial_handshake(self):
        # Perform the initial handshake asynchronously
        await self.serial_message_handler.pass_message_async(self.handshake_message)
        print("Initiated initial handshake.")
        response = await self.serial_message_handler.get_message_async()
        response_message = response.message_key
        return response_message == self.handshake_response

    async def run_ping_loop(self, interval):
        # Ping loop to perform handshake every `interval` seconds
        try:
            while True:
                handshake_success = await self.ping_handshake()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
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
    gui_queue = None

    def __init__(self, time_manager):
        if not isinstance(time_manager, TimeManager):
            print(f"time_manager is of type {type(time_manager)}, expected TimeManager")
            raise TypeError(f"time_manager is of type {type(time_manager)}, expected TimeManager")

        self.time_manager = time_manager
        self.string_message_handler = StringMessageHandler(self.time_manager)
        self.serial_connection_manager = SerialConnectionManager(gui_queue=self.gui_queue)
        self.serial_message_handler = SerialMessageHandler(self.serial_connection_manager, self.string_message_handler)
        self.serial_handshake_handler = SerialHandshakeHandler(
            self.serial_message_handler, "ping_sending", "ping_receiving"
        )

        self.loop = asyncio.new_event_loop()  # Create a new event loop

        self.lock = asyncio.Lock()

    async def setup_serial(self):
        # Setup serial connection
        await self.serial_connection_manager.setup_COM(self.serial_handshake_handler)
        if not self.serial_connection_manager.handshake_completed:
            print("Failed to complete handshake. Exiting.")
            if self.gui_queue:
                self.gui_queue.put("Setup failed.")
            return
        if self.gui_queue:
            self.gui_queue.put("Setup complete.")
        # Start the periodic ping loop after successful handshake
        self.serial_handshake_handler.start_ping_loop()
        # Start the heartbeat loop
        self.serial_connection_manager.start_heartbeat()

    def get_connection_info(self):
        return self.serial_connection_manager.get_connection_info()

    def shutdown(self):
        """
        Gracefully shutdown the asyncio event loop and close serial connections.
        """
        self.serial_handshake_handler.stop_ping_loop()
        self.serial_connection_manager.stop_heartbeat()
        # Schedule the clean_connection coroutine in the event loop
        asyncio.run_coroutine_threadsafe(
            self.serial_connection_manager.clean_connection(),
            self.loop
        )
        self.loop.call_soon_threadsafe(self.loop.stop)

class ProcessManager:
    """
    Encapsulates overall procedures for managing processes
    """
    asyncio_thread = None

    def __init__(self, serial_manager, gui, time_manager):
        self.time_manager = time_manager
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
    time_manager = TimeManager()

    # Initialize SerialManager instance
    serial_manager = SerialManager(time_manager)

    # Initialize GUI
    gui = GUI(serial_manager)

    # Set gui_queue in SerialManager and its components
    serial_manager.gui_queue = gui.gui_queue
    serial_manager.serial_connection_manager.gui_queue = gui.gui_queue
    serial_manager.serial_handshake_handler.gui_queue = gui.gui_queue

    process_manager = ProcessManager(serial_manager, gui, time_manager)

    process_manager.startup()

if __name__ == "__main__":
    main()
    # Use an event with an asynchronous coroutine for graceful shutdown.
    # The startup method in the process manager starts the shutdown coroutine. This one has an event that waits for the shutdown event to be triggered, then clears the event, and runs shutdown for everything that needs to be shut down.
    # If it all worked, teletubbies should print even after the serial ping reply bug.
    # print("Teletubbies!")

# from collections import namedtuple


# # from datetime import datetime

# # time_test = "25/5/2024 15:36:32.434"
# # format_test = "%d/%m/%Y %H:%M:%S.%f"
# # test = datetime.strptime(time_test, format_test)
# # if isinstance(test, datetime):
# #     print(f"FFFF{type(test).__name__}ff")
# # else:
# #     print("B")

import time

import serial
import serial.tools.list_ports

try:
    serial_port = serial.Serial("COM18", 9600, timeout=2)
    time.sleep(2)
    serial_port.close()
    print("closed")
    time.sleep(2)
    serial_port.open()
    print("open")

except Exception as e:
    print(e)


#Serial exceptions:
    # serial.Serial FileNotFoundError, the system cannot find the file specified: When the serial port specified isn't found
    # serial.Serial PermissionError, Access is denied: When the serial port is allready in use. Try closing it.

    # serial.write() PermissionError: When the serial port is disconnected while attempting to write.

    #serial.tools.list_ports.comports() Only hardware problems, can't be my problem. Use a simple Exception and raise OSError manually.

    #serial.open() FileNotFOundError, The system cannot find the file specified. Attempt another connect.

    #port.description: Ignore, don't look.
    #port.name: Ignore, don't look.

# test = []

# try:
#     hi = 0 / 0
# except Exception as e:
#     test.append(e)

# try:
#     for e in test:
#         if isinstance(e, ZeroDivisionError):
#             print("Handled ZeroDivisionError:", e)
#             raise(e)
#         elif isinstance(e, KeyError):
#             print("Handled KeyError:", e)
#         else:
#             print("Unhandled exception:", e)
# except ZeroDivisionError as e:
#     raise

# try:
#     try:
#         hi = 0 / 0
#     except ZeroDivisionError as e:
#         raise ZeroDivisionError("BOGUS!") from e
# except Exception as e:
#     raise ZeroDivisionError("EHEM") from e


from dataclasses import dataclass
from collections import namedtuple

# Define a named tuple
Coordinates = namedtuple('Coordinates', ['x', 'y'])

# Use the named tuple in a data class
@dataclass
class Point:
    name: str
    coords: Coordinates

# Example usage
coords = Coordinates(x=10, y=20)
point = Point(name="A", coords=coords)

total = f"{point.name}{point.coords.y}"

print(total)