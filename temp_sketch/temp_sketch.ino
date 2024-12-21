
        #include "HX711.h"
        #define DT 2
        #define SCK 3
        HX711 balanza;
        void setup() {
            Serial.begin(9600);
            balanza.begin(DT, SCK);
            Serial.println("Lectura del valor del ADC:");
            Serial.println(balanza.read());
            balanza.set_scale();
            balanza.tare(1);
        }
        void loop() {
            if (Serial.available()) {
            char command = Serial.read();
            if (command == 'R') { // Comando de reinicio
                Serial.println("Reiniciando Arduino...");
                delay(100); // Breve pausa antes de reiniciar
                asm volatile("jmp 0"); // Reinicio por software
            }
            }
            Serial.print("Valor: 	");
            Serial.println(balanza.get_value(), 0);
            delay(1);
        }
        