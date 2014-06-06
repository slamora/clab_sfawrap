README
------

This package contains the SFA wrapper server for the Community-Lab testebd.
The wrapper is installed and publicly available on https://84.88.85.16:12346/

To install the wrapper there are some dependencies that must be satisfied:

 - SFA (SFAWrap) http://svn.planet-lab.org/wiki/SFATutorialInstall
 - CONFINE-ORM  http://confine-orm.readthedocs.org/

Installation processes for the dependencies can be found on their websites.

The files, modules and classes contained in this package need to be installed to patch the SFA default installation
so it can work with Community-Lab SFA wrapper.

The correspondance between the files, modules and classes is:

./clab/  				-->   /usr/lib/python2.7/dist-packages/sfa/
./clab_other/clabimporter.py    	-->   /usr/lib/python2.7/dist-packages/sfa/importer/
./clab_other/clab.py  			-->   /usr/lib/python2.7/dist-packages/sfa/generic/
./generic/auth.py  			-->   /usr/lib/python2.7/dist-packages/sfa/trust/
./generic/pgv2.py  			-->   /usr/lib/python2.7/dist-packages/sfa/rspecs/versions/
./generic/cache.py  			-->   /usr/lib/python2.7/dist-packages/sfa/util/
./configuration/etc/			-->   /etc/sfa/
./configuration/sfa-config-tty  	-->   /usr/lib/python2.7/dist-packages/sfa/rspecs/versions/
./rspec/clabv1.py			-->   /usr/lib/python2.7/dist-packages/sfa/rspecs/elements/versions/
./rspec/clabv1Node.py			-->   /usr/lib/python2.7/dist-packages/sfa/rspecs/elements/versions/
./rspec/clabv1Sliver.py			-->   /usr/lib/python2.7/dist-packages/sfa/rspecs/elements/versions/
./rspec/clabv1SliverParameters.py	-->   /usr/lib/python2.7/dist-packages/sfa/rspecs/elements/versions/
./rspec/clabv1Interface.py		-->   /usr/lib/python2.7/dist-packages/sfa/rspecs/elements/versions/


INSTALL
-------

The installation script automates the installation process. It installs the necessary dependencies
and patch the SFA installation as needed.

Run the script:

./install.sh



CONFIGURE
---------

To configure the SFAWrap to work with Community-Lab_

1. Run the configuration tool: sfa-config-tty
2. Type "u" for usual changes.
3. Enter the configuration:
	 sfa_generic_flavour : [clab] 
	 sfa_interface_hrn : [clab] 
	 sfa_registry_root_auth : [clab] 
	 sfa_registry_host : [ip_of_the-host] 
	 sfa_aggregate_host : [ip_of_the-host] 
	 sfa_sm_host : [ip_of_the-host] 
	 sfa_db_host : [ip_of_the-host] 
	 sfa_clab_user : [user_name_of_communitylab] 
	 sfa_clab_password : [********] 
	 sfa_clab_group : [group_of_communitylab] 
	 sfa_clab_url : [https://controller.community-lab.net/api/] 
	 sfa_clab_auto_slice_creation : [True] 
	 sfa_clab_auto_node_creation : [False] 
	 sfa_clab_aggregate_caching : [True] 
	 sfa_clab_aggregate_cache_expiration_time : [600]
	 sfa_clab_default_template : [Debian Squeeze] 
	 sfa_clab_temp_dir_exp_data : [~/clab_sfawrap/experiment-data/] 
4. Type "w" to write the changes.
5. Type "r" to restart the wrapper.
6. Type "q" to quit.


USAGE
-----
After the configuraiton the wrapper is ready to be used.
It exposes the following interfaces:

PlanetLabSliceRegistry v1:  https://ip_of_the-host:12345/
Community-Lab SFA AM v3:    https://ip_of_the-host:12346/





