# Programmable-furnace
Watchdog and PID controllers for any furnace.

WARNING: DO NOT MODIFY THE FURNACE OR SETTINGS FOR THE PROGRAM EXCEPT FOR THE COM PORT UNLESS YOU ARE QUALIFIED. THE WATCHDOG IS MEANT AS AN EXTRA LAYER OF SECURITY. AND TO INTERFACE WITH A PC. IN ANY CASE THE FURNACE MUST HAVE A BUILDT-IN OVERHEAT PROTECTION, WITH OR WITHOUT THE WATCHDOG!

This system is designed for furnaces, but can probably be used for many other things too!

Watchdog and PID controllers for any furnace. It uses an Arduino with output directly to the furnace's SSR relay (only modify the furnace if you're qualified) and Python as an interface. Can be hooked up to Labview or anything that can call Python methods.

It's modular, so the PID and watchdog are two separate Arduino programs that can be run on two separate Arduinos. The PID Arduino can give on/off signals either directly to the furnace, or to the watchdog module. The watchdog module will only forward to the furnace's SSR if it's safe to do so. The watchdog can also be used on it's own, just configure it in the watchdog Arduino program. This gives redundancy; if one Arduino fails, the other will still run and keep the heat off during overheat.

One Python program on the PC interfaces with both modules at once.

The PID is run on the PC and gives signals to the Arduino when to turn on and off, with temperature feedback of course. Temperature measurements are done with a MAX31856 sensor. The watchdog part takes input from the PID PWM signal via an SR latch to check if it's frozen high, and it also checks if the temperature is above a set max value, if that is set to yes. This means the watchdog can be used without the expensive temperature sensor.

If the watchdog detects frozen PID PWM or overheat, or if serial connection is lost if that is set, it will turn off the signal to the SSR to turn off the furnace. A manual disconnection and reconnection of the Arduino controller device is required to clear the error. If there's no serial loss, the PC will be notified. An LED shows if serial communication is present. The PID can also give alarm to the PC on overheat.

It can recover the serial COM if it's lost or switched, but the user needs to write the COM port being used. The system can run for days without problems.


Currently, there's only the watchdog module, and it's settings need to be done from the Arduino code and not from a one-time setup via Labview or the GUI.