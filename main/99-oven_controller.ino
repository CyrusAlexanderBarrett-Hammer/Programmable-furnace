bool generalEmergency = false; //Critical error. Oven controll SSR will be off as long as this is on.

//Object instance pointer (*) ready to be initialiozed and set up later
Oven *oven1 = nullptr;
SrLatchFrozenWatchdog *oven1SrLatchFrozenWatchdog = nullptr;

//Object instance pointers (*) ready to be initialiozed andset up later
Max31856Sensor *oven1TemperatureSensor = nullptr;
OvenOverheatWatchdog *oven1OverheatWatchdog = nullptr;

void setup() {

  //Oven SSR pin (int), absolute max temperature (float), goal temperature for oven (float), force oven to stay off? (bool), use the heating simulation? (bool)
  oven1 = new Oven(oven1ControllPin, oven1AbsoluteMax);
  oven1SrLatchFrozenWatchdog = new SrLatchFrozenWatchdog(externalPwmHighPeriod, srLatchResetPin, srLatchOutputPin);
  oven1SrLatchFrozenWatchdog->begin(); // -> is used instead of . for pointers.

  if(useOven1TemperatureSensor)
  {
    //max31856 CS designated pin for Chip Select (int), optional thermocouple type (int)
    oven1TemperatureSensor = new Max31856Sensor(oven1TemperatureSensorCSPin, oven1TemperatureSensorTcType);
    oven1TemperatureSensor->begin();
    oven1OverheatWatchdog = new OvenOverheatWatchdog(oven1AbsoluteMax);
  }
  serialConnectionManager.begin();

  pinMode(serialLedPin, OUTPUT);
}

void loop() {
  ParsedMessageStruct message = serialMessageHandler.getMessage();

  serialHandshakeHandler.handleHandshake(message);
  
  bool resetErrors = digitalRead(errorResetPin);
  if(resetErrors)
  {
    oven1SrLatchFrozenWatchdog->srLatchFrozen = false;
    oven1OverheatWatchdog->ovenOverheat = false;
    oven1TemperatureSensor->temperatureSensorFailAlarm = false;
    generalEmergency = false;

    resetErrors = false;
  }

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
    digitalWrite(serialLedPin, HIGH);
    sendAlarmMessages(
      generalEmergency,
      oven1TemperatureSensor->temperatureSensorFailAlarm,
      oven1OverheatWatchdog->ovenOverheat,
      oven1SrLatchFrozenWatchdog->srLatchFrozen
    );
  }
  else
  {
    digitalWrite(serialLedPin, LOW);
  }

  if(message.message == &Messages::FORCE_EMERGENCY_STOP)
  {
    generalEmergency = true;
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
  if(temperatureSensorFailAlarm)
  {
    if(MessageTimeouts::THERMOSENSOR_ERROR.timedOut())
      {
        serialMessageHandler.passMessage(Messages::THERMOSENSOR_ERROR);
        MessageTimeouts::THERMOSENSOR_ERROR.resetTimer();
      }
  }
  if(ovenOverheat)
  {
    if(MessageTimeouts::OVEN_OVERHEAT.timedOut())
      {
        serialMessageHandler.passMessage(Messages::OVEN_OVERHEAT);
        MessageTimeouts::OVEN_OVERHEAT.resetTimer();
      }
  }
  if(srLatchFrozen)
  {
    if(MessageTimeouts::WATCHDOG_SR_LATCH_FROZEN.timedOut())
      {
        serialMessageHandler.passMessage(Messages::WATCHDOG_SR_LATCH_FROZEN);
        MessageTimeouts::WATCHDOG_SR_LATCH_FROZEN.resetTimer();
      }
  }
}