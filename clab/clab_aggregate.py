'''
Created on 06/02/2014

@author: gerard
'''

from sfa.rspecs.elements.granularity import Granularity
from sfa.rspecs.elements.hardware_type import HardwareType
from sfa.rspecs.elements.lease import Lease
from sfa.rspecs.elements.login import Login
from sfa.rspecs.elements.sliver import Sliver
from sfa.rspecs.rspec import RSpec
from sfa.rspecs.version_manager import VersionManager
from sfa.storage.model import SliverAllocation
from sfa.util.sfalogging import logger
from sfa.util.sfatime import utcparse, datetime_to_string
from sfa.util.xrn import Xrn, hrn_to_urn, urn_to_hrn
from sfa.rspecs.elements.node import NodeElement
from sfa.util.faults import SearchFailed

import datetime
import time

# local imports from the Project
#from rspecs.elements.versions.clabNode import ClabNode
from sfa.clab.clab_xrn import type_of_urn, urn_to_slicename, slicename_to_urn,\
    hostname_to_urn, urn_to_nodename, urn_to_slivername, slivername_to_urn, unicode_normalize
from sfa.clab.clab_xrn import urn_to_uri, get_node_by_urn, get_slice_by_urn, get_sliver_by_urn, get_slice_by_sliver_urn
from sfa.clab.clab_slices import ClabSlices
from sfa.clab.clab_exceptions import ResourceNotFound

class ClabAggregate:
    """
    Aggregate Manager class for C-Lab. 
    GENI AM API v3
    """
    
    def __init__(self, driver):
        self.driver = driver
        self.AUTHORITY = driver.AUTHORITY
        self.AUTOMATIC_SLICE_CREATION = driver.AUTOMATIC_SLICE_CREATION
        self.AUTOMATIC_NODE_CREATION = driver.AUTOMATIC_NODE_CREATION
        self.EXP_DATA_DIR = driver.EXP_DATA_DIR
        
        
    ##################################
    # GENI AM API v3 METHODS
    ##################################
            
    def get_version(self):
        """
        Returns a dictionary following the GENI AM API v3 GetVersion struct. 
        It contains information about this aggregate manager implementation, 
        such as API and RSpec versions supported.
        
        :returns: dictionary implementing GENI AM API v3 GetVersion struct
        :rtype: dict
        
        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3#GetVersion

        """        
        # Version by default: GENI 3
        version_manager = VersionManager()
        
        # int geni_api 
        geni_api = int(version_manager.get_version('GENI 3').version)
        
        # struct code
        code = dict(geni_code=0)
        
        # struct value
        value = dict()
        value['geni_api'] = int(version_manager.get_version('GENI 3').version)
        value['geni_api_versions'] = dict([(version_manager.get_version('GENI 3').version, "https://84.88.85.16:12346")])
        value['geni_request_rspec_versions'] = [version.to_dict() for version in version_manager.versions if (version.content_type in ['*', 'request'] and version.type in ['GENI','CLab'])]
        value['geni_ad_rspec_versions'] = [version.to_dict() for version in version_manager.versions if (version.content_type in ['*', 'ad'] and version.type in ['GENI','CLab'])]
        value['geni_credential_types'] = [{'geni_type': 'geni_sfa', 'geni_version' : '3'}] ##???????????????????????????? CHECK
        
        # output
        output = None
        
        return dict([('geni_api', geni_api), ('code', code), ('value', value), ('output', output)])
    
    
    
    def list_resources(self, credentials={}, options={}):
        """
        Returns an advertisement Rspec of available resources at this
        aggregate. This Rspec contains a resource listing along with their
        description, providing sufficient information for clients to be able to
        select among available resources.
        
        :param credentials: GENI credentials of the caller 
        :type credentials: list

        :param options: various options. The valid options are: {boolean
            geni_compressed <optional>; struct geni_rspec_version { string type;
            #case insensitive , string version; # case insensitive}} . The only
            mandatory options if options is specified is geni_rspec_version.
        :type options: dictionary

        :returns: On success, the value field of the return struct will contain
            a geni.rspec advertisment RSpec
        :rtype: Rspec advertisement in xml.

        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3/CommonConcepts#RSpecdatatype
        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3#ListResources
        """
        
        # Options field (from jFed) contains: {'geni_rspec_version': {'version': '3', 'type': 'geni'}, 'geni_compressed': True}
        rspec_version = options.get('geni_rspec_version').get('version', '3')
        rspec_type = options.get('geni_rspec_version').get('type', '3')
        
        version_manager = VersionManager()
        #version = version_manager.get_version('GENI 3')        
        #rspec_version= version_manager._get_version(version.type, version.version, 'ad')
        rspec_version = version_manager._get_version(rspec_type, rspec_version, 'ad')
        rspec = RSpec(version=rspec_version, user_options=options)        
           
        #Geni state in options?
        state=None
        if options.get('geni_available'): state='available'

        # Function get nodes
        nodes = self.get_nodes_by_geni_state(state)

        # Translate to Rspec
        rspec_nodes = []
        for node in nodes:
            rspec_nodes.append(self.clab_node_to_rspec_node(node, 'advertisement'))
            
        # Function get slices
        #slices = self.get_slices_by_geni_state(state)

        rspec.version.add_nodes(rspec_nodes)
        
        return rspec.toxml()
    
    
        
    def describe(self, urns, credentials={}, options={}):
        """
        Retrieve a manifest RSpec describing the resources contained by the
        named entities, e.g. a single slice or a set of the slivers in a slice.
        This listing and description should be sufficiently descriptive to allow
        experimenters to use the resources.

        :param urns: list of slice URNs or sliver URNs that belong to the same slice, whose 
            resources will be described
        :type urns: list  of strings
        
        :param credentials: GENI credentials of the caller and slices 
        :type credentials: list
        
        :param options: various options. the valid options are: {boolean
            geni_compressed <optional>; struct geni_rspec_version { string type;
            #case insensitive , string version; # case insensitive}}
        :type options: dictionary

        :returns On success returns the following dictionary:
        {
         geni_rspec: <geni.rspec, a Manifest RSpec>
         geni_urn: <string slice urn of the containing slice> 
         geni_slivers: list of dict 
                         { geni_sliver_urn: <string sliver urn>, 
                           geni_expires:  <dateTime.rfc3339 allocation expiration string, as in geni_expires from SliversStatus>,
                           geni_allocation_status: <string sliver state - e.g. geni_allocated or geni_provisioned >, 
                           geni_operational_status: <string sliver operational state>, 
                           geni_error: <optional string. The field may be omitted entirely but may not be null/None,
                                        explaining any failure for a sliver.>
                         }
        }
        :rtype dict

        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3#Describe

        """
        
        # Options field (from jFed) contains: {'geni_rspec_version': {'version': '3', 'type': 'geni'}, 'geni_compressed': True}
        rspec_version = '3'
        rspec_type = 'geni'
        rspec_definition = options.get('geni_rspec_version')
        if rspec_definition:
            rspec_version = rspec_definition.get('version', '3')
            rspec_type = rspec_definition.get('type', 'geni')
        
        version_manager = VersionManager()
        #version = version_manager.get_version('GENI 3')        
        #rspec_version= version_manager._get_version(version.type, version.version, 'manifest')
        rspec_version = version_manager._get_version(rspec_type, rspec_version, 'manifest')
        rspec = RSpec(version=rspec_version, user_options=options)   
        
        # Check that urn argument is a list (not a string)
        if isinstance(urns, str): urns = [urns] 

        if(type_of_urn(urns[0])=='slice'):
            try:
                # urns = single slice urn 
                # First urn belongs to slice. Other urns of the list will be ignored
                # There should be just one urn if the type is slice
                geni_urn=urns[0]
                # Get dictionary slice from urn
                slice=get_slice_by_urn(self.driver, geni_urn)
                # Get slivers of the slice (list of sliver dictionaries)
                slivers=self.driver.testbed_shell.get_slivers_by_slice(slice=slice)
                # Get nodes of the slice (list of nodes dictionary)
                #nodes=self.driver.testbed_shell.get_nodes_by_slice(slice=slice)
            except ResourceNotFound:
                slivers = []
                
        elif(type_of_urn(urns[0])=='sliver'):
            try:
                # urns = set of slivers urns in a single slice
                # Get the slice from one of the urn-sliver (dictionary slice)
                slice=get_slice_by_sliver_urn(self.driver, urns[0])
                geni_urn=slicename_to_urn(slice['name'])
                # Get slivers from the urns list (list of slivers dictionary)
                slivers=[]
                for urn in urns:
                    slivers.append(get_sliver_by_urn(self.driver, urn))
                # Get nodes of the slice (list of nodes dictionary)
                #nodes=self.driver.testbed_shell.get_nodes_by_slice(slice=slice)   
            except ResourceNotFound:
                raise SearchFailed(urn[0])
                
        # Prepare Return struct
        # geni_rpec. Translate nodes to rspec
        rspec_nodes = []
        geni_slivers = []
        for sliver in slivers:
            rspec_nodes.append(self.clab_sliver_to_rspec_node(sliver, 'manifest'))
            geni_slivers.append(self.clab_sliver_to_geni_sliver(sliver))
        rspec.version.add_nodes(rspec_nodes)
        
        # geni_slivers. Translate to geni (list of geni sliver dicts)
        #geni_slivers = []
        #for sliver in slivers:
        #    geni_slivers.append(self.clab_sliver_to_geni_sliver(sliver))
        
        return {'geni_urn': geni_urn,
                'geni_rspec': rspec.toxml(),
                'geni_slivers': geni_slivers}
        
            
    def allocate(self, slice_urn, rspec_string, expiration, credentials={}, options={}):
        '''
        Function to allocate/reserve the resources described in the rspec_string for a sliver 
        that will belong to the slice specified by the slice_urn argument.
        
        :param slice_urn: URN of the slice in which the resources will be allocated
        :type slice_urn: string
        
        :param credentials: GENI credentials of the caller and slices 
        :type credentials: list
        
        :param rspec_string: string that contains a XML RSpec describing the resources
            that will be allocated in the givne slice
        :type string
        
        :param expiration: string that contains the expiration date of the allocated resources
        :type string
        
        :param options: various options.
        :type options: dictionary
        
        :returns Returns the following struct:
        {
             "geni_slivers" -> [
                 {
                     "geni_sliver_urn" -> "urn:publicid:IDN+wall2.ilabt.iminds.be+sliver+2576",
                     "geni_allocation_status" -> "geni_allocated",
                     "geni_expires" -> "2014-02-10T11:39:28Z"
                }
             ],
             "geni_rspec" -> rspec string
        }
        :rtype dict
    
        NOTE: ALLOCATE (GENI) = REGISTER (C-LAB)
              Create slivers in Register state. (by default, takes state from slice)
        
        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3#Allocate      
        
        '''
        # ClabSlices class is a checker for nodes and slices
        checker = ClabSlices(self.driver)
        
        # Verify slice exist. Return slice in Register state (to be modified)
        slice = checker.verify_slice(slice_urn, credentials, self.AUTOMATIC_SLICE_CREATION, options=options)
        
        # version
        rspec_version = {'type':'clab', 'version':'1', 'content_type':'request' }
        
        # parse RSpec (if rspec_string argument)
        rspec = RSpec(rspec_string, version=rspec_version)
        # nodes in which the slivers will be created (list of dict)
        # the dict contains a 'slivers' field, a list of dicts with info about slivers (template, sliver_interfaces)
        nodes_with_slivers = rspec.version.get_nodes_with_slivers()
        # ignore slice attributes...
        requested_attributes = rspec.version.get_slice_attributes()
        created_slivers = []
        
        # Translate sliver RSpecs to C-Lab slivers
        # Each element node_with_sliver will create a sliver belonging to the slice in the corresponding node
        for node_with_sliver in nodes_with_slivers:            
            # Verify the required nodes
            bound_node = checker.verify_node(slice_urn, node_with_sliver, credentials, 
                                             self.AUTOMATIC_NODE_CREATION, options=options)
            # interfaces_definition
            #interfaces = node_with_sliver['interfaces'] 
            #interfaces_definition=[]
            #for interface in interfaces:
                # Get the interface name  (client_id = MySliverName:IfaceName)
            #    name = interface['client_id']
            #    if ':' in name: name = name.split(':')[1]
            #    interface_definition = dict([('name', name),('type', interface['role']),('nr', int(interface['interface_id']))])
            #    interfaces_definition.append(interface_definition)
            
            # Get sliver definition parameters (if any)
            sliver_parameters = {}
            slivers = node_with_sliver.get('slivers')
            if slivers:
                sliver_parameters = slivers[0]

            # properties
            # used to save the client_id field and the external_user_urn
            properties={"sfa_client_id" : node_with_sliver.get('client_id')}
            external_user_urn = options.get('external_user_urn',[])
            for x in external_user_urn:
                properties['external_user_urn'] = x
        
            
            # create the sliver
            created_sliver = self.driver.testbed_shell.create_sliver(slice['uri'], bound_node['uri'], 
                                                                     sliver_parameters.get('sliver_interfaces'), sliver_parameters.get('template'), properties)
            # force 'Register' state to the created sliver
            created_sliver = self.driver.testbed_shell.update_sliver_state(created_sliver['uri'], 'register')
            logger.debug("CREATED SLIVER IN ALLOCATE %s"%created_sliver)
            # add created sliver to a list of created slivers
            created_slivers.append(created_sliver)
            
        # prepare return struct 
        #return self.describe([slice_urn], credentials, options)
        
        version_manager = VersionManager()
        #version = version_manager.get_version('GENI 3')        
        rspec_version = version_manager._get_version('clab', '1', 'manifest')
        rspec = RSpec(version=rspec_version, user_options=options)  
        
        # Prepare Return struct
        rspec_nodes = []
        geni_slivers = []
        for sliver in created_slivers:
            rspec_nodes.append(self.clab_sliver_to_rspec_node(sliver, 'manifest'))
            geni_sliver = self.clab_sliver_to_geni_sliver(sliver)
            # Force allocated state (to avoid error in automatic test Allocate)
            ## geni_sliver['geni_allocation_status'] = 'geni_allocated'
            #geni_sliver['geni_operational_status'] = 'geni_notready'
            #geni_slivers.append(geni_sliver)
            geni_slivers.append(self.clab_sliver_to_geni_sliver(sliver))
        rspec.version.add_nodes(rspec_nodes)
        
        return {'geni_urn': slice_urn,
                'geni_rspec': rspec.toxml(),
                'geni_slivers': geni_slivers}

    
    def renew(self, urns, expiration_time, credentials={}, options={}):
        '''
        Request that the named slivers be renewed, with their expiration date extended.
        However, the expiration_time argument is ignore since in C-Lab, renewals are standard 
        and the expiration date is set to 30 days from the current date (maximum)
        In C-Lab the entities that are renewed are the SLICES, but not the SLIVERS.
        Note that renew a slice automatically renews all the slivers contained in that slice.
        Therefore, urns argument can contain sliver urns or slice urns. (either slivers or slices)
        In case of containing sliver urns, the slice in which the sliver is contained will be renewed.
        Note again that renewing a slice it automatically renews all the slivers of the slice.
        
        :param urns: list of slice URNs or sliver URNs that belong to the same slice, whose 
            resources will be described
        :type urns: list  of strings
        
        :param credentials: GENI credentials of the caller and slices 
        :type credentials: list
        
        :param options: various options. the valid options are: {boolean
            geni_best_effort <optional>} If false, it specifies whether the client 
            prefers all included slivers/slices to be renewed or none. 
            If true, partial success if possible
        :type options: dictionary
        
        :returns On success, returns a list of dict:
        [
            {    geni_sliver_urn: string
                 geni_allocation_status: string
                 geni_operational_status: string
                 geni_expires: string
            }
        ]
        :rtype list of dict
        
        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3#Renew
        
        '''
        # Get geni_best_effort option
        geni_best_effort = options.get('geni_best_effort', True)

        # Check that urn argument is a list (not a string)
        if isinstance(urns, str): urns = [urns]
        
        # SLIVERS
        if type_of_urn(urns[0])=='sliver':    
            # Get uris of slivers from the urns list
            uris = [urn_to_uri(self.driver, urn) for urn in urns]
            for uri in uris:
                ok=self.driver.testbed_shell.renew_sliver(uri)
                if not geni_best_effort and not ok: break
        
        # SLICES
        elif type_of_urn(urns[0])=='slice':
            # Get uris of slivers from the urns list
            uris = [urn_to_uri(self.driver, urn) for urn in urns]
            for uri in uris:
                ok=self.driver.testbed_shell.renew_slice(uri)
                if not geni_best_effort and not ok: break
       
        # Return struct (geni_slivers field of Describe method)
        description = self.describe(urns, 'GENI 3')
        return description['geni_slivers']

    
    def provision(self, urns, credentials={}, options={}):
        '''
        Request for provisioning the the indicated slivers/slices, so their state become geni_provisioned 
        and they may possibly be geni_ready for experimenter use.
        The urns argument indicates either the slivers or slices that have to be provisioned.
        Note that the slice status has priority over the sliver status.
        
        :param urns: list of slice URNs or sliver URNs that belong to the same slice, whose 
            resources will be provisioned
        :type urns: list  of strings
        
        :param credentials: GENI credentials of the caller and slices 
        :type credentials: list
        
        :param options: various options. the valid options are: {string
            geni_rspec_version <optional>} It indicates the verson of RSpec 
        :type options: dictionary
        
        :returns On success, returns the following dict:
        {
            geni_rspec: RSpec manifest (string)
            geni_slivers: [
                            {    geni_sliver_urn: string
                                 geni_allocation_status: string
                                 geni_operational_status: string
                                 geni_expires: string
                            }, 
                            ...
                          ]
        }
        The returned manifest covers only new provisioned slivers.
        :rtype dict 
        
        NOTE: PROVISION (GENI) = DEPLOY (C-LAB)
        
        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3#Provision
        
        '''        
                
        # DEBUG print options field
        logger.debug("clab_aggregate/PROVISION options field: %s"%options)

        # Get geni_users option
        geni_users_list = options.get('geni_users')
        
        # Create the exp-data file to push the public keys of SFA users to the provisioned sliver/slice
        exp_data_file = self.create_exp_data(self.EXP_DATA_DIR, geni_users_list)
        logger.debug("PROVISION - exp-data-file created: %s"%exp_data_file)
        
        
        # Get geni_best_effort option
        geni_best_effort = options.get('geni_best_effort', True)
        
        # Check that urn argument is a list (not a string)
        if isinstance(urns, str): urns = [urns]
        
        # SLIVER
        if type_of_urn(urns[0])=='sliver':    
            # Get sliver_uris of slivers from the urns list
            sliver_uris = [urn_to_uri(self.driver, urn) for urn in urns]
            slivers = []
            for sliver_uri in sliver_uris:
                # Upload the exp-data file to push the public keys of the SFA user
                s = self.driver.testbed_shell.upload_exp_data_to_sliver(exp_data_file, sliver_uri)
                # Set the sliver state to Deploy 
                sliver = self.driver.testbed_shell.update_sliver_state(sliver_uri, 'deploy')
                slivers.append(sliver)
                
            # Update the slice state for the changes in the sliver to have effect
            # Will not affect other slivers since they will have a lower set_state   
            # Get the slice uri of the slivers
            slice_uri = self.driver.testbed_shell.get_sliver_by(sliver_uri=sliver_uris[0])['slice']['uri']
            # Get slice dict
            slice = self.driver.testbed_shell.get_slice_by(slice_uri=slice_uri)
            # Change state of the slice if needed (lower than deploy)
            if slice['set_state'] == 'register':
                # Set slice state to 'deploy'
                self.driver.testbed_shell.update_slice_state(slice_uri, 'deploy')  
                    
        
        # SLICE
        elif type_of_urn(urns[0])=='slice':
            # Get sliver_uris of slices from the urns list
            slice_uris = [urn_to_uri(self.driver, urn) for urn in urns]
            for slice_uri in slice_uris:
                # Upload the exp-data file to push the public keys of the SFA user
                self.driver.testbed_shell.upload_exp_data_to_slice(exp_data_file, slice_uri)
                # Set the slice state to Deploy
                self.driver.testbed_shell.update_slice_state(slice_uri, 'deploy')
                
                # Update the state of all the slivers contained in the slice
                # If the set_state of the sliver was lower, the changes in the slice would not affect its slivers 
                slivers = self.driver.testbed_shell.get_slivers_by_slice(slice_uri=slice_uri)
                slivers = [self.driver.testbed_shell.update_sliver_state(sliver['uri'], 'deploy') for sliver in slivers]

                for sliver in slivers:
                    self.driver.testbed_shell.update_sliver_state(sliver['uri'], 'deploy')

                    
        # Clean the directory structure and files of the exp-data file
        self.clean_exp_data(self.EXP_DATA_DIR)
        
        # Prepare and return the struct (use describe function)   
       
         # Options field (from jFed) contains: {'geni_rspec_version': {'version': '3', 'type': 'geni'}, 'geni_compressed': True}
        rspec_version = options.get('geni_rspec_version').get('version', '3')
        rspec_type = options.get('geni_rspec_version').get('type', 'geni')
        
        version_manager = VersionManager()
        #version = version_manager.get_version('GENI 3')        
        #rspec_version= version_manager._get_version(version.type, version.version, 'manifest')
        rspec_version = version_manager._get_version(rspec_type, rspec_version, 'manifest')
        rspec = RSpec(version=rspec_version, user_options=options)   
        
        # Prepare Return struct
        rspec_nodes = []
        geni_slivers = []
        for sliver in slivers:
            rspec_nodes.append(self.clab_sliver_to_rspec_node(sliver, 'manifest'))
            # Force allocated state (to avoid error in automatic test Allocate)
            #geni_sliver = self.clab_sliver_to_geni_sliver(sliver)
            #geni_sliver['geni_allocation_status'] = 'geni_provisioned'
            #geni_slivers.append(geni_sliver)
            geni_slivers.append(self.clab_sliver_to_geni_sliver(sliver))
        rspec.version.add_nodes(rspec_nodes)
        
        return {'geni_rspec': rspec.toxml(),
                'geni_slivers': geni_slivers}
    
    def status (self, urns, credentials={}, options={}):
        '''
        Function to get the status of a sliver or slivers belonging to a single slice at the given aggregate.
        
        :param urns: list of slice URNs or sliver URNs that belong to the same slice, whose 
            status will be retrieved
        :type urns: list  of strings
        
        :param credentials: GENI credentials of the caller and slices 
        :type credentials: list
        
        :param options: various options. 
        :type options: dictionary
        
        :returns On success returns the following:
        {
            geni_urn: slice URN
            geni_slivers: [
                            {    geni_sliver_urn: sliver URN
                                 geni_allocation_status: string
                                 geni_operational_status: string
                                 geni_expires: string
                            },
                            ...
                          ]
        }
        :rtype dict
        
        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3#Status
        
        '''
        description = self.describe(urns, credentials, options)
        status = {'geni_urn': description['geni_urn'],
                  'geni_slivers': description['geni_slivers']}
        return status
        

    def perform_operational_action(self, urns, action, credentials={}, options={}):
        '''
        Perform the named operational action on the named slivers, possibly changing
        the geni_operational_staus of the slivers. 
        
        :param urns: list of slice URNs or sliver URNs that belong to the same slice, that will 
            be affected by the operational action
        :type urns: list  of strings
        
        :param credentials: GENI credentials of the caller and slices 
        :type credentials: list
        
        :param options: various options. the valid options are: 
            {boolean geni_best_effort <optional>} 
            False: action applies to all slivers equally or none
            True: try all slivers even if some fail
        :type options: dictionary
        
        :returns On success returns the following:
              [
                    {    geni_sliver_urn: sliver URN
                         geni_allocation_status: string
                         geni_operational_status: string
                         geni_expires: string
                         geni_resource_status: optional string
                         geni_error: optional string
                    },
                    ...
              ]
        :rtype list of dict
        
        Supported actions: geni_start, geni_restart, geni_stop 
        geni_start = set_state to start in the sliver/slice
        geni_restart = reboot node that contains the sliver
        geni_stop = not supported... (delete slice?)
        
        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3#Status
        
        '''
        # Get geni_best_effort option
        geni_best_effort = options.get('geni_best_effort', True)
        
        # Check that urn argument is a list (not a string)
        if isinstance(urns, str): urns = [urns]
        
        # Discover if urns is a list of sliver urns or slice urns
        if type_of_urn(urns[0])=='sliver': is_sliver_list=1 # urns is a sliver list
        else: is_sliver_list=0 # urns is a slice list
        
        # Get uris of slivers/slices from the urns list
        uris = [urn_to_uri(self.driver, urn) for urn in urns]
        
        if action in ['geni_start', 'start']:
            # Start sliver or slice
            # SLIVER
            if is_sliver_list:    
                for uri in uris:
                    self.driver.testbed_shell.update_sliver_state(uri, 'start')
                
                # Get slice uri of the sliver
                slice_uri = self.driver.testbed_shell.get_sliver_by(sliver_uri=uris[0])['slice']['uri']
                # Get slice dict
                slice = self.driver.testbed_shell.get_slice_by(slice_uri=slice_uri)
                # Change state of the slice if needed (lower than deploy)
                if slice['set_state'] in ['register','deploy']:
                    # Set slice state to 'deploy'
                    self.driver.testbed_shell.update_slice_state(slice_uri, 'start')  
                    
            # SLICE
            else:
                for uri in uris:
                    self.driver.testbed_shell.update_slice_state(uri, 'start')
                    # Update the state of all the slivers contained in the slice
                    # If the set_state of the sliver was lower, the changes in the slice would not affect its slivers 
                    slivers = self.driver.testbed_shell.get_slivers_by_slice(slice_uri=uri)
                    for sliver in slivers:
                        self.driver.testbed_shell.update_sliver_state(sliver['uri'], 'start')
        
        elif action in ['geni_restart', 'restart']:
            # Restart node that contains the slivers
            # SLIVER
            if is_sliver_list: 
                for uri in uris:
                    # Reboot node containing each sliver
                    node_uri = self.driver.testbed_shell.get_sliver_by(sliver_uri=uri)['node']['uri']
                    self.driver.testbed_shell.reboot_node(node_uri)
            # SLICE
            else:
                for uri in uris:
                    # Get nodes of the slice
                    nodes_of_slice = self.driver.testbed_shell.get_nodes_by_slice(slice_uri=uri)
                    # Reboot all the nodes of the slice
                    for node in nodes_of_slice:
                        self.driver.testbed_shell.reboot_node(node['uri'])
        
        elif action in ['geni_stop', 'stop']:
            # Not supported
            # Delete slivers/slices or set them to deploy?
            # SLIVER
            if is_sliver_list: 
                for uri in uris:
                    # Delete slivers in the list
                    #self.driver.testbed_shell.delete_sliver(uri)
                    # Set sliver state to deploy: 
                    self.driver.testbed_shell.update_sliver_state(uri, 'deploy')
            # SLICE
            else:
                for uri in uris:
                    # Delete slices in the list
                    #self.driver.testbed_shell.delete_slice(uri)
                    # Set sliver state to deploy: 
                    self.driver.testbed_shell.update_slice_state(uri, 'deploy')
                    
        # Return struct (geni_slivers field of Describe method)
        description = self.describe(urns, credentials, options)
        return description['geni_slivers']    
                
        # Prepare and return the struct (use describe function)   
        #version_manager = VersionManager()
        #rspec_version = version_manager.get_version('GENI 3'options['geni_rspec_version'])
        #return self.describe(urns, rspec_version, options=options)
    
        
    
    def delete(self, urns, credentials={}, options={}):
        '''
        Delete the named slivers, making them geni_unallocated
        The urns argument can be a list of slivers urns (belonging to the same slice)
        or a single slice urn, so the operation will affect all the slivers in the slice
        
        :param urns: list of slice URNs or sliver URNs that belong to the same slice, which will 
            be deleted
        :type urns: list of strings
        
        :param credentials: GENI credentials of the caller and slices 
        :type credentials: list
        
        :param options: various options. 
        :type options: dictionary
        
        :returns list of dicts of the slivers that have been deleted
            [
                {    geni_sliver_urn: string
                     geni_allocation_status: 'geni_unallocated'
                     geni_expires: string
                },
                ...
            ]
        :rtype list of dict
        
        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3#Delete
        
        '''
        # Get geni_best_effort option
        geni_best_effort = options.get('geni_best_effort', True)
        
        # Return list
        deleted_slivers = []
                
        # Discover if urns is a list of sliver urns or slice urns
        # SLIVER
        if type_of_urn(urns[0])=='sliver':
            # For each urn of the list
            for urn in urns:
                # Obtain sliver uri and complete return struct
                sliver_uri = urn_to_uri(self.driver, urn)
                slice_uri = self.driver.testbed_shell.get_sliver_by(sliver_uri=sliver_uri)['slice']['uri']
                expires_on = self.driver.testbed_shell.get_slice_by(slice_uri=slice_uri)['expires_on']
                deleted_sliver = dict([('geni_sliver_urn', urn), ('geni_allocation_status', 'geni_unallocated'), ('geni_expires', expires_on)])
                deleted_slivers.append(deleted_sliver)
                # Delete the sliver
                self.driver.testbed_shell.delete(sliver_uri)
        # SLICE
        elif type_of_urn(urns[0])=='slice':
            # For each slice urn of the list
            for urn in urns:
                slice_uri = urn_to_uri(self.driver, urn)
                expires_on = self.driver.testbed_shell.get_slice_by(slice_uri=slice_uri)['expires_on']
                slivers = self.driver.testbed_shell.get_slivers_by_slice(slice_uri=slice_uri)
                # For each sliver of the slice
                for sliver in slivers:
                    # Complete return struct
                    sliver_urn = slivername_to_urn(self.AUTHORITY, sliver['id'])
                    sliver_uri = urn_to_uri(self.driver, sliver_urn)
                    deleted_sliver = dict([('geni_sliver_urn', sliver_urn), ('geni_allocation_status', 'geni_unallocated'), ('geni_expires', expires_on)])
                    deleted_slivers.append(deleted_sliver)
                    # Delete the sliver
                    self.driver.testbed_shell.delete(sliver_uri)
        
        return deleted_slivers
          
    
    def shutdown(self, slice_urn, credentials={}, options={}):
        '''
        Perform an emeregency shutdown on the slivers in the given slive at this aggregate. 
        Resources should be taken offline such that experimenter access is cut off. 
        The slivers are shut down but remain available for further forensics.
        
        No direct translation to C-Lab. The function will set the set_state of the slice to Register,
        so the resources are reserved but offline. Therefore, all the slivers of the slice will eventually be
        in Registered state.
        
        :param slice_urn: URN of the slice whose slivers will be shutdown
        :type slice_urn: string
        
        :param credentials: GENI credentials of the caller and slices 
        :type credentials: list
        
        :param options: various options. 
        :type options: dictionary
        
        :return True
        :rtype boolean
        
        .. seealso:: http://groups.geni.net/geni/wiki/GAPI_AM_API_V3#Shutdown
        
        '''
        slice_uri = urn_to_uri(self.driver, slice_urn)
        self.driver.testbed_shell.update_slice_state(slice_uri, 'register')
        # Update the state of all the slivers contained in the slice
        # If the set_state of the sliver was lower, the changes in the slice would not affect its slivers 
        slivers = self.driver.testbed_shell.get_slivers_by_slice(slice_uri=slice_uri)
        for sliver in slivers:
            self.driver.testbed_shell.update_sliver_state(sliver['uri'], 'register')
        # Return true indicating success
        return 1
    
    
    ############################################################################################
    
    ##################################
    # AUXILIARY METHODS AM
    ##################################
    # Methods for AM based on 
    # URN/HRN (SFA standard)
    # GENI API
    ##################################
    
    def create_exp_data(self, exp_data_dir, geni_users_list):
        '''
        Method to create a experiment-data file that will be uploaded to the sliver during the 
        Provision (Deploy in SFA) phase. The experiment data consists of a directory structure
        with a script that will pushed the public keys of the SFA user to the created sliver when
        the sliver is started and available. 
        
        :param exp_data_dir: directory where the files and dirs for preparing the exp-data will be created
        :type exp_data_dir: string
        
        :param geni_users_list: list of dicts (geni_user type) containing the public keys of the SFA users 
        :type geni_users_list: list
        
        :return void
        :rtype None
        '''
        import os
        import subprocess
        
        # Directory and file for experiment data
        directory=os.path.join(exp_data_dir, 'temp/etc') 
        file_path =os.path.join(directory, 'rc.local')
        
        # Create directory if it does not exist yet
        if not os.path.exists(directory):
            logger.debug("DIRECTORY %s does not exist. Create!"%directory)
            os.makedirs(directory)
        
        # Prepare content of the /etc/rc.local script
        script_content= \
        '#!/bin/bash \n\
# \n\
# rc.local \n\
# \n\
# This script is executed at the end of each multiuser runlevel. \n\
# Make sure that the script will "exit 0" on success or any other \n\
# value on error. \n\
# \n\
# Script invoked by SFAWrap C-Lab. \n\
# The script is placed in the created slivers through an exp-data file uploaded to the sliver \n\
# The exp-data file is provided during the Deploy (Provision in SFA) phase. \n\
# The script adds the ssh-rsa public key of the SFA user that created the slice \n\
# to the /root/.ssh/authorized_keys file.  \n\
# The SFA will be able to ssh the created sliver with his public key. \n\
#  \n\
# Create .ssh directory if it does not exist \n\
mkdir -p /root/.ssh  \n\
# Append the ssh-rsa public keys of the user \n'
        
        # Add a line in the script for every key of every user that has to be pushed
        for user in geni_users_list:
            for key in user['keys']:
                script_content += 'echo "%s" >> /root/.ssh/authorized_keys \n'%key
        script_content += 'exit 0'
        logger.debug("create_exp_data. Script rc.local: \n%s"%script_content)
        
        # Create /etc/rc.local script 
        target = open (file_path, 'a')
        target.write(script_content)
        target.close()
        logger.debug("FILE %s created!"%file_path)
        
        # Permission to execute the file
        os.chmod(file_path, 0777)
        
        # Compress the sirectory structure to generate the exp-data file
        compressed_file_name = os.path.join(exp_data_dir, 'exp-data-temp.tgz')
        dir_to_compress = os.path.join(exp_data_dir, 'temp')
        cmd='tar -czvf %s --numeric-owner --group=root --owner=root -C %s .'%(compressed_file_name,dir_to_compress)
        subprocess.call(cmd, shell=True)
        logger.debug("DIRECTORY %s compressed to FILE %s"%(dir_to_compress,compressed_file_name))
        
        # return the path of the created compressed file
        return compressed_file_name
    
    
    def clean_exp_data(self, exp_data_dir):
        '''
        Method to clean the files generated by the method create_experiment_data.
        It is convinient to clean all these files because they are temporary. Once the create_experiment_data
        method returns, these files are not used anymore.
        
        :param exp_data_dir: directory where the files and dirs for preparing the exp-data will be created
        :type exp_data_dir: string
        
        :return void
        :rtype None
        '''
        import os
        import shutil
        
        # Compressed file and directory structure to delete
        compressed_file_name = os.path.join(exp_data_dir, 'exp-data-temp.tgz')
        dir_to_compress = os.path.join(exp_data_dir, 'temp')
        
        # remove compressed file and directory structure
        os.remove(compressed_file_name)
        shutil.rmtree(dir_to_compress)


        
    
    #####################################
    # GENI realted and translationmethods
    #####################################
    
    def clab_sliver_to_geni_sliver(self, sliver):
        '''
        Method that receives a clab-specific dictionary describing the sliver
        and returns a dictionary describing the sliver with geni format.
        Function used in Describe
        The fields of the geni_sliver:
            geni_sliver_urn
            geni_expires
            geni_allocation_status
            geni_operational_status
        
        :param sliver: C-lab specific dictionary of a sliver
        :type dict
        
        :returns GENI specific dictionary of a sliver
        :rtype dict
        '''
        # Get fields of the geni sliver dictionary
        
        # Get sliver urn
        geni_sliver_urn = slivername_to_urn(self.AUTHORITY, sliver['id'])
        
        # Get expiration date of the sliver (RFC 3339 format)
        # Get string containing the expires_on field of the slice containing the sliver
        sliver_expires_on = self.driver.testbed_shell.get_sliver_expiration(sliver=sliver)
        # Create a datetime object
        dt = self.get_datetime_from_clab_expires(sliver_expires_on)
        geni_expires = datetime_to_string(dt)
        
        # Get current state of the sliver
        sliver_current_state = self.driver.testbed_shell.get_sliver_current_state(sliver=sliver)
        
        # Fill geni states
        geni_allocation_status = self.clab_state_to_geni_allocation_state(sliver['set_state'])
        geni_operational_status = self.clab_state_to_geni_operational_state(sliver_current_state)
        logger.debug("CLAB_SLIVER_TO_GENI_SLIVER set_state: %s  - current state: %s - alloc: %s - op: %s"%(sliver['set_state'],sliver_current_state,geni_allocation_status,geni_operational_status))
        
        # Create and fill geni sliver dictionary
        geni_sliver = {'geni_sliver_urn':geni_sliver_urn, 'geni_expires':geni_expires, 
                       'geni_allocation_status':geni_allocation_status, 'geni_operational_status':geni_operational_status}
        logger.debug("RETURN GENI SLIVER in clab_sl_to_geni_sl: %s"%geni_sliver)
        return geni_sliver 
    
    
    def get_datetime_from_clab_expires(self, sliver_expires_on):
        '''
        Function to get a datetime object from the string parameter sliver_expires_on.
        
        :param sliver_expires_on: expiration time following the C-Lab format 'YYY-MM-DD'
        :type string
        
        :returns datetime object with the expiration date
        :type datetime
        '''
        year, month, day = sliver_expires_on.split('-')
        dt=datetime.datetime(int(year), int(month), int(day), 00, 00, 00)
        return dt
    
    
    def clab_node_is_geni_available(self, current_state):
        '''
        Function to check if a C-Lab node is in a GENI avaialable state
        
        :param current_state: C-Lab specific current state of a Node
        :type string
        
        :returns boolean indicating if the node is currently GENI availabe
        :rtype boolean
        '''
        if current_state == 'production': return 'true'
        else: return 'false'
                
 
 
    def clab_state_to_geni_boot_state(self, clab_state):
        '''
        Function to translate the clab-specific states of nodes to the standard geni boot states.
        
        :param clab_state: C-Lab specific state of Node
        :type string
        
        :returns GENI boot state
        :rtype string
        '''
        # NODE STATES 
        if clab_state in ['debug','safe','failure', 'offline', 'crashed']:
            # debug: the nodes has incomplete/invalid configuration
            # safe: complete/valid configuration but not available for hosting slivers
            # failure: node experimenting hw/sfw problems, not available for slivers
            return 'geni_unavailable'
        elif clab_state == 'production':
            # production: node running and available for slivers
            return 'geni_available'
    
    
    def clab_state_to_geni_allocation_state(self, clab_state):
        '''
        Function to translate the clab-specific states to the standard geni allocaiton states.
        
        :param clab_state: C-Lab specific state of Node/Slice/Sliver
        :type string
        
        :returns GENI allocation state
        :rtype string
        '''
        # NODE STATES 
        if clab_state in ['debug','safe','failure', 'offline', 'crashed']:
            # debug: the nodes has incomplete/invalid configuration
            # safe: complete/valid configuration but not available for hosting slivers
            # failure: node experimenting hw/sfw problems, not available for slivers
            return 'geni_unavailable'
        elif clab_state == 'production':
            # production: node running and available for slivers
            return 'geni_available'
        
        # SLICE/SLIVER STATES
    
        # NORMAL STATES
        elif clab_state in ['register', 'registered']:
            # register(ed): slice/sliver descriptions correct and  known by the server
            return 'geni_allocated'

        elif clab_state in ['deploy', 'deployed']:
            # deploy(ed): slice/slivers have requested resources allocated and data installed.
            return 'geni_provisioned'
            
        elif clab_state in ['start', 'started']:
            # start(ed): slice/slivers are to have their components started
            return 'geni_provisioned'
            
        elif clab_state in ['unknown', 'nodata', None]:
            return 'geni_unallocated'
        
        #TRANSITORY STATES
        elif clab_state in ['allocating', '(allocating)', '(allocate)']:
            # Transitory state that runs the allocate action
            return 'geni_unallocated'

        elif clab_state in ['deploying', '(deploying)']:
            # Transitory state that runs the deploy action
            return 'geni_allocated'
            
        elif clab_state in ['starting', '(starting)']:
            # Transitory state that runs the start action
            return 'geni_provisioned'
        
        # FAILURE STATES
        elif clab_state =='fail_alloc':
            # Transitory state that runs the allocate action
            return 'geni_unallocated'
            
        elif clab_state == 'fail_deploy':
            # Transitory state that runs the deploy action
            return 'geni_allocated'
            
        elif clab_state == 'fail_start':
            # Transitory state that runs the start action
            return 'geni_provisioned'
            
            
            
    def clab_state_to_geni_operational_state(self, clab_state):
        '''
        Function to translate the clab-specific states to the standard geni operational states.

        :param clab_state: C-Lab specific state of Node/Slice/Sliver
        :type string
        
        :returns GENI operational state
        :rtype string
        '''
        # NODE STATES 
        if clab_state in ['debug','safe','failure', 'offline', 'crashed']:
            # debug: the nodes has incomplete/invalid configuration
            # safe: complete/valid configuration but not available for hosting slivers
            # failure: node experimenting hw/sfw problems, not available for slivers
            return 'geni_unavailable'
        elif clab_state == 'production':
            # production: node running and available for slivers
            return 'geni_available'
        
        # SLICE/SLIVER STATES
        # Distinguish between Allocation state and Operational state
    
        # NORMAL STATES
        elif clab_state in ['register', 'registered']:
            # register(ed): slice/sliver descriptions correct and  known by the server
            return 'geni_notready'
            
        elif clab_state in ['deploy', 'deployed']:
            # deploy(ed): slice/slivers have requested resources allocated and data installed.
            return 'geni_notready'
            
        elif clab_state in ['start', 'started']:
            # start(ed): slice/slivers are to have their components started
            return 'geni_ready'
            
        elif clab_state in ['unknown', 'nodata', None]:
            return 'geni_pending_allocation'
        
        #TRANSITORY STATES
        elif clab_state in ['allocating', '(allocating)', '(allocate)']:
            # Transitory state that runs the allocate action
            return 'geni_pending_allocation'
            
        elif clab_state in ['deploying', '(deploying)']:
            # Transitory state that runs the deploy action
            return 'geni_notready'
            
        elif clab_state in ['starting', '(starting)']:
            # Transitory state that runs the start action
            return 'geni_configuring'
        
        # FAILURE STATES
        elif clab_state =='fail_alloc':
            # Transitory state that runs the allocate action
            return 'geni_failed'
            
        elif clab_state == 'fail_deploy':
            # Transitory state that runs the deploy action
            return 'geni_failed'
            
        elif clab_state == 'fail_start':
            # Transitory state that runs the start action
            return 'geni_failed'
            
    
        
    def get_nodes_by_geni_state(self, state=None):
        '''
        Function to get the Nodes from the controller. It supports the option to get only the nodes 
        that are in geni_available state. (production state in CLab)
        
        :param state: 'available' to specify that geni_available nodes will be got <optional>
        :type string
        
        :returns list of C-Lab dictionaries decscribing the nodes
        :rtype list of dict
        '''
        nodes = self.driver.testbed_shell.get_nodes()
        #if state and state=='available':
        nodes = [node for node in nodes if self.driver.testbed_shell.get_node_current_state(node=node)=='production']
            #nodes = [node for node in nodes if node['set_state']=='production' ]
        return nodes
        
            
    def get_slices_by_geni_state(self, state=None):
        '''
        Function to get the Slices from the controller. It supports the option to get only the slices 
        that are in geni_available state. (deployed, started current state in CLab)
        
        :param state: 'available' to specify that geni_available slices will be got <optional>
        :type string
        
        :returns list of C-Lab dictionaries decscribing the slices
        :rtype list of dict
        '''
        slices = self.driver.testbed_shell.get_slices()
        if state and state=='available':
            slices = [slice for slice in slices if slice['set_state'] in ['deploy','start']]
        return slices
    
    
            
        
    ########################################
    # RSPEC related and translation methods
    ########################################
    
    def clab_node_to_rspec_node(self, node, rspec_type, sliver={}, options={}):
        '''
        Translate the CLab-specific node dictionary to the standard Rspec format.
        The Rspec format used is v3 and it is augmented with specific fields from CLab.
        
        :param node: C-Lab specific Node dict OR uri of node 
        :type dict OR string
        
        :param options: various options
        :type dict
        
        :returns list of dictionaries containing the RSpec of the nodes
        :rtype list
        
        NOTE: this method is only used for generating the Advertisement RSpec in the listResources method
        '''    
        # If the argument is the node uri, obtain node dict
        if isinstance(node, str):
            node = self.driver.testbed_shell.get_node_by(node_uri=node)
            
        rspec_node = NodeElement()
        
        # Unicode normalize node name in case it contains special characters (no ascii chrarcters)
        node_name = unicode_normalize(node['name'])

        # DOES NOT MAKE SENSE. REQUEST RSPEC NEVER GENERATED BY WRAPPER
        if rspec_type == 'request':
            rspec_node['component_manager_id'] = hrn_to_urn(self.AUTHORITY, 'authority+cm') # urn:publicid:IDN+confine:clab+authority+cm
            rspec_node['exclusive'] = 'false'
            rspec_node['component_id'] = hostname_to_urn(self.AUTHORITY, node_name) # 'urn:publicid:IDN+confine:clab+node+MyNode'
            #rspec_node['client_id'] = node_name 
            rspec_node['component_name'] = node_name # pc160  
            rspec_node['authority_id'] = hrn_to_urn(self.AUTHORITY, 'authority+sa') #urn:publicid:IDN+confine:clab+authority+sa
            rspec_node['sliver_id'] = "URN OF THE SLIVER"
            
        elif rspec_type == 'advertisement':
            rspec_node['component_manager_id'] = hrn_to_urn(self.AUTHORITY, 'authority+cm') # urn:publicid:IDN+confine:clab+authority+cm
            rspec_node['component_id'] = hostname_to_urn(self.AUTHORITY, node_name) # 'urn:publicid:IDN+confine:clab+node+MyNode'
            rspec_node['component_name'] = node_name # pc160
            rspec_node['authority_id'] = hrn_to_urn(self.AUTHORITY, 'authority+sa') #urn:publicid:IDN+confine:clab+authority+sa  
            rspec_node['exclusive'] = 'false'
            
            node_current_state = self.driver.testbed_shell.get_node_current_state(node=node)
            rspec_node['available'] = self.clab_node_is_geni_available(node_current_state)
            rspec_node['boot_state'] = self.clab_state_to_geni_boot_state(node_current_state)
            rspec_node['hardware_types'] = [HardwareType({'name': node['arch']})]
            # Add INTERFACES
            rspec_node['interfaces'] = self.clab_node_interfaces_to_rspec_interfaces(node)
            rspec_node['sliver_type']='RD_sliver'
            
            # EXTENSION for C-Lab v1 RSpec
            # Group
            group = self.driver.testbed_shell.get_group_by(group_uri=node['group']['uri'])
            rspec_node['group'] = {'name': group['name'], 'id':str(group['id'])}
            # Island
            island = self.driver.testbed_shell.get_island_by(island_uri=node['island']['uri'])
            rspec_node['island'] = {'name': island['name'], 'id':str(island['id'])}
            # Network interfaces
            rspec_node['nodeInterfaces'] = self.clab_node_interfaces_to_clabv1rspec_interfaces(node)
            # Management network
            rspec_node['mgmt_net'] = {'addr':node['mgmt_net']['addr']}
            
            
        elif rspec_type == 'manifest':
            #rspec_node['client_id'] = node_name # 'MyNode'
            rspec_node['component_manager_id'] = hrn_to_urn(self.AUTHORITY, 'authority+cm') # urn:publicid:IDN+confine:clab+authority+cm
            rspec_node['exclusive'] = 'false'
            rspec_node['component_id'] = hostname_to_urn(self.AUTHORITY, node_name) # 'urn:publicid:IDN+confine:clab+node+MyNode'       
            #rspec_node['sliver_id'] = "URN OF THE SLIVER"
            rspec_node['component_name'] = node_name # pc160  
            rspec_node['authority_id'] = hrn_to_urn(self.AUTHORITY, 'authority+sa') #urn:publicid:IDN+confine:clab+authority+sa
            # Add SLIVERS
            rspec_node['slivers'] = self.clab_slivers_to_rspec_slivers(node)
            # Add SERVICES and LOGIN information
            rspec_node['services'] = [{'login':{'authentication':'ssh-keys', 'hostname':'sliver_ipv6', 'port':'22', 'username':'root'}}]
            # EXTENSION for C-Lab v1 RSpec
            # Group
            group = self.driver.testbed_shell.get_group_by(group_uri=node['group']['uri'])
            rspec_node['group'] = {'name': group['name'], 'id':str(group['id'])}
            # Island
            island = self.driver.testbed_shell.get_island_by(island_uri=node['island']['uri'])
            rspec_node['island'] = {'name': island['name'], 'id':str(island['id'])}
            # Network interfaces
            rspec_node['nodeInterfaces'] = self.clab_node_interfaces_to_clabv1rspec_interfaces(node)
            # Management network
            rspec_node['mgmt_net'] = {'addr':node['mgmt_net']['addr']}
            
        return rspec_node
    
    
    
    def clab_sliver_to_rspec_node(self, sliver, rspec_type, options={}):
        '''
        Translate the CLab-specific sliver dictionary to the standard Rspec format of node element.
        The Rspec format used is v3 and it is augmented with specific fields from CLab.
        
        :param node: C-Lab specific Sliver dict OR uri of sliver 
        :type dict OR string
        
        :param options: various options
        :type dict
        
        :returns list of dictionaries containing the RSpec of the nodes
        :rtype list
        '''    
        # If the argument is the node uri, obtain node dict
        if isinstance(sliver, str):
            sliver = self.driver.testbed_shell.get_sliver_by(sliver_uri=sliver)
        node = self.driver.testbed_shell.get_node_by(node_uri=sliver['node']['uri'])
        rspec_node = NodeElement()
        
        # Unicode normalize node name in case it contains special characters (no ascii chrarcters)
        node_name = unicode_normalize(node['name'])

        # DOES NOT MAKE SENSE. REQUEST RSPEC NEVER GENERATED BY WRAPPER
        if rspec_type == 'request':
            rspec_node['client_id'] = sliver['properties']['sfa_client_id'] 
            rspec_node['component_manager_id'] = hrn_to_urn(self.AUTHORITY, 'authority+cm') # urn:publicid:IDN+confine:clab+authority+cm
            rspec_node['component_id'] = hostname_to_urn(self.AUTHORITY, node_name) # 'urn:publicid:IDN+confine:clab+node+MyNode'
            rspec_node['component_name'] = node_name # pc160  
            rspec_node['exclusive'] = 'false'
            rspec_node['authority_id'] = hrn_to_urn(self.AUTHORITY, 'authority+sa') #urn:publicid:IDN+confine:clab+authority+sa
            rspec_node['sliver_id'] = slivername_to_urn(self.AUTHORITY, sliver['id'])
            
        elif rspec_type == 'advertisement':
            rspec_node['component_manager_id'] = hrn_to_urn(self.AUTHORITY, 'authority+cm') # urn:publicid:IDN+confine:clab+authority+cm
            rspec_node['component_id'] = hostname_to_urn(self.AUTHORITY, node_name) # 'urn:publicid:IDN+confine:clab+node+MyNode'
            rspec_node['component_name'] = node_name # pc160  
            rspec_node['authority_id'] = hrn_to_urn(self.AUTHORITY, 'authority+sa') #urn:publicid:IDN+confine:clab+authority+sa
            rspec_node['exclusive'] = 'false'
            node_current_state = self.driver.testbed_shell.get_node_current_state(node=node)
            rspec_node['available'] = self.clab_node_is_geni_available(node_current_state)
            rspec_node['boot_state'] = self.clab_state_to_geni_boot_state(node_current_state)
            rspec_node['hardware_types'] = [HardwareType({'name': node['arch']})]
            rspec_node['sliver_type']='RD_sliver'
            # Add INTERFACES
            rspec_node['interfaces'] = self.clab_node_interfaces_to_rspec_interfaces(node)
        
        elif rspec_type == 'manifest':
            rspec_node['client_id'] = sliver['properties']['sfa_client_id']
            rspec_node['component_manager_id'] = hrn_to_urn(self.AUTHORITY, 'authority+cm') # urn:publicid:IDN+confine:clab+authority+cm
            rspec_node['component_id'] = hostname_to_urn(self.AUTHORITY, node_name) # 'urn:publicid:IDN+confine:clab+node+MyNode'
            rspec_node['component_name'] = node_name # pc160  
            rspec_node['authority_id'] = hrn_to_urn(self.AUTHORITY, 'authority+sa') #urn:publicid:IDN+confine:clab+authority+sa
            rspec_node['exclusive'] = 'false'
            rspec_node['sliver_id'] = slivername_to_urn(self.AUTHORITY, sliver['id'])          
            # Add SLIVERS  (contains EXTENSION for CLAb v1 RSpec)
            rspec_node['slivers'] = self.clab_sliver_to_rspec_sliver(sliver)
            
            if self.driver.testbed_shell.get_sliver_set_state(sliver=sliver) in ['deploy', 'start']:
                # Add SERVICES and LOGIN information
                ipv6_sliver_addr = self.driver.testbed_shell.get_ipv6_sliver_address(sliver=sliver)
                rspec_node['services'] = [{'login':{'authentication':'ssh-keys', 'hostname':ipv6_sliver_addr, 'port':'22', 'username':'root'}}]
            # EXTENSION for C-Lab v1 RSpec
            # Group
            group = self.driver.testbed_shell.get_group_by(group_uri=node['group']['uri'])
            rspec_node['group'] = {'name': group['name'], 'id':str(group['id'])}
            # Island
            island = self.driver.testbed_shell.get_island_by(island_uri=node['island']['uri'])
            rspec_node['island'] = {'name': island['name'], 'id':str(island['id'])}
            # Network interfaces
            rspec_node['nodeInterfaces'] = self.clab_node_interfaces_to_clabv1rspec_interfaces(node)
            # Management network
            rspec_node['mgmt_net'] = {'addr':node['mgmt_net']['addr']}
        return rspec_node
    
    
    
    def clab_node_interfaces_to_rspec_interfaces(self, node, options={}):
        '''
        Translate a list of CLab-specific interfaces dictionaries of a Node 
        to a list of standard Rspec interfaces.
        
        :param node: C-Lab specific dict of a node
        :type dict
        
        :param options: various options
        :type dict
        
        :returns list of dictionaries containing the RSpec of the node interfaces
        :rtype list
        ''' 
        rspec_interfaces = []
        
        # LOCAL IFACE FIELD REMOVED IN THE CONTROLLER UPGRADE (28/05/2014)
        #local_iface = node['local_iface']
        direct_ifaces = node['direct_ifaces']
        
        # Unicode normalize node name in case it contains special characters (no ascii chrarcters)
        node_name = unicode_normalize(node['name'])
        
        #if local_iface:
        #    client_id = '%s:%s'%(node_name, local_iface)
        #    rspec_local_iface = dict([('interface_id', local_iface), ('node_id', node['id']), 
        #                              ('role', 'local_iface'), ('client_id', client_id)])
        #    rspec_interfaces.append(rspec_local_iface)
        
        if direct_ifaces:
            for direct_iface in direct_ifaces:
                rspec_direct_iface = dict([('component_id', direct_iface)])
                rspec_interfaces.append(rspec_direct_iface)
                    
        return rspec_interfaces
    
    
    def clab_sliver_interfaces_to_rspec_interfaces(self, sliver, options={}):
        '''
        Translate a list of CLab-specific interfaces dictionaries of a Sliver 
        to a list of standard Rspec interfaces.
        
        :param sliver: C-Lab specific dictionary of Sliver
        :type dict
        
        :param options: various options
        :type dict
         
        :returns list of dictionaries containing the RSpec of the sliver interfaces
        :rtype list
        ''' 
        rspec_interfaces = []
        for interface in sliver['interfaces']:
            client_id = '%s:%s'%(sliver['id'],interface['name'])
            rspec_iface = dict([('interface_id', interface['nr']), ('role', interface['type']), ('client_id', client_id)])
            rspec_interfaces.append(rspec_iface)
        return rspec_interfaces
    
    def clab_node_interfaces_to_clabv1rspec_interfaces(self, node, options={}):
        '''
        Translate a list of CLab-specific interfaces dictionaries of a Node 
        to a list of interfaces for the CLabv1 Rspec.
        
        :param node: C-Lab specific dict of a node
        :type dict
        
        :param options: various options
        :type dict
        
        :returns list of dictionaries containing the CLabv1RSpec of the node interfaces
        :rtype list
        ''' 
        rspec_interfaces = []
        
        # LOCAL IFACE FIELD REMOVED IN THE CONTROLLER UPGRADE (28/05/2014)
        #local_iface = node['local_iface']
        direct_ifaces = node['direct_ifaces']
        
        #if local_iface:
        #    rspec_local_iface = dict([('name', local_iface), ('type', 'direct')])
        #    rspec_interfaces.append(rspec_local_iface)
        
        if direct_ifaces:
            for direct_iface in direct_ifaces:
                rspec_direct_iface = dict([('name', direct_iface), ('type', 'direct')])
                rspec_interfaces.append(rspec_direct_iface)
                    
        return rspec_interfaces
    
    
    def clab_sliver_interfaces_to_clabv1rspec_interfaces(self, sliver, options={}):
        '''
        Translate a list of CLab-specific interfaces dictionaries of a Sliver 
        to a list of interfaces for the CLabv1RSpec.
        
        :param sliver: C-Lab specific dictionary of Sliver
        :type dict
        
        :param options: various options
        :type dict
         
        :returns list of dictionaries containing the CLabv1RSpec of the sliver interfaces
        :rtype list
        ''' 
        rspec_interfaces = []
        for interface in sliver['interfaces']:
            rspec_iface = dict([('name', interface['name']), ('type', interface['type']), ('nr', str(interface['nr']))])
            rspec_interfaces.append(rspec_iface)
        return rspec_interfaces


    def clab_sliver_to_rspec_sliver(self, sliver, options={}):
        '''
        Translate a list of Clab-specific sliver dictionary  
        to a standard Rspec sliver.
        
        :param node: C-Lab specific dictionary of Node
        :type dict
        
        :param options: various options
        :type dict
         
        :returns list of dictionaries containing the RSpec of the slivers 
        :rtype list
        '''
        disk_image = self.clab_template_to_rspec_disk_image(sliver)
        rspec_sliver = dict([('sliver_id', sliver['id']), #('client_id', sliver['id']), 
                            ('name', sliver['id']), ('type', 'RD_Sliver'), ('disk_image', disk_image)])
        
        # EXTENSION FOR CLab v1 RSpec
        # Template
        template_uri = sliver.get('template')
        if not template_uri:
            template_uri = self.driver.testbed_shell.get_slice_by(slice_uri=sliver['slice']['uri'])['template']
        template = self.driver.testbed_shell.get_template_by(template_uri=template_uri['uri'])
        rspec_sliver['template'] = {'name':template['name'], 'id':template['id'], 'type':template['type']}
        # Interfaces 
        rspec_sliver['interfaces'] = sliver['interfaces'] 
        
        return rspec_sliver 
    
    
    
    
    def clab_slivers_to_rspec_slivers(self, node, options={}):
        '''
        Translate a list of CLab-specific slivers dictionaries of a Node 
        to a list of standard Rspec slivers.
        
        :param node: C-Lab specific dictionary of Node
        :type dict
        
        :param options: various options
        :type dict
         
        :returns list of dictionaries containing the RSpec of the slivers 
        :rtype list
        '''
        rspec_slivers = []
        slivers = node['slivers']
        for clab_sliver in slivers:
            sliver = self.driver.testbed_shell.get_sliver_by(sliver_uri=clab_sliver['uri'])
            disk_image = self.clab_template_to_rspec_disk_image(sliver)
            rspec_sliver = dict([('sliver_id', sliver['id']), #('client_id', sliver['id']), 
                                ('name', sliver['id']), ('type', 'RD_Sliver'), ('disk_image', disk_image)])
            
            # EXTENSION FOR CLab v1 RSpec
            # Template
            # Interfaces
            
            rspec_slivers.append(rspec_sliver)
            
        return rspec_slivers  
        
    
    def clab_template_to_rspec_disk_image(self, sliver):
        '''
        Translate a CLab-specific template dictionary to 
        standard RSpec disk_image dict.

        :param node: C-Lab specific dictionary of Sliver
        :type dict
         
        :returns dictionary containing the Rspec specific disk image 
        :rtype dict
        '''  
        # The filed sliver['template'] or slice['template'] contains the uri of the template
        template = sliver['template']
        if not template or template in ['null', '(from slice)', '(from sliver defaults)', "(from slice's sliver defaults)"]: 
            # Get template_uri from the slice
            template_uri = self.driver.testbed_shell.get_slice_by(slice_uri=sliver['slice']['uri'])['template']['uri']
        else: 
            # Get the template uri from the dictionary of the sliver
            template_uri = template['uri']
        # Retrieve the template object from the template_uri
        template = self.driver.testbed_shell.get_by_uri(template_uri)
        
        template_rspec = dict([('name', template['name']), ('os', template['type']), ('description', template['description']) ])
        return template_rspec                        
        
    
    
    
    
    
    
    
            

    
   
    
       



