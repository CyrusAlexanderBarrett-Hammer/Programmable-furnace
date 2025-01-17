//TODO: Make an instantiable struct object for time and date time stamps.

#include "String.h"

#include <Adafruit_MAX31856.h>
#include <SPI.h>;

const String negativeOneSentinel = "-1"; //Nan equivalent for when NaN can't be used, use well; universal

float devDelay = 100; //A stalling delay for development, in milliseconds

//Oven status and settings
typedef struct OvenData
{
  //args: max31856 CS designated pin for Chip Select (int), heating element oven controll pin (int), force oven to stay off? (bool), use the heating simulation? (bool), optional thermocouple type (int)

  //Simulation, heating override, etc adjustable for each individual oven

  const int heatingElement; //Oven controll pin

  const Adafruit_MAX31856 maxSensor;

  const uint8_t tcType; //Thermocouple type, see Max31856 library examples

  bool heatingOn;
  float currentTemp;

  //Settings
  const bool heatingOverride = true; //Force actual heater to be off? Won't effect anything else.
  const bool useHeatingSimulation = true; //Ignore thermo sensor and fake temperature from controlled heating algorithm
  float tempGoal = 30; //Degrees


  OvenData(uint8_t _maxCS, int _heatingElement, bool _heatingOverride, bool _useHeatingSimulation, uint8_t _tcType = 3) //Constructor for setting values
          : maxSensor(_maxCS), heatingElement(_heatingElement), heatingOverride(_heatingOverride), useHeatingSimulation(_useHeatingSimulation), tcType(_tcType) {} //_maxCS tself is not set here, as it's an instanciation

  void begin()
  {
    maxSensor.setThermocoupleType(tcType);
    maxSensor.begin();
    pinMode(heatingElement, OUTPUT);
    digitalWrite(heatingElement, LOW); //Keep oven securely off until 
  }
};

//Simulation status and settings, not important for the system, and can optionally be ignored
typedef struct SimulationData
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
typedef struct MessageStruct
{
  char category;
  char message;
};

typedef struct ParsedMessageStruct
{
  //Category and message combines into instruction with MessageStruct
  MessageStruct *message;
  float value;
  String timestamp;
};
ParsedMessageStruct parsedMessageStruct;

namespace Messages{
  //Pre-written instructions
  static const MessageStruct PING_SENDING = {'1', '2'};
  static const MessageStruct PING_RECEIVING = {'1', '1'};

  //Allows iteration by using pointers to memory address, unlike structs
  const MessageStruct* messagePointers[] = {
    &Messages::PING_SENDING,
    &Messages::PING_RECEIVING
  };

  static constexpr size_t NUM_MESSAGES = sizeof(messagePointers) / sizeof(messagePointers[0]); //size calculations are platform independent unlike integers, size_t bridges the gap
};

class SerialHandshakeHandler
{
  public:
    static bool checkHandshake(const ParsedMessageStruct *message) {
      if(message->message == &Messages::PING_RECEIVING)
        return true;
      else {
        return false;
      }
    }

    // Delete copy constructor and assignment operator to avoid misuse
    SerialHandshakeHandler(const SerialHandshakeHandler&) = delete;
    SerialHandshakeHandler& operator=(const SerialHandshakeHandler&) = delete;

  private:
    // Private constructor to prevent instantiation
    SerialHandshakeHandler() = default;
    ~SerialHandshakeHandler() = default;
};

class SerialConnectionManager{

  public:
    enum CommunicationStatus{
      unknown,
      connected,
      disconnected
    };
    CommunicationStatus communicationStatus = unknown;

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
      buildtMessage += message_part_separator;
      // Append message
      buildtMessage += String(message.message);
      buildtMessage += message_part_separator;
      // Append value with two decimal places or "NaN" if not a number
      if (isnan(value)) {
          buildtMessage += "NaN";
      } else {
          buildtMessage += String(value, 2); // 2 decimal places
      }
      buildtMessage += message_part_separator;
      // Append timestamp
      if (timestamp == ""){
        buildtMessage += "NaN";
      } else {
        buildtMessage += timestamp;
      }
      return buildtMessage;
    }

    ParsedMessageStruct* parseMessage (const String &message, ParsedMessageStruct &parsed){ //Deconstructs a serial message in the format category,message,value,timestamp\n(\n is optional)
      if(message != negativeOneSentinel){
        int commaIndex = 0;

        int commaIndexes[3];
        int commaIndexesLength = sizeof(commaIndexes)/sizeof(*commaIndexes);

        for(int i = 0; i < commaIndexesLength; i++){
          commaIndex = message.indexOf(message_part_separator, commaIndex + 1);
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
      return &parsed;
    }


  private:
    // Private constructor to prevent external instantiation
    StringMessageHandler() { //(singleton implementation, I just copy-paste)
    }

    // Private destructor (optional)
    ~StringMessageHandler() { //(singleton implementation, I just copy-paste)
    }

    char message_part_separator = ",";

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

    ParsedMessageStruct* getMessage(ParsedMessageStruct &parsed)
    {
      String incomingMessage = receiveMessage();
      stringMessageHandler.parseMessage(incomingMessage, parsed);
      return &parsed;
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
    // Private constructor to prevent external instantiation
    SerialMessageHandler() {
    }

    // Private destructor (optional)
    ~SerialMessageHandler() {
    }

    StringMessageHandler &stringMessageHandler = StringMessageHandler::getInstance();

};


//max31856 CS designated pin for Chip Select (int), heating element oven controll pin (int), force oven to stay off? (bool), use the heating simulation? (bool), optional thermocouple type (int)
OvenData oven1Data(10, 5, false, false);

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
  oven1Data.begin();
  pinMode(3, OUTPUT);
}

void loop() {
  currentTime = millis(); //Put in a getTime method, in a new timekeeping struct

  ParsedMessageStruct *message = serialMessageHandler.getMessage(parsedMessageStruct);

  // if(message->message == &Messages::PING_RECEIVING){
  //   digitalWrite(3, HIGH);
  // }


  // //Get all of this, including whatever in the global scope they use, into their structs or classes, in batch
  // if(SerialHandshakeHandler::checkHandshake(message)){
    serialConnectionManager.communicationStatus = SerialConnectionManager::CommunicationStatus::connected;
  //   serialMessageHandler.passMessage(Messages::PING_SENDING);
  //   lastSerialPingTime = currentTime;
  // }

  
  // if(!isnan(lastSerialPingTime)){
  //   deltaSerialPingTime = currentTime - lastSerialPingTime;
  // }
  // if(SerialConnectionManager::CommunicationStatus::connected && deltaSerialPingTime >= serialPingTime){
  //   serialConnectionManager.communicationStatus = SerialConnectionManager::CommunicationStatus::disconnected;
  // }

  //Procedure for the connectivity recheck: Send a ping to python every 60 seconds, then return to main loop and keep reading the serial port.
  //Look for reply message, and if there's no response within five deltatime seconds, assume disconnection.
  //It avoids the need for a big, big buffer array, and eliminates pot luck of receiving the message at the right time completely.
  //It's non-blocking. 
  

  // delay(1000);
  // // put your main code here, to run repeatedly:
  // delay(devDelay);

  if (oven1Data.useHeatingSimulation) {
    oven1Data.currentTemp = tempSimulation(oven1Data.heatingOn, oven1Data.currentTemp, oven1SimulationData);
  } else {
    oven1Data.currentTemp = oven1Data.maxSensor.readThermocoupleTemperature();
  }

  if (oven1Data.currentTemp <= oven1Data.tempGoal) {
    oven1Data.heatingOn = true;
  } else {
    oven1Data.heatingOn = false;
  }

  if (oven1Data.heatingOverride) {
    digitalWrite(oven1Data.heatingElement, LOW);
  }
  else
  {
    if (oven1Data.heatingOn) {
      digitalWrite(oven1Data.heatingElement, HIGH);
    }
    else
    {
      digitalWrite(oven1Data.heatingElement, LOW);
    }
  }

  Serial.println(oven1Data.currentTemp);

  // Serial.println(oven1Data.currentTemp);
  // Serial.println(oven1Data.heatingOn);
  // // // digitalWrite(oven1Data.heatingElement, HIGH);
  // // // delay(2000);
  // // // digitalWrite(oven1Data.heatingElement, LOW);
  // // // delay(2000);
  // Serial.println("01,02,NaN,NaN");
}

//Simulation, not important for the system, and can optionally be ignored
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