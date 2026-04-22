import paho.mqtt.client as mqtt

# Thresholds (can be changed)
TEMP_THRESHOLD = 45
HUMIDITY_THRESHOLD = 70

def on_connect(client, userdata, flags, rc):
    print("CONNECTED to broker, rc =", rc)
    client.subscribe("iot/#")  # listen to all IoT topics

def on_message(client, userdata, msg):
    value = int(msg.payload.decode())

    if msg.topic == "iot/temperature":
        print("Temperature:", value)
        if value > TEMP_THRESHOLD:
            print("ALERT: Temperature Anomaly!")

    elif msg.topic == "iot/humidity":
        print("Humidity:", value)
        if value > HUMIDITY_THRESHOLD:
            print("ALERT: Humidity Anomaly!")

# MQTT client setup
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
client.on_connect = on_connect
client.on_message = on_message

client.connect("localhost", 1883, 60)
print("IDS started...")
client.loop_forever()
