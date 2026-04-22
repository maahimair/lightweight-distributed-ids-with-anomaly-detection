import paho.mqtt.client as mqtt
import time
import random

broker = "localhost"
topic = "iot/temperature"

client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
client.connect(broker, 1883)

while True:
    temperature = random.randint(20, 40)
    client.publish(topic, temperature)
    print("Temperature sent:", temperature)
    time.sleep(2)
