
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
cp ./generic/cache.py /usr/lib/python2.7/dist-packages/sfa/util/
cp ./configuration/sfa-config-tty /usr/lib/python2.7/dist-packages/sfa/rspecs/versions/
cp ./rspec/clabv1.py /usr/lib/python2.7/dist-packages/sfa/rspecs/elements/versions/
cp ./rspec/clabv1Node.py /usr/lib/python2.7/dist-packages/sfa/rspecs/elements/versions/
cp ./rspec/clabv1Sliver.py /usr/lib/python2.7/dist-packages/sfa/rspecs/elements/versions/
cp ./rspec/clabv1SliverParameters.py /usr/lib/python2.7/dist-packages/sfa/rspecs/elements/versions/
cp ./rspec/clabv1Interface.py /usr/lib/python2.7/dist-packages/sfa/rspecs/elements/versions/

# Wrapper configuraiton files
cp -r ./configuration/etc/* /etc/sfa/
cp ./configuration/sfa-config-tty /usr/bin/
