#include "HX711.h"

const int SCK_1 = 2; const int DOUT_1 = 3;
const int SCK_2 = 4; const int DOUT_2 = 5;
const int SCK_3 = 6; const int DOUT_3 = 7;
const int SCK_4 = 8; const int DOUT_4 = 9;
const int SCK_5 = 10; const int DOUT_5 = 11;
const int SCK_6 = 12; const int DOUT_6 = 13;

HX711 scale1; HX711 scale2; HX711 scale3; HX711 scale4; HX711 scale5; HX711 scale6;

long load1; long load2; long load3; long load4; long load5; long load6; long total;
long tare1=0; long tare2=0; long tare3=0; long tare4=0; long tare5=0; long tare6=0;
long reading1; long reading2; long reading3; long reading4; long reading5; long reading6;

void setup() {
  Serial.begin(9600);

  scale1.begin(DOUT_1, SCK_1);
  scale2.begin(DOUT_2, SCK_2);
  scale3.begin(DOUT_3, SCK_3);
  scale4.begin(DOUT_4, SCK_4);
  scale5.begin(DOUT_5, SCK_5);
  scale6.begin(DOUT_6, SCK_6);
}

void loop()
{
  if (Serial.available() > 0) {
      char inByte = Serial.read();
      if (inByte == 't')
      {
        tare1=reading1; tare2=reading2; tare3=reading3; tare4=reading4; tare5=reading5; tare6=reading6;
        Serial.println(String("Tare: ")+tare1+String(" ; ")+tare2+String(" ; ")+tare3+String(" ; ")+tare4+String(" ; ")+tare5+String(" ; ")+tare6);
      }
  }

  if (scale1.is_ready() && scale2.is_ready() && scale3.is_ready() && scale4.is_ready() && scale5.is_ready() && scale6.is_ready())
  {
    reading1 = scale1.read()/100;
    reading2 = scale2.read()/100;
    reading3 = scale3.read()/100;
    reading4 = scale4.read()/100;
    reading5 = scale5.read()/100;
    reading6 = scale6.read()/100;

    load1 = (reading1-tare1)/1.0930;
    load2 = (reading2-tare2)/1.0814;
    load3 = (reading3-tare3)/1.0806;
    load4 = (reading4-tare4)/1.1074;
    load5 = (reading5-tare5)/1.0948;
    load6 = (reading6-tare6)/1.0835;

    total = load1 + load2 + load3 + load4 + load5 + load6;

    Serial.println(String("MOTOR-1: ")+load5+String("; ") +
                   String("MOTOR-2: ")+load3+String("; ") + 
                   String("MOTOR-3: ")+load2+String("; ") + 
                   String("MOTOR-4: ")+load6+String("; ") +
                   String("MOTOR-6: ")+load1+String("; ")+
                   String("MOTOR-5: ")+load4+String("; ") +
                   String("TOTOAL: ")+total);
    
  } 
  else 
  {
    Serial.println("HX711 not ready");
  }

  delay(100);
  
}
