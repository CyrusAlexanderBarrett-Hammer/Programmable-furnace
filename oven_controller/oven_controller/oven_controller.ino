#include "String.h"

#include <Adafruit_MAX31856.h>
#include <SPI.h>;

const String negativeOneSentinel = "-1"; //NAN equivalent for when NaN can't be used. Can be used anywhere, but NaN should be used where possible

float devDelay = 100; //A stalling delay for use in development, in milliseconds

class Timer
{
  private:
    unsigned long durationMs;
    unsigned long startTime;

    void startTimer()
    {
      startTime = millis();
    }
  
  public:
    // Constructor with an additional parameter to start as timed out
    Timer(unsigned long _durationMs, bool _startTimedOut = false)
      : durationMs(_durationMs)
    {
        if (_startTimedOut) {
            // timedOut() will return true immediately
            startTime = millis() - durationMs;
        } else {
            startTimer(); // Start the timer normally
        }
    }

    void resetTimer()
    {
      startTime = millis();
    }

    unsigned long getElapsedTimeMs()
    {
      unsigned long currentTime = millis();
      unsigned long deltaTime = currentTime - startTime;
      return deltaTime;
    }

    float getElapsedTimeS()
    {
      float timeInSeconds = getElapsedTimeMs() / 1000;
      return timeInSeconds;
    }

    bool timedOut()
    {
      unsigned long elapsedTime = getElapsedTimeMs();

      if(elapsedTime >= durationMs)
      {
        return true;
      }
      else
      {
        return false;
      }
    }
};

enum class FailStates
{
  Successful,
  Unknown,
  Unsuccessful
};

class Max31856FaultHandler
{
  private:
    int8_t maxCS;

    const unsigned long sensorMeasurementTime = 20; //The sensor needs 20 milliseconds to update temperature measurement for value comparisons. Hardware limitation.

    float temperatureReference = NAN;
    float temperatureNew;

    int maxFailAttempts = 3;
    int failCount = 0;

    bool overrideUpdateFail = true; //Use new temperature after next iteration after resetting the sensor before increasing fail count

    Timer recheckReadingTimer; //Declaring the instance for later initalization in constructor and use

  public:
    Max31856FaultHandler(uint8_t _maxCS) //Constructor for setting values
            : maxCS(_maxCS), recheckReadingTimer(sensorMeasurementTime) {} //Initializing the instance in the constructor

    void resetThermosensor(){
      digitalWrite(maxCS, LOW);  // Select the MAX31856 via chip select
      SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE1)); //I SPENT AGES FINDING THIS! :-D
      SPI.transfer(0x0F);  // Write address (0x0F) with write command
      SPI.transfer(0x00);  // Write any byte to the register to clear the fault
      SPI.endTransaction();
      digitalWrite(maxCS, HIGH);  // Deselect the MAX31856 via chip select
    }

  FailStates handlePotentialFault(float temperatureReading)
  {
    if (recheckReadingTimer.timedOut())
    {
      temperatureNew = temperatureReading;
      recheckReadingTimer.resetTimer();
      if (isnan(temperatureReference)) 
      {
        if (isnan(temperatureNew))
        {
            failCount = maxFailAttempts;
        }
        else
        {
            temperatureReference = temperatureNew;
            failCount = 0;
            return FailStates::Successful;
        }
      }
      else
      {
        bool faultDetected = (!isnan(temperatureReference) && temperatureNew == temperatureReference) || isnan(temperatureNew);
        if (faultDetected)
        {
            resetThermosensor();
            if (overrideUpdateFail)
            {
                overrideUpdateFail = false;
                return FailStates::Unknown;
            }
            overrideUpdateFail = true;
            failCount++;
        }
        else
        {
            failCount = 0;
            temperatureReference = temperatureNew;
        }
      }
    }

    if (failCount >= maxFailAttempts)
    {
        return FailStates::Unsuccessful; //Failed permanently
    }
    else if (failCount > 0)
    {
        return FailStates::Unknown; //Not sure yet
    }
    else
    {
        return FailStates::Successful; //Normal operation
    }
  }
};

class OvenOverheatWatchdog
{
  private:
    float maxTemp;
  
  public:
    bool ovenOverheat = false;

    OvenOverheatWatchdog(float _maxTemp)
        : maxTemp(_maxTemp)
        {}

    void checkOverheat(float currentTemperature, bool temperatureSensorFailAlarm = false)
    {
      //If temperatureSensorFailAlarm is on, the high temperature of 2023 degrees (Labview sensor fail standard) is because of thermocouple fail, not overheat
      //We can't know if there's overheat if the sensor isn't working anyway, and no thermocouples or thermosensors can measure 2023 degrees or higher
      if((currentTemperature >= maxTemp) && !temperatureSensorFailAlarm)
      {
        ovenOverheat = true;
      }
    }
};

class SrLatchFrozenWatchdog
{
  //This class checks for high pulses after inversion from low by a NOT gate
  private:
    unsigned long srLatchLowDurationMs; //Maximum expected low duration
    int srLatchResetPin;
    int srLatchOutputPin;
  
    Timer srLatchLowTimer;
  
    bool srLatchOutputStatus;

  public:
    bool srLatchFrozen = false;

    SrLatchFrozenWatchdog(unsigned long _srLatchLowDurationMs, int _srLatchResetPin, int _srLatchOutputPin)
          : srLatchLowDurationMs(_srLatchLowDurationMs), srLatchResetPin(_srLatchResetPin), srLatchOutputPin(_srLatchOutputPin), srLatchLowTimer(_srLatchLowDurationMs)
        {}

    void begin()
    {
      pinMode(srLatchResetPin, OUTPUT);
      pinMode(srLatchOutputPin, INPUT);
    }

    void checkSrLatchFrozen()
    {
      srLatchOutputStatus = digitalRead(srLatchOutputPin);

      if(srLatchOutputStatus)
      {
        //Latch got set, everything in order
        srLatchLowTimer.resetTimer();
        digitalWrite(srLatchResetPin, HIGH); //Latch will go to low, and will go to high again if it's set pin is set to high (pulsed) by external signal
        return;
      }

      else if(srLatchLowTimer.timedOut())
      {
        //At this stage, the SR latch has not gone to high
        //Watchdog barks
        srLatchFrozen = true;
        return;
      }

      else
      {
        //Keep giving a chance ready for next time
        return;
      }
    }

};

class Max31856Sensor
{
  //args: max31856 CS designated pin for Chip Select (int), optional thermocouple type (int)

  private:
    const Adafruit_MAX31856 maxSensor;

    const uint8_t tcType; //Thermocouple type, see Max31856 library examples

    Max31856FaultHandler max31856FaultHandler;

  public:
    float currentTemp;
    bool temperatureSensorFailAlarm = false;

    Max31856Sensor(uint8_t _maxCS, uint8_t _tcType = 3) //Constructor for setting values
            : maxSensor(_maxCS), //Allready existing maxSensor object is set and initialized with the pin number value of _maxCS
              max31856FaultHandler(_maxCS),
              tcType(_tcType)
            {}

    void begin()
    {
      bool sensorBeginSuccess = maxSensor.begin();
      bool sensorNoOtherFaults = !maxSensor.readFault();
      bool sensorInitializationSuccess = sensorBeginSuccess && sensorNoOtherFaults;

      if (!sensorInitializationSuccess) //True if sensor initialization was successful, it's connected, and the couple type was correct
      {
        temperatureSensorFailAlarm = true;
      }
    }

    float readTemperature()
    {
      if (!temperatureSensorFailAlarm)
      {
        float currentTempReference = maxSensor.readThermocoupleTemperature();

        FailStates temperatureSensorFailStatus = max31856FaultHandler.handlePotentialFault(currentTempReference); //Alarm goes on if sensor is confirmed failed.

        if(temperatureSensorFailStatus == FailStates::Successful)
        {
          currentTemp = currentTempReference;
        }
        else if(temperatureSensorFailStatus == FailStates::Unsuccessful)
        {
          currentTemp = 2023;
          temperatureSensorFailAlarm = true;
        }

        //If unknown, don't update temperature
        return currentTemp;
      }

      else
      {
        currentTemp = 2023;
        return 2023; //Labview standard thermosensor error temperature, as per request from Terje
      }

    }


  //If setup configurations are implemented to be set from Python on PC, make methods here to change the values like max temperature, tc type etc (see "signals" in the documentation)
};

//Oven status and settings
struct Oven
{
  //args: Oven SSR pin (int), absolute max temperature for oven (float), goal temoperature for oven (float), force oven to stay off? (bool), use the heating simulation? (bool)

  //Simulation, heating override, etc adjustable for each individual oven if relevant
  
  private:
    const int ovenControllPin; //Oven SSR pin

    //Settings
    const bool heatingOverride; //Force actual heater to be off? Won't effect anything else.
    const bool useHeatingSimulation; //Ignore thermo sensor and fake temperature from controlled heating algorithm

  public:
    bool heatingOn;
    float currentTemp;
  
    //Settings
    float tempGoal; //Degrees
    float absoluteMaxTemp;
  
  
    Oven(int _ovenControllPin, float _absoluteMaxTemp, float _tempGoal = NAN, bool _heatingOverride = false, bool _useHeatingSimulation = false) //Constructor for setting values
            : ovenControllPin(_ovenControllPin), 
              tempGoal(_tempGoal),
              absoluteMaxTemp(_absoluteMaxTemp), 
              heatingOverride(_heatingOverride), 
              useHeatingSimulation(_useHeatingSimulation)
            {}
  
    void begin()
    {
      pinMode(ovenControllPin, OUTPUT);
    }
  
    void turnOvenControllPinOn()
    {
      digitalWrite(ovenControllPin, HIGH);
      heatingOn = false;
    }
  
    void turnOvenControllPinOff()
    {
      digitalWrite(ovenControllPin, LOW);
      heatingOn = false;
    }
  
    //If setup configurations are implemented to be set from Python on PC, make methods here to change the values like pin number, max temperature, temperature goal, etc (see "signals" in the documentation)
};

//Simulation status and settings, not important for the system, and can optionally be ignored
struct SimulationData
{
  //Args: All are optional. Time step (float), wattage (float), element heat buildup time (float), element heat cooldown time (float), oven heat capacity (float), heat loss in oven versus room temperature (float), room temperature (float), time step (float)

  //inputs
  float currentTemp = NAN; //Tcurrent, current temperature (currentTemp)
  bool heatingOn; //heatingOn is not used in the equation directly
  bool lastHeatingState; //Used to check state changes

  float stateTime; //t, time oven has been in current on/off state

  //Simulation parameters
  const float timeStep; //Deltat, simulation time step in seconds

  const float elementBuildupTime; //Ton, time element takes to reach full heat production in seconds
  const float elementCooldownTime; //Toff, time element takes to cool off again in seconds
  const float actualWattage; //Pactual(t) element heat production wattage per now (NOT NEEDED)
  const float wattage; //P, element power wattage rating CHECK
  const float heatCapacity; //C, oven heat capacity in joules per degree celsius
  const float lossCoefficient; //h, heat loss to environment per degree difference
  const float ambientTemperature; //Tenv, the room temperature

  SimulationData(float _timeStep = 0.0001, float _wattage = 3000, float _elementBuildupTime = 130, float _elementCooldownTime = 20, float _heatCapacity = 1500, float _lossCoefficient = 0.02, float _ambientTemperature = 23)
                : wattage(_wattage), elementBuildupTime(_elementBuildupTime), elementCooldownTime(_elementCooldownTime), heatCapacity(_heatCapacity), lossCoefficient(_lossCoefficient), ambientTemperature(_ambientTemperature), timeStep(_timeStep){}
};

struct MessageStruct
{
  char category; //Categories enforce structure
  char message;
};

struct ParsedMessageStruct
{
  //Category and message combines into instruction with MessageStruct
  MessageStruct *message;
  float value;
  String timestamp;
  // Indicate whether the parsed message is valid
  bool isValid;
};

namespace Messages{
  //Pre-written instructions
  //Categories encforce structure.
  static const MessageStruct PING_ARDUINO_PC = {'1', '2'}; //Sent to PC
  static const MessageStruct PING_PC_ARDUINO = {'1', '1'}; //Received from PC

  static const MessageStruct TEMPERATURE_READING = {'2', '1'}; //Sent to PC

  static const MessageStruct FORCE_EMERGENCY_STOP = {'4', '0'}; //Received from PC

  static const MessageStruct EMERGENCY_ALARM = {'9', '0'}; //Sent to PC
  static const MessageStruct THERMOSENSOR_ERROR = {'9', '1'}; //Sent to PC
  static const MessageStruct WATCHDOG_SR_LATCH_FROZEN = {'9', '2'}; //Sent to PC. The oven heating signal is stuck to high.
  static const MessageStruct OVEN_OVERHEAT = {'9', '3'}; //Sent to PC

  //Allows iteration by using pointers to Messages' memory addresses, unlike iterating over their structs directly
  const MessageStruct* messagePointers[] = {
    &Messages::PING_ARDUINO_PC,
    &Messages::PING_PC_ARDUINO,
    &Messages::TEMPERATURE_READING,
    &Messages::FORCE_EMERGENCY_STOP,
    &Messages::EMERGENCY_ALARM,
    &Messages::THERMOSENSOR_ERROR,
    &Messages::WATCHDOG_SR_LATCH_FROZEN,
    &Messages::OVEN_OVERHEAT
  };

  static constexpr size_t NUM_MESSAGES = sizeof(messagePointers) / sizeof(messagePointers[0]); //size calculations are platform independent unlike integers, size_t bridges the gap
};


//Timeout durations for sending any outgoing messages to avoid overcrowding the serial buffer
namespace MessageTimeouts {
  // Instantiate Timer for each message with specific timeout durations
  //What about PING_ARDUINO_PC_TIMER? It has no timeout since it responds once on ping from PC.
  //FORCE_EMERGENCY_STOP is sent from Python on the computer, so the timeout is handled there
  
  //All in milliseconds
  static Timer TEMPERATURE_READING(1500, true);
  static Timer EMERGENCY_ALARM(1000, true); //Milliseconds
  static Timer THERMOSENSOR_ERROR(1000, true); //Milliseconds
  static Timer WATCHDOG_SR_LATCH_FROZEN(1000, true); //Milliseconds
  static Timer OVEN_OVERHEAT(1000, true); //Milliseconds
}

class SerialConnectionManager{

  public:
    bool serialConnection = false; //While serialConnection is known connection at the moment...
    // bool serialLost = false; //...serialLoss indicates going from connected to disconnected.

    void begin(unsigned long baudRate = 9600){
      Serial.begin(baudRate);
    }

    static SerialConnectionManager& getInstance() {
      static SerialConnectionManager instance; // Created on first use
      return instance;
    }

    SerialConnectionManager(const SerialConnectionManager&) = delete;
    SerialConnectionManager& operator=(const SerialConnectionManager&) = delete;

  private:
    SerialConnectionManager() {
    }

    // Private destructor (optional)
    ~SerialConnectionManager() {
    }
};


class StringMessageHandler
{
//Class is a singleton, forcing you to have a single reference point for it. It makes the code tidier and more resource efficient.

  public:
    // Access the Singleton instance (singleton implementation, I just copy-paste)
    static StringMessageHandler& getInstance() {
        static StringMessageHandler instance; // Created on first use
        return instance;
    }

    // Delete copy constructor and assignment operator to prevent copies (singleton implementation, I just copy-paste)
    StringMessageHandler(const StringMessageHandler&) = delete;
    StringMessageHandler& operator=(const StringMessageHandler&) = delete;

    // Builds a message in the format "category,message,value,timestamp\n"
    String buildMessage(const MessageStruct& message, float value = NAN, const String &timestamp = "") const //Null substitute in timestamp for Python receival, C++ is lacking
    {
      String buildtMessage = "";
      // Append category
      buildtMessage += String(message.category);
      buildtMessage += messagePartSeparator;
      // Append message
      buildtMessage += String(message.message);
      buildtMessage += messagePartSeparator;
      // Append value with two decimal places or "NaN" if not a number
      if (isnan(value)) {
          buildtMessage += "NaN";
      } else {
          buildtMessage += String(value, 2); // 2 decimal places
      }
      buildtMessage += messagePartSeparator;
      // Append timestamp
      if (timestamp == ""){
        buildtMessage += "NaN";
      } else {
        buildtMessage += timestamp;
      }
      return buildtMessage;
    }

    ParsedMessageStruct parseMessage (const String &message){ //Deconstructs a serial message in the format category,message,value,timestamp\n(\n is optional)
      
      ParsedMessageStruct parsed;
      
      if(message != negativeOneSentinel)
      {
        //Protocol format for message is "category,message,value,timestamp", so three commas
        int commaCount = 0;
        for (int i = 0; i < message.length(); i++) {
          if (message.charAt(i) == messagePartSeparator) {
            commaCount++;
          }
        }
        
        // If comma count isn't exactly 3, it's invalid
        if (commaCount != 3) {
          // Early return with isValid = false
          parsed.message = nullptr;
          parsed.value = NAN;
          parsed.timestamp = negativeOneSentinel;
    
          return parsed;
        }
        
        //Find comma positions for message separation
        int commaIndex = 0;
        int commaIndexes[3];
        int commaIndexesLength = sizeof(commaIndexes)/sizeof(*commaIndexes);
        for(int i = 0; i < commaIndexesLength; i++){
          commaIndex = message.indexOf(messagePartSeparator, commaIndex + 1); //Find the next comma starting from nothing or the previous one
          //Test necessity
          if (commaIndex >= 0 && commaIndex < message.length()){ //Avoid out of bounds
            commaIndexes[i] = commaIndex;
          }
          else{
            // If this ever fails, it's invalid
            parsed.message = nullptr;
            parsed.value = NAN;
            parsed.timestamp = negativeOneSentinel;
            parsed.isValid = false;
            return parsed;
          }
        }
        
        char messageCategory = message.charAt(commaIndexes[0] - 1); //First digit before the first comma
        char messageMessage = message.charAt(commaIndexes[1] - 1); //First digit before the second comma
        MessageStruct *messageStruct = findMessage(messageCategory, messageMessage); //Gets the correct message type using category and message
        if(messageStruct != nullptr){
          parsed.message = messageStruct;
        }
        else{
          // Invalid because we didn't find the message
          parsed.message = nullptr;
          parsed.value = NAN;
          parsed.timestamp = negativeOneSentinel;
          parsed.isValid = false;
          return parsed;
        }
        
        float messageValue;
        String messageValueString = message.substring(commaIndexes[1] + 1, commaIndexes[2]);
        if(messageValueString != "NaN"){
          messageValue = atof(messageValueString.c_str()); //String to float
          parsed.value = messageValue;
        }
        else{
          parsed.value = NAN;
        }
        
        String messageTimestampString = message.substring(commaIndexes[2] + 1);
        if(messageTimestampString != "NaN"){
          // Check if timestamp format is valid
          if(isTimestampFormatValid(messageTimestampString)){
            parsed.timestamp = messageTimestampString;
          }
          else{
            // Invalid timestamp
            parsed.message = nullptr;
            parsed.value = NAN;
            parsed.timestamp = negativeOneSentinel;
            parsed.isValid = false;
            return parsed;
          }
        }
      }
      else
      {
        //In this case, there's no message
        parsed.message = nullptr;
        parsed.value = NAN;
        parsed.timestamp = negativeOneSentinel;
        parsed.isValid = false;
        return parsed;
      }
      
      parsed.isValid = true;
      return parsed;
    }

  private:
    // Private constructor to prevent external instantiation
    StringMessageHandler() { //(singleton implementation, I just copy-paste)
    }

    // Private destructor (optional)
    ~StringMessageHandler() { //(singleton implementation, I just copy-paste)
    }

    char messagePartSeparator = ',';

    // Verify timestamp format "%m/%d/%Y %H:%M:%S"
    // Checks if the string has 19 characters with /, space, and colons, and numbers. It does NOT check if the day and month is correct, but that's not necessary.
    bool isTimestampFormatValid(const String &ts) const
    {
      int len = ts.length();

      // Minimum length is 13: "M/D/YYYY H:M:S"
      // Maximum length is 19: "MM/DD/YYYY HH:MM:SS"
      if(len < 13 || len > 19) return false;

      // Find the positions of the delimiters
      int firstSlash = ts.indexOf('/');
      if(firstSlash == -1 || firstSlash < 1 || firstSlash > 2) return false;

      int secondSlash = ts.indexOf('/', firstSlash + 1);
      if(secondSlash == -1 || secondSlash < firstSlash + 2 || secondSlash > firstSlash + 3) return false;

      int space = ts.indexOf(' ', secondSlash + 1);
      if(space == -1 || space < secondSlash + 5 || space > secondSlash + 6) return false;

      int firstColon = ts.indexOf(':', space + 1);
      if(firstColon == -1 || firstColon < space + 2 || firstColon > space + 3) return false;

      int secondColon = ts.indexOf(':', firstColon + 1);
      if(secondColon == -1 || secondColon < firstColon + 2 || secondColon > firstColon + 3) return false;

      // Check if all other characters are digits
      for(int i = 0; i < len; i++){
          if(i == firstSlash || i == secondSlash || i == space || i == firstColon || i == secondColon) {
              // skip these since they're '/', '/', ' ', ':', ':'
              continue;
          }
          if(!isDigit(ts.charAt(i))) {
              return false;
          }
      }

      return true;
    }

    const MessageStruct* findMessage(char category, char message){
      for(size_t i = 0; i < Messages::NUM_MESSAGES; ++i){
        if(category == Messages::messagePointers[i]->category && message == Messages::messagePointers[i]->message){
          return Messages::messagePointers[i];
        }
      }
      return nullptr; //Message not there
    }

};

class SerialMessageHandler
{

  public:
    static SerialMessageHandler& getInstance() {
        static SerialMessageHandler instance;
        return instance;
    }

    SerialMessageHandler(const SerialMessageHandler&) = delete;
    SerialMessageHandler& operator=(const SerialMessageHandler&) = delete;

    void passMessage(const MessageStruct& message, float value = NAN, const String &timestamp = "") const
    {
      String outgoingMessage = stringMessageHandler.buildMessage(message, value, timestamp);
      sendMessage(outgoingMessage);
    }

    ParsedMessageStruct getMessage()
    {
      String incomingMessage = receiveMessage();
      ParsedMessageStruct parsed = stringMessageHandler.parseMessage(incomingMessage);
      return parsed;
    }

    // Sends the message via Serial
    void sendMessage(const String& message) const
    {
      Serial.println(message);
    }

    // Receives a message from Serial until a newline character is encountered
    String receiveMessage() const
    {
      if (Serial.available())
      {
          return Serial.readStringUntil('\n');
      }
      else
      {
          return negativeOneSentinel;
      }
    }


  private:
    // Private constructor to prevent external instantiation more than once
    SerialMessageHandler() {
    }

    // Private destructor (optional)
    ~SerialMessageHandler() {
    }

    StringMessageHandler &stringMessageHandler = StringMessageHandler::getInstance();

};

class SerialHandshakeHandler
{
  //If the whole procedure with both handshake and detection for going from serial contact to serial loss is implemented, the serial connection manager would need the handshake handler as a dependency and not opposite.
  //The whole thing would happen in a handleSerialConnection method in the serial connectio manager, using the handshake handler
  //This class will need to be moved to below all the other serial classes.

  public:
    // Static method to access the single instance
    static SerialHandshakeHandler& getInstance() {
        static SerialHandshakeHandler instance;
        return instance;
    }

    void handleHandshake(const ParsedMessageStruct &message) {
      if(message.message == &Messages::PING_PC_ARDUINO)
      {
        serialConnectionManager.serialConnection = true;
        pingReceivedTimer.resetTimer();
        serialMessageHandler.passMessage(Messages::PING_ARDUINO_PC);
      }
      else
      {
        if(pingReceivedTimer.timedOut())
        {
          serialConnectionManager.serialConnection = false;
        }
      }
    }

    // Delete copy constructor and assignment operator to avoid misuse
    SerialHandshakeHandler(const SerialHandshakeHandler&) = delete;
    SerialHandshakeHandler& operator=(const SerialHandshakeHandler&) = delete;

  private:
    unsigned long pingReceivedTimeout = 15000;
    Timer pingReceivedTimer;

    // Private constructor to prevent instantiation
    SerialHandshakeHandler()
      : pingReceivedTimer(pingReceivedTimeout)
    {}

    ~SerialHandshakeHandler() = default;

    SerialConnectionManager &serialConnectionManager = SerialConnectionManager::getInstance();
    SerialMessageHandler &serialMessageHandler = SerialMessageHandler::getInstance();
};


//Oven heating simulation, not important for the system, and can optionally be ignored
float tempSimulation(bool heatingOn, float currentTemp, SimulationData &simulationData) {

  if(heatingOn)
  {
    simulationData.heatingOn = true;
  }
  else
  {
    simulationData.heatingOn = false;
  }

  //Finding how long oven has been in current state
  if(simulationData.heatingOn != simulationData.lastHeatingState)
  {
    simulationData.stateTime = 0;
  }
  simulationData.lastHeatingState = simulationData.heatingOn;
  simulationData.stateTime += simulationData.timeStep;

    //This simulation is very inaccurate
  //I just follow the math more or less blindly

  //Formula:
  //e: The natural logarithm constant, 2.718
  //Tgain: Total heat gain
  //Tloss: Total heat loss
  //Tnew: New temperature

  //If oven is on:
    //Pactual(t) = P * (1 - e^(-(t / Ton)))
  //If oven is off:
    //Pactual(t) = P * e^(-(t / Toff)))
    
  //Tgain: (Pactual(t) * deltat) / C

  //Tloss = (h * (Tcurrent - Tenv) * deltat) / C

  //Tnew: Tcurrent + Tgain - Tloss

  const float e = 2.718;

  float Pactual;
  float Tgain;
  float Tloss;
  float Tnew;

  //Full calculation, hit it!
  if(simulationData.heatingOn)
  {
    Pactual = simulationData.wattage * (1 - pow(e, -(simulationData.stateTime / simulationData.elementBuildupTime)));
  }
  else
  {
    //Pactual(t) = P * e^(-(t / Toff)))
    Pactual = simulationData.wattage * pow(e, -(simulationData.stateTime / simulationData.elementCooldownTime));
  }
  Tgain = (Pactual * simulationData.timeStep) / simulationData.heatCapacity;
  Tloss = (simulationData.lossCoefficient * (simulationData.currentTemp - simulationData.ambientTemperature) * simulationData.timeStep / simulationData.heatCapacity);
  Tnew = simulationData.currentTemp + Tgain - Tloss;
  simulationData.currentTemp = Tnew;

  return simulationData.currentTemp;
}

//User settings
int oven1ControllPin = 7; //Controll pin for the oven SSR.
float oven1AbsoluteMax = 200;

unsigned long externalPwmHighPeriod = 2000; //Maximum time the external PWM signal should be high. Slightly above actual intervals.
int srLatchResetPin = 4;
int srLatchOutputPin = 6;

bool useOven1TemperatureSensor = true;
int oven1TemperatureSensorCSPin = SS; //CS = Chip Select. Does not need to be correct if not using temperature sensor.

//Dev settings
bool heatingOverride = false; //Oven might be connected and on, but you don't want the Arduino to controll it
bool useHeatingSimulation = true; //You don't always have an oven





bool generalEmergency = false; //Critical error. Oven controll SSR will be off as long as this is on.

//Object instance pointer (*) ready to be initialiozed and set up later
Oven *oven1 = nullptr;
SrLatchFrozenWatchdog *oven1SrLatchFrozenWatchdog = nullptr;

//Object instance pointers (*) ready to be initialiozed andset up later
Max31856Sensor *oven1TemperatureSensor = nullptr;
OvenOverheatWatchdog *oven1OverheatWatchdog = nullptr;

SerialMessageHandler &serialMessageHandler = SerialMessageHandler::getInstance();
SerialConnectionManager &serialConnectionManager = SerialConnectionManager::getInstance();
SerialHandshakeHandler &serialHandshakeHandler = SerialHandshakeHandler::getInstance();


void setup() {

  //Oven SSR pin (int), absolute max temperature (float), goal temperature for oven (float), force oven to stay off? (bool), use the heating simulation? (bool)
  oven1 = new Oven(oven1ControllPin, oven1AbsoluteMax);
  oven1SrLatchFrozenWatchdog = new SrLatchFrozenWatchdog(externalPwmHighPeriod, srLatchResetPin, srLatchOutputPin);
  oven1SrLatchFrozenWatchdog->begin(); // -> is used instead of . for pointers.

  if(useOven1TemperatureSensor)
  {
    //max31856 CS designated pin for Chip Select (int), optional thermocouple type (int)
    oven1TemperatureSensor = new Max31856Sensor(oven1TemperatureSensorCSPin);
    oven1TemperatureSensor->begin();
    oven1OverheatWatchdog = new OvenOverheatWatchdog(oven1AbsoluteMax);
  }
  serialConnectionManager.begin();
  oven1->begin();
}

void loop() {
  ParsedMessageStruct message = serialMessageHandler.getMessage();

  serialHandshakeHandler.handleHandshake(message);

  if(useOven1TemperatureSensor)
  {
    oven1->currentTemp = oven1TemperatureSensor->readTemperature();
    if(oven1TemperatureSensor->temperatureSensorFailAlarm)
    {
      generalEmergency = true;
    }

    if(serialConnectionManager.serialConnection)
    {
      if(MessageTimeouts::TEMPERATURE_READING.timedOut())
      {
        serialMessageHandler.passMessage(Messages::TEMPERATURE_READING, oven1->currentTemp);
        MessageTimeouts::TEMPERATURE_READING.resetTimer();
      }
    }
  }

  if(useOven1TemperatureSensor && !oven1OverheatWatchdog->ovenOverheat)
  {
    oven1OverheatWatchdog->checkOverheat(oven1->currentTemp, oven1TemperatureSensor->temperatureSensorFailAlarm);
  }
  if(!oven1SrLatchFrozenWatchdog->srLatchFrozen)
  {
    oven1SrLatchFrozenWatchdog->checkSrLatchFrozen();
  }
  if(oven1OverheatWatchdog->ovenOverheat || oven1SrLatchFrozenWatchdog->srLatchFrozen)
  {
    generalEmergency = true;
  }
  if(generalEmergency)
  {
    oven1->turnOvenControllPinOff();
  }
  else
  {
    oven1->turnOvenControllPinOn();
  }

  if(serialConnectionManager.serialConnection)
  {
    sendAlarmMessages(
      generalEmergency,
      oven1TemperatureSensor->temperatureSensorFailAlarm,
      oven1OverheatWatchdog->ovenOverheat,
      oven1SrLatchFrozenWatchdog->srLatchFrozen
    );
  }

  if(message.message == &Messages::FORCE_EMERGENCY_SHUTDOWN)
  {
    generealEmergency = true;
  }
}

void sendAlarmMessages(bool generalEmergency, bool temperatureSensorFailAlarm, bool ovenOverheat, bool srLatchFrozen)
{
  if(generalEmergency)
  {
      if(MessageTimeouts::EMERGENCY_ALARM.timedOut())
      {
        serialMessageHandler.passMessage(Messages::EMERGENCY_ALARM);
        MessageTimeouts::EMERGENCY_ALARM.resetTimer();
      }
  }
  if(oven1TemperatureSensor->temperatureSensorFailAlarm)
  {
    if(MessageTimeouts::THERMOSENSOR_ERROR.timedOut())
      {
        serialMessageHandler.passMessage(Messages::THERMOSENSOR_ERROR);
        MessageTimeouts::THERMOSENSOR_ERROR.resetTimer();
      }
  }
  if(oven1OverheatWatchdog->ovenOverheat)
  {
    if(MessageTimeouts::OVEN_OVERHEAT.timedOut())
      {
        serialMessageHandler.passMessage(Messages::OVEN_OVERHEAT);
        MessageTimeouts::OVEN_OVERHEAT.resetTimer();
      }
  }
  if(oven1SrLatchFrozenWatchdog->srLatchFrozen)
  {
    if(MessageTimeouts::WATCHDOG_SR_LATCH_FROZEN.timedOut())
      {
        serialMessageHandler.passMessage(Messages::WATCHDOG_SR_LATCH_FROZEN);
        MessageTimeouts::WATCHDOG_SR_LATCH_FROZEN.resetTimer();
      }
  }
}