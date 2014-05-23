
# INSTALLATION SCRIPT FOR COMMUNITY-LAB SFA WRAPPER


########################
# INSTALL DEPENDENCIES #
########################

# SFA
cd /etc/apt/sources.list.d/
echo "deb http://build-debian.onelab.eu/sfa/stable-precise-64/ ./" > sfa.list
apt-get update -y
apt-get install -y --force-yes sfa sfa-common sfa-client sfa-dummy 

# ORM
apt-get install python-pip
pip install confine-orm

# Wrapper modules and classes
cp -r ./clab/ /usr/lib/python2.7/dist-packages/sfa/
cp ./clab_other/clabimporter.py /usr/lib/python2.7/dist-packages/sfa/importer/
cp ./clab_other/clab.py /usr/lib/python2.7/dist-packages/sfa/generic/
cp ./generic/auth.py /usr/lib/python2.7/dist-packages/sfa/trust/
cp ./generic/pgv2.py /usr/lib/python2.7/dist-packages/sfa/rspecs/versions/

# Wrapper configuraiton files
cp -r ./configuration/etc/* /etc/sfa/
cp ./configuration/sfa-config-tty /usr/bin/
