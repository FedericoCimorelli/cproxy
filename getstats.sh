 #!/bin/bash
sshpass  -p "odl" scp -P 2004 odl@172.27.1.4:/home/odl/cproxy/flowmod_latency_C1.csv ./flowmod_latency_C1.csv
sshpass  -p "odl" scp -P 2004 odl@172.27.1.4:/home/odl/cproxy/flowmod_latency_C2.csv ./flowmod_latency_C2.csv
sshpass  -p "odl" scp -P 2004 odl@172.27.1.4:/home/odl/cproxy/flowmod_latency_C3.csv ./flowmod_latency_C3.csv
sshpass  -p "odl" scp -P 2004 odl@172.27.1.4:/home/odl/cproxy/wardrop.csv ./wardrop.csv
