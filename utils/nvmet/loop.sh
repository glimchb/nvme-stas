sudo yum install nvmetcli
sudo modprobe -v nvme-loop
sudo nvmetcli restore loop.json

sudo nvme connect --transport=loop --hostnqn=test_hostnqn --nqn=test_subnqn
sudo nvme list

sudo nvmetcli clear

