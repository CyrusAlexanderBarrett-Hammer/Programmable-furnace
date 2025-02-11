//User settings
int serialLedPin = 8;

int oven1ControllPin = 7; //Controll pin for the oven SSR.
float oven1AbsoluteMax = 100;

unsigned long externalPwmHighPeriod = 2000; //Maximum time the external PWM signal should be high. Slightly above actual intervals.
int srLatchResetPin = 4;
int srLatchOutputPin = 5;

bool useOven1TemperatureSensor = true;
int oven1TemperatureSensorCSPin = SS; //CS = Chip Select. Does not need to be correct if not using temperature sensor.
int oven1TemperatureSensorTcType = 3; //Thermocouple types: B:0, E:1, J:2, K:3, N:4, R:5, S:6, T:7

//Dev settings
bool heatingOverride = false; //Oven might be connected and on, but you don't want the Arduino to controll it
bool useHeatingSimulation = true; //If you don't have an oven