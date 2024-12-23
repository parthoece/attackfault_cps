

printStep(){
    echo ""
    echo ""
    echo "[" $1 "STARTED]"
    sleep 1 
}

printStep "DEPLOYMENT"

printStep "DOWN PREVIOUS CONTAINERS"
sudo docker compose down 

printStep "CREATE TEMP SRC FILE"
sudo mkdir ./ics-docker/src/ 
sudo mkdir ./attacker-docker/src/ 

printStep "PRUNING DOCKER"
sudo docker system prune -f

printStep 'DOCKER_COMPOSE BUILD'
sudo docker compose build

printStep "REMOVE TEMP SRC FILE"
sudo rm -r ./ics-docker/src/ 
sudo rm -r ./attacker-docker/src/ 

printStep 'DOCKER_COMPOSE UP'
sudo docker compose up -d

printStep 'DOCKER_COMPOSE UP'
sudo docker compose ps

#sudo tcpdump -w traffic.pcap -i br_icsnet

printStep "CAPTURING TRAFFIC PACKETS"
sudo tcpdump -w ./logs/traffic_$(date +%F_%T).pcap -i br_icsnet &
#sudo tcpdump -w traffic_all_$(date +%F_%T).pcap -i any &


printStep "RECORDING SYSLOG DATA"
#sudo tail -f /var/log/syslog > syslog_data.log &
sudo tail -f /var/log/syslog > ./logs/syslog_data_$(date +%F_%T).log &


printStep "DEPLOYMENT COMPLETE"
