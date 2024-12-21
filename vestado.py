from PyQt5 import QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtGui import QIntValidator, QDoubleValidator
import serial
import serial.tools.list_ports
import sys
from Ui_inicio import Ui_Inicio
import os
import time
import subprocess
from PyQt5.QtCore import QTimer
import re
class ArduinoReaderThread(QThread):
    data_received = pyqtSignal(str)
    connection_status = pyqtSignal(str) 
    arduino_reset = pyqtSignal()

    def __init__(self, port="COM10", baud_rate=9600, parent=None): #WINDOWS COM en Linux sería /dev/ttyUSB0 o /dev/ttyACM0
        super().__init__(parent)
        self.port = port
        self.baud_rate = baud_rate
        self.serial_connection = None
        self.running = False
        
    def run(self):
        self.running = True
        while self.running:
            try:
                if self.serial_connection is None or not self.serial_connection.is_open:
                    print(f"Conectando a {self.port}...")
                    self.serial_connection = serial.Serial(
                        port=self.port,
                        baudrate=self.baud_rate,
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        timeout=1
                    )
                    self.connection_status.emit("Conectado")
                if self.serial_connection.in_waiting > 10:
                    data = self.serial_connection.readline()
                    decoded_data = data.decode('utf-8', errors='ignore').strip()
                    self.data_received.emit(decoded_data)  

            except serial.SerialException as e:
                print(f"Error en la comunicación serial: {e}")
                self.connection_status.emit("Desconectado")
                if self.serial_connection is not None and self.serial_connection.is_open:
                    self.serial_connection.close() 

            except Exception as e:
                print(f"Error inesperado: {e}")
                self.connection_status.emit("Desconectado")  

    def reset_arduino(self):
        """Envía un comando al Arduino para que se reinicie."""
        if self.serial_connection is not None and self.serial_connection.is_open:
            try:
                self.serial_connection.write(b'R')  # Enviar el comando de reinicio
                print("Comando de reset enviado al Arduino.")
            except serial.SerialException as e:
                print(f"Error al enviar el comando de reset: {e}")
        else:
            print("No hay conexión serial activa para enviar el comando de reset.")     

        self.arduino_reset.emit()     

    def stop(self):
        self.running = False
        self.wait()
        print("Hilo detenido.")

    def cleanup(self):
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.close()
                print(f"Conexión serial cerrada en {self.port}.")
            except Exception as e:
                print(f"Error al cerrar la conexión serial: {e}")

    def is_running(self):
        return self.running

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_Inicio()
        self.serial_thread = None
        self.ui.setupUi(self)
        self.min_value = None
        self.max_value = None
        self.mid_value = None
        self.latest_value = None 
        self.data_counter = 0
        self.conversion_factor = None
        self.is_calibrated = False
        self.peso_timer = QTimer()
        self.peso_timer.timeout.connect(self.actualizar_peso_calibrado)
        self.setWindowTitle("Lectura y Programación de Arduino")
        self.update_serial_ports()

        self.arduino_manager = ArduinoReaderThread(self.start_thread)
        self.arduino_manager.arduino_reset.connect(self.reset_min_max)
        
        self.reader_thread = ArduinoReaderThread()#Linux sería /dev/ttyUSB0 o /dev/ttyACM0
        self.reader_thread.data_received.connect(self.update_display)
        self.reader_thread.connection_status.connect(self.update_connection_status)
        self.reader_thread.arduino_reset.connect(self.reset_min_max)
        self.reader_thread.start()
        
        self.ui.btn_restart.clicked.connect(self.reset_arduino)
        self.ui.btn_restart_cont.clicked.connect(self.reset_min_max)
        self.ui.btn_restart_adc.clicked.connect(self.reset_adc)
        self.ui.btn_calibrar.clicked.connect(self.calibrar_peso)
        self.ui.btn_mostrar_peso.clicked.connect(self.mostrar_peso_calibrado)

        # self.ui.btn_mostra_peso.clicked.connect(self)
    def update_serial_ports(self):
        """Llena el combobox con los puertos seriales disponibles."""
        ports = serial.tools.list_ports.comports()
        self.ui.combo_Port.clear()  # Limpia el combobox antes de agregar los puertos
        for port in ports:
            self.ui.combo_Port.addItem(port.device)  # Agrega los nombres de los puertos disponibles

        if self.ui.combo_Port.count() == 0:
            self.ui.combo_Port.addItem("vacio")
            
    def start_thread(self):
        """Inicia el hilo de lectura del puerto serial."""
        selected_port = self.ui.combo_Port.currentText()
        if selected_port == "No se encontraron puertos" or not selected_port:
            return
        # self.serial_thread = ArduinoReaderThread(selected_port)
        # self.reader_thread = ArduinoReaderThread(selected_port)#Linux sería /dev/ttyUSB0 o /dev/ttyACM0
        # self.reader_thread.data_received.connect(self.update_display)
        # self.reader_thread.connection_status.connect(self.update_connection_status)
        # self.reader_thread.arduino_reset.connect(self.reset_min_max)
        # self.reader_thread.start()

    def update_connection_status(self, status):
        if status == "Conectado":
            self.ui.lblEstadoIndicador.setStyleSheet("background-color: rgb(20, 180, 60); border-radius: 10px;")
            self.ui.lblEstadoIndicador.setText("Conectado")
        elif status == "Desconectado":
            self.ui.lblEstadoIndicador.setStyleSheet("background-color: rgb(255, 0, 0); border-radius: 10px;")
            self.ui.lblEstadoIndicador.setText("Desconectado")
        if status == "Desconectado":
            self.reset_min_max()

    def update_display(self, data):
        self.ui.lblPesoIndicador.setText(data)
        self.update_min_max(data)

    def update_min_max(self, data):
       
        self.data_counter += 1
        if self.data_counter <= 10:
            print(f"Omitiendo dato {self.data_counter}: {data}")
            return

        try:
            match = re.search(r"-?\d+", data)
            if not match:
                print(f"No se encontró un número en el dato: {data}")
                return

            value = int(match.group())  
            if self.min_value is None or value < self.min_value:
                self.min_value = value
                self.ui.lbl_valor_min.setText(f"{self.min_value}")

            if self.max_value is None or value > self.max_value:
                self.max_value = value
                self.ui.lbl_valor_max.setText(f"{self.max_value}")
            
            if self.min_value is not None and self.max_value is not None:
                margin = self.max_value - self.min_value
                self.ui.lbl_margen.setText(f"{margin}")

                if self.mid_value is None:
                    self.mid_value = (self.min_value + self.max_value) // 2
                    self.ui.lbl_medio.setText(f"{self.mid_value}")

                    if self.mid_value is not None:
                        self.mid_value = (self.min_value + self.max_value) // 2
                        self.ui.lbl_medio.setText(f"{self.mid_value}")

        except ValueError:
            print(f"Error al procesar el dato: {data}")

    def reset_min_max(self):

        self.min_value = None
        self.max_value = None
        self.margin = None
        self.data_counter = 0 
        self.ui.lbl_valor_min.setText("0000")
        self.ui.lbl_valor_max.setText("0000")

    def reset_adc(self):
        self.mid_value = None
        self.ui.lbl_medio.setText("0000")

    def calibrar_peso(self):
        """
        Calibra el peso utilizando la fórmula m = (X2 - X1) / (Y2 - Y1).
        X1 = 0 (constante), X2 = peso real ingresado.
        Y1 = lbl_medio (ADC sin peso), Y2 = lblPesoIndicador (ADC con peso).
        """
        try:
            X1 = 0

            # Peso real ingresado
            peso_real_text = self.ui.txt_peso_real.text()
            if not peso_real_text.strip():
                print("Error: El campo del peso real está vacío.")
                return
            X2 = float(peso_real_text)
            if X2 <= 0:
                print("Error: El peso real debe ser mayor a 0.")
                return

            # ADC sin peso (Y1)
            lbl_medio_text = self.ui.lbl_medio.text()
            if not lbl_medio_text.strip():
                print("Error: El valor ADC sin peso no está definido.")
                return
            Y1 = float(lbl_medio_text)

            # ADC con peso (Y2)
            lbl_peso_indicador_text = self.ui.lblPesoIndicador.text()
            if not lbl_peso_indicador_text.strip():
                print("Error: El valor ADC con peso no está definido.")
                return
            Y2 = float(lbl_peso_indicador_text)
            if Y2 <= Y1:
                print("Error: El valor ADC con peso debe ser mayor al valor sin peso.")
                return

            self.calibration_factor = round((X2 - X1) / (Y2 - Y1), 7)
            self.Y1_saved = Y1  # Guardar el valor de ADC sin peso
            self.is_calibrated = True  # Indicar que el sistema está calibrado
            print(f"Factor de calibración calculado: {self.calibration_factor:.7f}")
            print(f"Valor ADC sin peso guardado: {self.Y1_saved:.3f}")

        except ValueError as ve:
            print(f"Error de validación: {ve}. Por favor, ingrese valores numéricos válidos.")
        except Exception as e:
            print(f"Error inesperado durante la calibración: {e}")

    def mostrar_peso_calibrado(self):
        """
        Inicia la actualización en tiempo real del peso calibrado.
        """
        try:
            # Verificar si la calibración se realizó
            if not hasattr(self, 'calibration_factor') or not self.is_calibrated:
                print("Error: El sistema no está calibrado. Calibre antes de mostrar el peso.")
                return

            self.reset_arduino()

            lbl_medio_text = self.ui.lbl_medio.text()
            if not lbl_medio_text.strip():
                print("Error: El valor ADC sin peso no está definido.")
                return
            self.Y1_saved = float(lbl_medio_text)

            if not self.peso_timer.isActive():
                self.peso_timer.start(1)  # Intervalo de 1 ms
                print("Actualización en tiempo real del peso calibrado iniciada.")

        except Exception as e:
            print(f"Error inesperado al iniciar la actualización en tiempo real: {e}")

    def actualizar_peso_calibrado(self):
        """
        Calcula y actualiza el peso calibrado en tiempo real.
        """
        try:
            # Obtener el valor actualizado de lblPesoIndicador
            lbl_peso_indicador_text = self.ui.lblPesoIndicador.text()
            if not lbl_peso_indicador_text.strip():
                print("Error: El valor ADC con peso no está definido.")
                return
            Y2 = float(lbl_peso_indicador_text)

            Y1 = getattr(self, 'Y1_saved', None)
            if Y1 is None:
                print("Error: El valor ADC sin peso no está disponible.")
                return

            peso_calibrado = round(self.calibration_factor * (Y2 - Y1), 3)

            self.ui.lbl_peso_calibrado.setText(f"{peso_calibrado:.3f}")
            # print(f"Peso calibrado actualizado: {peso_calibrado:.3f}")

        except ValueError as ve:
            print(f"Error de validación: {ve}. Por favor, verifique los valores numéricos.")
        except Exception as e:
            print(f"Error inesperado al actualizar el peso calibrado: {e}")
    
    def reset_arduino(self):
        self.reader_thread.reset_arduino()

    def closeEvent(self, event):
        if self.reader_thread.isRunning():
            self.reader_thread.stop()
            self.reader_thread.wait()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_app = MainApp()
    main_app.show()
    sys.exit(app.exec_())