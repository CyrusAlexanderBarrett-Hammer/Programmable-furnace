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