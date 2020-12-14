#!/usr/bin/python

from __future__ import (absolute_import, division, print_function)
import sys
import splunklib.six as six
import urllib
from xml.etree import ElementTree
import getpass

__metaclass__ = type

DOCUMENTATION = r'''
---
module: splunk_clients

short_description: Ansible module designed to add clients into a server class on a Splunk Deployment Server instance.

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "1.0.0"

description: Module will need the splunk instance (hostname or ip address, whatever your ansible machine is able to resolve), the server class name, and the list of clients to be added.

options:
    deployment_server:
        description: The splunk deployment server instance.
        required: true
        type: str
    username:
        description: User that makes API rest calls in Splunk
        required: true
        type: str
    password:
        description: Password to make API rest calls
        requiretd: true
        type: str
    server_class:
        description: The server class that's going to receive new clients
        required: true
        type: str
    clients:
        description: The list of hosts to be added as new clients
        required: true
        type: list
# Specify this value according to your collection
# in format of namespace.collection.doc_fragment_name
extends_documentation_fragment:
    - marceloapps.splunk_modules.splunk_clients

author:
    - Marcelo Arakaki (@marceloapps)
'''

EXAMPLES = r'''
# Pass in a message
- name: Add new clients to CLASS_FWRD_TEST 
  marceloapps.splunk_modules.splunk_clients:
    deployment_server: 192.168.0.10
    username: admin
    password: pwd
    server_class: CLASS_FWRD_TEST
    clients:
        - 127.0.0.1
        - 127.0.0.2
        - 127.0.0.3
'''

RETURN = r'''
# These are examples of possible return values, and in general should use other names for return values.
original_message:
    description: Clients added to the serverclass.
    type: str
    returned: always
    sample: 'Clients added to the serverclass: Test'
message:
    description: The output message that the test module generates.
    type: str
    returned: always
    sample: 'Good job!'
'''

from ansible.module_utils.basic import AnsibleModule

GLOBAL_SESSION_KEY = ""
GLOBAL_DEPLOYMENT = ""
GLOBAL_CLIENTS = []

def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        deployment_server=dict(type='str', required=True),
        username=dict(type='str', required=True),
        password=dict(type='str', required=True),
        server_class=dict(type='str', required=True),
        clients=dict(type='list', required=True)
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
        original_message='',
        message=''
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # fill some global variables
    GLOBAL_DEPLOYMENT = module.params['deployment_server']
    GLOBAL_CLIENTS = module.params['clients']
    GLOBAL_SESSION_KEY = get_sessionKey(module.params['username'], module.params['password'], module.params['deployment_server'])

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    # manipulate or modify the state as needed (this is going to be the
    # part where your module will do what it needs to do)
    result['original_message'] = 'Clients added to following server class: ' + module.params['server_class']
    result['message'] = 'Good job!'

    # HERE GOES NOTHING =)
    try:
        if not serverclass_exists(module.params['server_class']):
            #parameter indicates if method should create a new server class
            manage_serverclass(True)
        else:
            #passing False will instruct the method to UPDATE the server class
            manage_serverclass(False)

        #serverclass reload and we are done! =)

    except:
        module.fail_json(msg='Request failed', **result)

    # all went well, time to exit this execution
    module.exit_json(**result)


def main():
    sys.path.append('splunk-sdk-python-1.6.14')
    run_module()

#this method will retreive sessionKey to use in next API calls according to username/password
def get_sessionKey(username, password, deployment_server):
    connection = six.moves.http_client.HTTPSConnection(deployment_server, 8089)
    body = urllib.urlencode({'username': username, 'password': password})

    headers =   {'Content-Type': "application/x-www-form-urlencoded",
                 'Host': deployment_server
                }    

    connection.request("POST", "/services/auth/login", body, headers)
    response = connection.getresponse()
    content = response.read()
    connection.close()   

    session_key = ElementTree.XML(content).findtext("./sessionKey")
    return session_key

#method tries to find serverclass in the deployment server and return a boolean
def serverclass_exists(server_class):
    connection = six.moves.http_client.HTTPSConnection(GLOBAL_DEPLOYMENT, 8089)
    headers = {'Content-Type': "application/x-www-form-urlencoded",
               'Host': GLOBAL_DEPLOYMENT,
               'Authorization': "Splunk %s" % GLOBAL_SESSION_KEY
              }

    connection.request("GET", "/services/deployment/server/serverclasses/" + server_class, "", headers)
    response = connection.getresponse()
    connection.close() 

    if response.status == 200:
        return True
    else:
        return False

#method to create or update a serverclass, adding new clients to the list
def manage_serverclass(create, server_class):
    url = "/services/deployment/server/serverclasses/"
    whitelist_size = 0

    if not create:
        url = url + server_class
        whitelist_size = serverclass_client_list(server_class)

    connection = six.moves.http_client.HTTPSConnection(GLOBAL_DEPLOYMENT, 8089)
    headers = {'Content-Type': "application/x-www-form-urlencoded",
               'Host': GLOBAL_DEPLOYMENT,
               'Authorization': "Splunk %s" % GLOBAL_SESSION_KEY
              }
    body =  urllib.urlencode(post_serverclass_body(whitelist_size))

    connection.request("POST", url, body, headers)
    response = connection.getresponse()
    connection.close()

    if response.status == 200:
        reload_serverclass(server_class)

# method will return the whitelist-size of a serverclass, if it doesn't find any, will return 0
# we can improve it by returning the list of clients so we don't add new ones unnecessarily
def serverclass_client_list(server_class):
    connection = six.moves.http_client.HTTPSConnection(GLOBAL_DEPLOYMENT, 8089)
    headers = {'Content-Type': "application/x-www-form-urlencoded",
               'Host': GLOBAL_DEPLOYMENT,
               'Authorization': "Splunk %s" % GLOBAL_SESSION_KEY
              }

    connection.request("GET", "/services/deployment/server/serverclasses/" + server_class, "", headers)
    response = connection.getresponse()
    content = response.read()
    connection.close() 

    if response.status == 200:
        whitelist_count = ElementTree.XML(content).findtext("./whitelist-size")
    else:
        whitelist_count = 0

    return whitelist_count

# method will put together the body needed to add new clients on Splunk
def post_serverclass_body(whitelist_size):
    body = {"restartSplunkd": "True", "continueMatching": "True"}
    for client in GLOBAL_CLIENTS:
        key = "whitelist." + str(whitelist_size)
        body.update({key: client})
        whitelist_size += 1

    return body

def reload_serverclass(server_class):
    connection = six.moves.http_client.HTTPSConnection(GLOBAL_DEPLOYMENT, 8089)
    headers = {'Content-Type': "application/x-www-form-urlencoded",
               'Host': GLOBAL_DEPLOYMENT,
               'Authorization': "Splunk %s" % GLOBAL_SESSION_KEY
              }

    body = urllib.urlencode({"serverclass": server_class})

    connection.request("POST", "/services/deployment/server/config/_reload", body, headers)
    response = connection.getresponse()
    content = response.read()
    connection.close()    

if __name__ == '__main__':
    main()