 #!/bin/bash
sshpass  -p "odl" scp -P 2004 odl@172.27.1.4:/home/odl/cproxy/controllers_latency.csv ./controllers_latency.csv
sshpass  -p "odl" scp -P 2004 odl@172.27.1.4:/home/odl/cproxy/flowmod_latency.csv ./flowmod_latency.csv
sshpass  -p "odl" scp -P 2004 odl@172.27.1.4:/home/odl/cproxy/wardrop.csv ./wardrop.csv
