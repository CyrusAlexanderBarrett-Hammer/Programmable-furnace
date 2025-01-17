#include "String.h"

void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);
  pinMode(3, OUTPUT);
}

void loop() {
  // put your main code here, to run repeatedly:
  String hi = Serial.readStringUntil('\n');
  if(hi == "RETRET!"){
    digitalWrite(3, HIGH);
  }
}
