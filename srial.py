import serial

# Configura el puerto serial (puerto 10 para el Arduino Nano)
puerto_serial = "COM10"  # En Windows, el puerto es algo como COM10; en Linux sería /dev/ttyUSB0 o /dev/ttyACM0
baud_rate = 9600  # Velocidad de transmisión del Arduino (debe coincidir con la configurada en el código del Arduino)

# Configurar la conexión serial
try:
    ser = serial.Serial(puerto_serial, baud_rate, timeout=1)  # Establecer la conexión serial con el puerto y velocidad deseada
    print(f"Conectado al puerto {puerto_serial} a {baud_rate} baudios")
except serial.SerialException:
    print(f"No se pudo conectar al puerto {puerto_serial}. Verifica el puerto y el dispositivo.")
    exit()

# Leer y mostrar los datos del puerto serial
while True:
    if ser.in_waiting > 0:  # Verifica si hay datos en el puerto serial
        data = ser.readline().decode('utf-8').strip()  # Lee una línea de datos y la decodifica
        print(f"Datos recibidos: {data}")

