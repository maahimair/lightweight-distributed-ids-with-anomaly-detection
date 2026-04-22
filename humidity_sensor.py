import paho.mqtt.client as mqtt
import time
import random

broker = "localhost"
topic = "iot/humidity"

client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
client.connect(broker, 1883)

while True:
    humidity = random.randint(30, 80)
    client.publish(topic, humidity)
    print("Humidity sent:", humidity)
    time.sleep(2)
