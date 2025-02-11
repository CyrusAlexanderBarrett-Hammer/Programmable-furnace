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