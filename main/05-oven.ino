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
            {pinMode(_ovenControllPin, OUTPUT);}
  
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