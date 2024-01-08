import json
import logging
import os
import threading
import time
import paho.mqtt.client as mqtt
from AttackerBase import AttackerBase
from MqttHelper import read_mqtt_params
import queue

from ics_sim.Device import Runnable


class AttackerRemote(AttackerBase):

    def __init__(self, remote_connection_file):
        AttackerBase.__init__(self, 'attacker_remote')
        self.remote_connection_file = remote_connection_file
        self.enabled = False
        self.applying_attack = False
        self.attacksQueue = queue.Queue()
        self.client = mqtt.Client()
        self.mqtt_thread = False

    def setup_mqtt_client(self):
        connection_params = read_mqtt_params(self.remote_connection_file)
        connection_params['topic'] = connection_params['topic'] + '/#'

        if connection_params.keys().__contains__('username') and connection_params.keys().__contains__('password'):
            print('password')
            username = connection_params['username']
            password = connection_params['password']
            self.client.username_pw_set(username, password)

        # Set up callback functions
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message

        self.client.connect(connection_params['address'], int(connection_params['port']))
        self.client.subscribe(connection_params['topic'], qos=1)
        self.client.loop_forever()

    def on_subscribe(self, client, userdata, mid, granted_qos):
        self.report("Subscribed: " + str(mid) + " " + str(granted_qos), level=logging.INFO)

    def on_message(self, client, userdata, msg):
        self.report(msg.topic + " " + str(msg.qos) + " " + str(msg.payload), level=logging.INFO)
        if self.applying_attack:
            self.report(f'Discard applying attack ({str(msg.payload)}) since already applying an attack.')
        else:
            self.attacksQueue.put(msg)

    def try_enable(self):

        sample = self._make_text("""
        type: MQTT
        address: <server_address>.com
        port: <port>
        topic: <testtopic>
        username: <optional username>
        password: <optional password>""", Runnable.COLOR_GREEN)

        message = f"""
        
        Please make sure you have right configuration in \"{self._make_text(self.remote_connection_file, Runnable.COLOR_GREEN)}\" file, before enabling attacker_remote!.
          
        Connection file must contains text file including of required info for making MQTT connection. 
        Sample of connection file:
        """ + sample + f"""
        Do you want to enable attacker_remote (y/n)?: """

        response = input(message)
        if not (response.lower() == "y" or response.lower() == "yes"):
            return

        connection_params = read_mqtt_params(self.remote_connection_file)
        if not all(key in connection_params for key in ["type", "address", "port", "topic"]):
            self.report(f'Connection file ({self.remote_connection_file}) is in wrong format. Not found correct keys!',
                        logging.ERROR)
            return

        for value in connection_params.values():
            if str(value).startswith("<") or str(value).endswith(">"):
                self.report(
                    f'Connection file ({self.remote_connection_file}) is in wrong format. Not found correct values!',
                    logging.ERROR)
                return

        new_msg = "connection file compiled! with following params:\n"
        for key,value in connection_params.items():
            new_msg += f'{key}: {value}'

        new_msg = Runnable._make_text(new_msg, Runnable.COLOR_YELLOW)

        self.report(new_msg)

        self.mqtt_thread = threading.Thread(target=self.setup_mqtt_client)
        self.mqtt_thread.start()
        self.enabled = True

    def _logic(self):
        if not self.enabled:
            self.try_enable()
        elif not self.attacksQueue.empty():
            self.applying_attack = True
            self.process_messages(self.attacksQueue.get())
            self.applying_attack = False
        else:
            time.sleep(2)

    def process_messages(self, msg):
        try:
            msg = json.loads(msg.payload.decode("utf-8"))
            self.report(f'Start processing incoming message: ({msg})', level=logging.INFO)
            attack = self.find_tag_in_msg(msg, 'attack')

            if attack == 'ip-scan':
                self._scan_scapy_attack()

            elif attack == 'ddos':
                timeout = self.find_tag_in_msg(msg, 'timeout')
                target = self.find_tag_in_msg(msg, 'target')
                target = self.find_device_address(target)
                self._ddos_attack(timeout=timeout, target=target, num_process=5)

            elif attack == 'port-scan':
                self._scan_nmap_attack()

            elif attack == 'mitm':
                mode = self.find_tag_in_msg(msg, 'mode')
                timeout = self.find_tag_in_msg(msg, 'timeout')
                target = '192.168.0.1/24'
                if mode.lower() == 'link':
                    target_1 = self.find_tag_in_msg(msg, 'target1')
                    target_2 = self.find_tag_in_msg(msg, 'target2')
                    target = self.find_device_address(target_1) + "," + self.find_device_address(target_2)
                self._mitm_scapy_attack(target=target, timeout=timeout)

            elif attack == 'replay':
                mode = self.find_tag_in_msg(msg, 'mode')
                timeout = self.find_tag_in_msg(msg, 'timeout')
                target = '192.168.0.1/24'
                replay = self.find_tag_in_msg(msg, 'replay')
                if mode.lower() == 'link':
                    target_1 = self.find_tag_in_msg(msg, 'target1')
                    target_2 = self.find_tag_in_msg(msg, 'target2')
                    target = self.find_device_address(target_1) + "," + self.find_device_address(target_2)
                self._replay_scapy_attack(target=target, timeout=timeout, replay_count=replay)
            else:
                raise Exception(f"attack type: ({attack}) is not recognized!")
        except Exception as e:
            self.report(e.__str__())

    @staticmethod
    def find_tag_in_msg(msg, tag):
        if not msg.keys().__contains__(tag):
            raise Exception(f'Cannot find tag name: ({tag}) in message!')
        return msg[tag]

    @staticmethod
    def find_device_address(device_name):
        if device_name.lower() == 'plc1':
            return '192.168.0.11'
        elif device_name.lower() == 'plc2':
            return '192.168.0.12'

        elif device_name.lower() == 'hmi1':
            return '192.168.0.21'

        elif device_name.lower() == 'hmi2':
            return '192.168.0.22'
        else:
            raise Exception(f'target:({device_name}) is not recognized!')


if __name__ == '__main__':
    attackerRemote = AttackerRemote("AttackerRemoteConnection.txt")
    attackerRemote.start()
