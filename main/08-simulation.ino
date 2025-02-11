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

class TempSimulation
{
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
};