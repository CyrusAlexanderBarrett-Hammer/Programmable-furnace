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
  
  public:
    // Constructor with an additional parameter to start as timed out
    Timer(unsigned long _durationMs = 0, bool _startTimedOut = false)
      : durationMs(_durationMs)
    {
        if (_startTimedOut) {
            // timedOut() will return true immediately
            startTime = millis() - durationMs;
        } else {
            startTimer(); // Start the timer normally
        }
    }

    void startTimer()
    {
      startTime = millis();
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
            : maxCS(_maxCS), recheckReadingTimer(sensorMeasurementTime, true) {} //Initializing the instance in the constructor

    void resetThermocouple(){
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

          bool faultDetected = (!isnan(temperatureReference) && temperatureNew == temperatureReference) || isnan(temperatureNew);

          if (faultDetected)
          {
              resetThermocouple();

              if (overrideUpdateFail)
              {
                  overrideUpdateFail = false;
                  return FailStates::Unknown; // Instead of returning true, return a FailState
              }

              overrideUpdateFail = true;
              failCount++;
          }
          else
          {
              failCount = 0;
          }

          temperatureReference = temperatureNew;
      }

      if (failCount >= maxFailAttempts)
      {
          return FailStates::Unsuccessful; // Failed permanently
      }
      else if (failCount > 0)
      {
          return FailStates::Unknown; // We do not yet know if the sensor failed permanently
      }
      else
      {
          return FailStates::Successful; // No fail yet
      }
    }

};

class OvenOverheatWatchdog
{
  private:
    float maxTemp;
  
  public:
    bool ovenOverheat;

    OvenOverheatWatchdog(float _maxTemp)
        : maxTemp(_maxTemp)
        {}

    void check_overheat(float currentTemperature, bool temperatureSensorFailAlarm)
    {
      //If temperatureSensorFailAlarm is on, the high temperature of 2023 degrees (Labview sensor fail standard) is because of thermocouple fail, not overheat
      //We can't know if there's overheat if the sensor isn't working anyway, and no thermocouples can measure 2023 degrees or higher
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
    unsigned long srLatchHighDurationMs; //Maximum tolerated high duration
    int srLatchResetPin;
    int srLatchOutputPin;
  
    Timer srLatchHighTimer;
  
    bool resetSrLatch = true;
  
    bool srLatchOutputStatus;
  
    int failCount = 0;
    int maxFailAttempts = 3;

  public:
    bool srLatchFrozen = false;

    SrLatchFrozenWatchdog(unsigned long _srLatchHighDurationMs, int _srLatchResetPin, int _srLatchOutputPin)
          : srLatchHighDurationMs(_srLatchHighDurationMs), srLatchResetPin(_srLatchResetPin), srLatchOutputPin(_srLatchOutputPin), srLatchHighTimer(_srLatchHighDurationMs)
        {}

    void checkSrLatchFrozen()
    {
      if(resetSrLatch)
      {
        digitalWrite(srLatchResetPin, HIGH); //Latch will go to low, and will go to high again if it's set pin is set to high (pulsed) by external signal
      }

      //Pulsed high, everything in order
      srLatchOutputStatus = digitalRead(srLatchOutputPin);
      if(srLatchOutputStatus == true)
      {
        srLatchHighTimer.resetTimer();
        resetSrLatch = true;
        return;
      }

      if(!srLatchHighTimer.timedOut())
      {
        //Keep giving a chance ready for next time
        resetSrLatch = false;
        return;
      }

      //At this stage, the SR latch has not gone to high
      resetSrLatch = true;
      failCount += 1;

      if(!failCount >= maxFailAttempts)
      {
        return;
      }
      else
      {
        //Watchdog barks
        srLatchFrozen = true;
      }
    }

};

class Max31856Sensor
{
  //args: max31856 CS designated pin for Chip Select (int), optional thermocouple type (int)

  const Adafruit_MAX31856 maxSensor;

  const uint8_t tcType; //Thermocouple type, see Max31856 library examples

  bool temperatureSensorFailAlarm = false;

  Max31856FaultHandler max31856FaultHandler;

  Oven(uint8_t _maxCS, uint8_t _tcType = 3) //Constructor for setting values
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
      currentTemp = 2023; //Labview standard thermocouple error temperature, as per request from Terje
    }
  }

  void readTemperature()
  {
    if (temperatureSensorFailAlarm == false)
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

      //If unknown, don't update
    }
  }


  //If setup configurations are implemented to be set from Python on PC, make methods here to change the values like max temperature, tc type etc (see "signals" in the documentation)
}

//Oven status and settings
struct Oven
{
  //args: heating element oven controll pin (int), goal temoperature for furnace (float), absolute max temperature for furnace (float) force oven to stay off? (bool), use the heating simulation? (bool)

  //Simulation, heating override, etc adjustable for each individual oven if relevant
  
  const int heatingElementPin; //Oven controll pin

  bool heatingOn;
  float currentTemp;

  //Settings
  const bool heatingOverride; //Force actual heater to be off? Won't effect anything else.
  const bool useHeatingSimulation; //Ignore thermo sensor and fake temperature from controlled heating algorithm
  float tempGoal; //Degrees
  float absoluteMaxTemp;


  Oven(int _heatingElementPin, float _tempGoal, float _absoluteMaxTemp, bool _heatingOverride = false, bool _useHeatingSimulation = false) //Constructor for setting values
          : heatingElementPin(_heatingElementPin), 
            tempGoal(_tempGoal),
            absoluteMaxTemp(_absoluteMaxTemp), 
            heatingOverride(_heatingOverride), 
            useHeatingSimulation(_useHeatingSimulation)
          {}

  void begin()
  {
    pinMode(heatingElement, OUTPUT);
    digitalWrite(heatingElement, LOW);
  }

  //If setup configurations are implemented to be set from Python on PC, make methods here to change the values like pin number, max temperature, temperature goal, etc (see "signals" in the documentation)
};

//Simulation status and settings, not important for the system, and can optionally be ignored
struct SimulationData
{
  //Args: All are optional. Time step (float), wattage (float), element heat buildup time (float), element heat cooldown time (float), oven heat capacity (float), heat loss in oven versus room temperature (float), room temperature (float), time step (float)

  //inputs
  float currentTemp = 23; //Tcurrent, current temperature (currentTemp)
  bool heatingOn; //heatingOn is not used in the equation directly
  bool lastHeatingState; //Used to check state changes

  float stateTime; //t, time oven has been in current on/off state

  //Simulation parameters
  const float timeStep; //Deltat, simulation time step in seconds

  const float elementBuildupTime; //Ton, time element takes to reach full heat production in seconds
  const float elementCooldownTime; //Toff, time element takes to cool off again in seconds
  const float actualWattage; //Pactual(t) element heat production wattage per now (NOT NEEDED)
  const float wattage; //P, element power wattage rating CHECK
  const float heatCapacity; //C, furnace heat capacity in joules per degree celsius
  const float lossCoefficient; //h, heat loss to environment per degree difference
  const float ambientTemperature; //Tenv, the room temperature

  SimulationData(float _timeStep = 0.0001, float _wattage = 3000, float _elementBuildupTime = 130, float _elementCooldownTime = 20, float _heatCapacity = 1500, float _lossCoefficient = 0.02, float _ambientTemperature = 23)
                : wattage(_wattage), elementBuildupTime(_elementBuildupTime), elementCooldownTime(_elementCooldownTime), heatCapacity(_heatCapacity), lossCoefficient(_lossCoefficient), ambientTemperature(_ambientTemperature), timeStep(_timeStep){}
};

//Sorry about these being global, they should all be in SerialMessageHandler, StringMessageHandler, or in header files
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
};

namespace Messages{
  //Pre-written instructions
  //Categories encforce structure.
  static const MessageStruct PING_ARDUINO_PC = {'1', '2'}; //Sent to PC
  static const MessageStruct PING_PC_ARDUINO = {'1', '1'}; //Received from PC

  static const MessageStruct TEMPERATURE_READING = {'2', '1'}; //Sent to PC

  static const MessageStruct FORCE_EMERGENCY_STOP = {'4', '0'}; //Received from PC

  static const MessageStruct EMERGENCY_ALARM = {'9', '0'}; //Sent to PC
  static const MessageStruct THERMOCOUPLE_ERROR = {'9', '1'}; //Sent to PC
  static const MessageStruct WATCHDOG_SR_LATCH_FROZEN_HIGH = {'9', '2'}; //Sent to PC. The furnace heating signal is stuck to high.
  static const MessageStruct FURNACE_OVERHEAT = {'2', '1'}; //Sent to PC

  //Allows iteration by using pointers to Messages' memory addresses, unlike iterating over their structs directly
  const MessageStruct* messagePointers[] = {
    &Messages::PING_ARDUINO_PC,
    &Messages::PING_PC_ARDUINO,
    &Messages::TEMPERATURE_READING,
    &Messages::FORCE_EMERGENCY_STOP,
    &Messages::EMERGENCY_ALARM,
    &Messages::THERMOCOUPLE_ERROR,
    &Messages::WATCHDOG_SR_LATCH_FROZEN_HIGH,
    &Messages::FURNACE_OVERHEAT
  };

  static constexpr size_t NUM_MESSAGES = sizeof(messagePointers) / sizeof(messagePointers[0]); //size calculations are platform independent unlike integers, size_t bridges the gap
};


//Timeout durations for sending any outgoing messages to avoid overcrowding the serial buffer.
namespace MessageTimeouts {
  // Instantiate Timer for each message with specific timeout durations
  //What about PING_ARDUINO_PC_TIMER? It has no timeout since it responds once on ping from PC.
  //FORCE_EMERGENCY_STOP is sent from Python on the computer, so the timeout is handled there
  static Timer TEMPERATURE_READING(1500, true); //Milliseconds
  static Timer EMERGENCY_ALARM(1000, true); //Milliseconds
  static Timer THERMOCOUPLE_ERROR(1000, true); //Milliseconds
  static Timer WATCHDOG_SR_LATCH_FROZEN_HIGH(1000, true); //Milliseconds
  static Timer FURNACE_OVERHEAT(1000, true); //Milliseconds
}

class SerialHandshakeHandler
{
  private:
    unsigned long pingReceivedTimeout = 15 * 1000;
    Timer pingReceivedTimer;

  public:
    SerialHandshakeHandler()
      : pingReceivedTimer(pingReceivedTimeout)
    {}

    void handleHandshake(const ParsedMessageStruct *message) {
      if(message->message == &Messages::PING_PC_ARDUINO)
      {
        serialConnectionManager.serialConnection = true;
        pingReceivedTimer.resetTimer()
        serialMessageHandler.passMessage(Messages::PING_ARDUINO_PC);
      }
      else
      {
        if(pingReceivedTimer.timedOut())
        {
          serialConnectionManager.serialConnection = true;
        }
      }
    }

    // Delete copy constructor and assignment operator to avoid misuse
    SerialHandshakeHandler(const SerialHandshakeHandler&) = delete;
    SerialHandshakeHandler& operator=(const SerialHandshakeHandler&) = delete;

  private:
    // Private constructor to prevent instantiation
    SerialHandshakeHandler() = default;
    ~SerialHandshakeHandler() = default;

    SerialConnectionManager &serialConnectionManager::getInstance();
    SerialMessageHandler &serialMessageHandler::getInstance();
};

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
      if(message != negativeOneSentinel){
        int commaIndex = 0;

        int commaIndexes[3];
        int commaIndexesLength = sizeof(commaIndexes)/sizeof(*commaIndexes);

        for(int i = 0; i < commaIndexesLength; i++){
          commaIndex = message.indexOf(messagePartSeparator, commaIndex + 1);
          if (commaIndex >= 0 && commaIndex < message.length()){ //Avoid out of bounds
            commaIndexes[i] = commaIndex;
          }
          else{
            int dummyVariable = 0; //Add some error handling here.
          }
        }

        char messageCategory = message.charAt(commaIndexes[0] - 1);
        char messageMessage = message.charAt(commaIndexes[1] - 1);
        MessageStruct *messageStruct = findMessage(messageCategory, messageMessage);
        if(messageStruct != nullptr){
          parsed.message = messageStruct;
        }
        else{
          parsed.message = nullptr;
          int dummyVariable = 0; //Add some error handling here.
        }

        float messageValue;
        String messageValueString = message.substring(commaIndexes[1] + 1, commaIndexes[2]);
        if(messageValueString != "NaN"){
          messageValue = atof(messageValueString.c_str());
          parsed.value = messageValue;
        }
        else{
          parsed.value = NAN;
        }

        String messageTimestamp;
        String messageTimestampString = message.substring(commaIndexes[2] + 1);
        if(messageTimestampString != "NaN"){
          messageTimestamp = messageTimestampString;
          parsed.timestamp = messageTimestamp;
        }
        else{
          parsed.timestamp = negativeOneSentinel;
        }

      }
      else{
        parsed.message = nullptr;
        parsed.value = NAN;
        parsed.timestamp = negativeOneSentinel;
        int dummyVariable = 0; //Add some error handling here
      }
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
        static SerialMessageHandler instance; // Created on first use
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


//Furnace heating simulation, not important for the system, and can optionally be ignored
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
//max31856 CS designated pin for Chip Select (int), optional thermocouple type (int)
Max31856Sensor temperatureSensor1(10);

//heating element oven controll pin (int), goal temperature for furnace (float), absolute max temperature (float), force oven to stay off? (bool), use the heating simulation? (bool)
Oven oven1(5, 30, 50, false, false);

//All are optional. Time step (float), wattage (float), element heat buildup time (float), element heat cooldown time (float), oven heat capacity (float), heat loss in oven versus room temperature (float), room temperature (float), time step (float)
SimulationData oven1SimulationData (devDelay / 1000);

SerialMessageHandler &serialMessageHandler = SerialMessageHandler::getInstance();
SerialConnectionManager &serialConnectionManager = SerialConnectionManager::getInstance();


unsigned long currentTime; //Put in new time keeping struct

//Goes in the handshake class
//Time between Python ping
unsigned long serialPingTime = 62000; //60 seconds, with 2 seconds margin
unsigned long lastSerialPingTime = NAN; //Ping might never happen
unsigned long deltaSerialPingTime = NAN; //Ping might never happen
//Time between ping and expected response
unsigned long maxSerialPingReplyTime = 5000;
unsigned long lastSerialPingReplyTime;
unsigned long deltaSerialPingReplyTime;


void setup() {
  serialConnectionManager.begin();
  oven1.begin();
  pinMode(3, OUTPUT);
}

void loop() {

  currentTime = millis(); //Put in a getTime method, in a new timekeeping struct

  ParsedMessageStruct message = serialMessageHandler.getMessage();

  if(MessageTimeouts::THERMOCOUPLE_ERROR.timedOut())
  {
    serialMessageHandler.passMessage(Messages::THERMOCOUPLE_ERROR);
    MessageTimeouts::THERMOCOUPLE_ERROR.resetTimer();
  }
  if(MessageTimeouts::TEMPERATURE_READING.timedOut())
  {
    serialMessageHandler.passMessage(Messages::TEMPERATURE_READING);
    MessageTimeouts::TEMPERATURE_READING.resetTimer();
  }

  // if(message->message == &Messages::PING_PC_ARDUINO){
  //   digitalWrite(3, HIGH);
  // }


  // //Get all of this, including whatever in the global scope they use, into their structs or classes, in batch
  // if(SerialHandshakeHandler::checkHandshake(message)){
    serialConnectionManager.serialLost = false;
  //   serialMessageHandler.passMessage(Messages::PING_ARDUINO_PC);
  //   lastSerialPingTime = currentTime;
  // }

  
  // if(!isnan(lastSerialPingTime)){
  //   deltaSerialPingTime = currentTime - lastSerialPingTime;
  // }
  // if(SerialConnectionManager.serialLoss = false && deltaSerialPingTime >= serialPingTime){
  //   serialConnectionManager.serialLoss = SerialConnectionManager.serialLoss = true;
  // }
  

  // delay(1000);
  // // put your main code here, to run repeatedly:
  // delay(devDelay);

  if (oven1.useHeatingSimulation) {
    //Why isn't the oven1SimulationData instanciated inside the oven1 object like everything else!!! It could always be changed again to be passed as a parameter if it uses too many resources.
    oven1.currentTemp = tempSimulation(oven1.heatingOn, oven1.currentTemp, oven1SimulationData);
  } else {
    if(!oven1.temperatureSensorFailAlarm){
      oven1.currentTemp = temperatureSensor1.read_temperature();
    }
  }

  if (oven1.currentTemp <= oven1.tempGoal) {
    oven1.heatingOn = true;
  } else {
    oven1.heatingOn = false;
  }

  if (oven1.heatingOverride) {
    digitalWrite(oven1.heatingElement, LOW);
  }
  else
  {
    if (oven1.heatingOn) {
      digitalWrite(oven1.heatingElement, HIGH);
    }
    else
    {
      digitalWrite(oven1.heatingElement, LOW);
    }
  }

  serialMessageHandler.passMessage(Messages::TEMPERATURE_READING, oven1.currentTemp);
  Serial.println(temperatureSensor1.temperatureSensorFailAlarm);
  Serial.println("Der!");

  // Serial.println(oven1.currentTemp);
  // Serial.println(oven1.heatingOn);
  // // // digitalWrite(oven1.heatingElement, HIGH);
  // // // delay(2000);
  // // // digitalWrite(oven1.heatingElement, LOW);
  // // // delay(2000);
  // Serial.println("01,02,NaN,NaN");
}