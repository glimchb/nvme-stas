# Copyright (c) 2021, Dell Inc. or its subsidiaries.  All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See the LICENSE file for details.
#
# This file is part of NVMe STorage Appliance Services (nvme-stas).
#
# Authors: Martin Belanger <Martin.Belanger@dell.com>

''' Configuration for staf/stac
'''
import os
import re
import sys
import configparser

#*******************************************************************************

class OrderedMultisetDict(dict):
    ''' This class is used to change the behavior of configparser.ConfigParser
        and allow multiple configuration parameters with the same key. The
        result is a list of values.
    '''
    def __setitem__(self, key, value):
        if key in self and isinstance(value, list):
            self[key].extend(value)
        else:
            super().__setitem__(key, value)

    def __getitem__(self, key):
        value = super().__getitem__(key)

        if isinstance(value, str):
            return value.split('\n')

        return value

#*******************************************************************************

TOKEN_RE  = re.compile(r'\s*;\s*')
OPTION_RE = re.compile(r'\s*=\s*')
def parse_controller(controller):
    ''' @brief Parse a "controller" entry. Controller entries are strings
               composed of several configuration parameters delimited by
               semi-colons. Each configuration parameter is specified as a
               "key=value" pair.
        @return A dictionary of key-value pairs.
    '''
    options = dict()
    tokens  = TOKEN_RE.split(controller)
    for token in tokens:
        if token:
            try:
                option,val = OPTION_RE.split(token)
                options[option] = val
            except ValueError:
                pass

    return options

#*******************************************************************************

class Configuration:
    ''' Read and cache configuration file.
    '''
    def __init__(self, conf_file):
        self._defaults = {
            ('Global', 'tron'): 'false',
            ('Global', 'persistent-connections'): 'true',
            ('Global', 'hdr-digest'): 'false',
            ('Global', 'data-digest'): 'false',
            ('Global', 'kato'): None,
            ('Global', 'ignore-iface'): 'false',
            ('Global', 'ip-family'): 'ipv4+ipv6',
            ('Service Discovery', 'zeroconf'): 'enabled',
            ('Controllers', 'controller'): list(),
            ('Controllers', 'blacklist'): list(),
        }
        self._conf_file = conf_file
        self.reload()

    def reload(self):
        ''' @brief Reload the configuration file.
        '''
        self._config = self.read_conf_file()

    @property
    def conf_file(self):
        return self._conf_file

    @property
    def tron(self):
        ''' @brief return the "tron" config parameter
        '''
        return self.__get_bool('Global', 'tron')

    @property
    def hdr_digest(self):
        ''' @brief return the "hdr-digest" config parameter
        '''
        return self.__get_bool('Global', 'hdr-digest')

    @property
    def data_digest(self):
        ''' @brief return the "data-digest" config parameter
        '''
        return self.__get_bool('Global', 'data-digest')

    @property
    def persistent_connections(self):
        ''' @brief return the "persistent-connections" config parameter
        '''
        return self.__get_bool('Global', 'persistent-connections')

    @property
    def ignore_iface(self):
        ''' @brief return the "ignore-iface" config parameter
        '''
        return self.__get_bool('Global', 'ignore-iface')

    @property
    def ip_family(self):
        ''' @brief return the "ip-family" config parameter.
            @rtype tuple
        '''
        family = self.__get_value('Global', 'ip-family')[0]

        if family == 'ipv4':
            return (4, )
        if family == 'ipv6':
            return (6, )

        return (4, 6)

    @property
    def kato(self):
        ''' @brief return the "kato" config parameter
        '''
        kato = self.__get_value('Global', 'kato')[0]
        return None if kato is None else int(kato)

    def get_controllers(self):
        ''' @brief Return the list of controllers in the config file.
                   Each controller is in the form of a dictionary as follows.
                   Note that some of the keys are optional.
                   {
                       'transport':   [TRANSPORT],
                       'traddr':      [TRADDR],
                       'trsvcid':     [TRSVCID],
                       'host-traddr': [TRADDR],
                       'host-iface':  [IFACE],
                       'subsysnqn':   [NQN],
                   }
        '''
        controller_list = self.__get_value('Controllers', 'controller')
        controllers = [ parse_controller(controller) for controller in controller_list ]
        for controller in controllers:
            try:
                # replace 'nqn' key by 'subsysnqn', if present.
                controller['subsysnqn'] = controller.pop('nqn')
            except KeyError:
                pass
        return controllers

    def get_blacklist(self):
        ''' @brief Return the list of blacklisted controllers in the config file.
                   Each blacklisted controller is in the form of a dictionary
                   as follows. All the keys are optional.
                   {
                       'transport':  [TRANSPORT],
                       'traddr':     [TRADDR],
                       'trsvcid':    [TRSVCID],
                       'host-iface': [IFACE],
                       'subsysnqn':  [NQN],
                   }
        '''
        controller_list = self.__get_value('Controllers', 'blacklist')
        blacklist = [ parse_controller(controller) for controller in controller_list ]
        for controller in blacklist:
            controller.pop('host-traddr', None) # remove host-traddr
            try:
                # replace 'nqn' key by 'subsysnqn', if present.
                controller['subsysnqn'] = controller.pop('nqn')
            except KeyError:
                pass
        return blacklist

    def get_stypes(self):
        ''' @brief Get the DNS-SD/mDNS service types.
        '''
        return ['_nvme-disc._tcp'] if self.zeroconf_enabled() else list()

    def zeroconf_enabled(self):
        return self.__get_value('Service Discovery', 'zeroconf')[0] == 'enabled'

    def read_conf_file(self):
        ''' @brief Read the configuration file if the file exists.
        '''
        config = configparser.ConfigParser(default_section=None, allow_no_value=True, delimiters=('='),
                                           interpolation=None, strict=False, dict_type=OrderedMultisetDict)
        if os.path.isfile(self._conf_file):
            config.read(self._conf_file)
        return config

    def __get_bool(self, section, option):
        return self.__get_value(section, option)[0] == 'true'

    def __get_value(self, section, option):
        try:
            value = self._config.get(section=section, option=option)
        except (configparser.NoSectionError, configparser.NoOptionError, KeyError):
            value = self._defaults.get((section, option), [])
            if not isinstance(value, list):
                value = [value]
        return value if value is not None else list()

#*******************************************************************************

class SysConfiguration:
    ''' Read and cache the host configuration file.
    '''
    def __init__(self, conf_file:str):
        self._conf_file = conf_file
        self.reload()

    def reload(self):
        ''' @brief Reload the configuration file.
        '''
        self._config = self.read_conf_file()

    def as_dict(self):
        return {
            'hostnqn': self.hostnqn,
            'hostid':  self.hostid,
            'symname': self.hostsymname,
        }

    @property
    def hostnqn(self):
        ''' @brief return the host NQN
            @return: Host NQN
            @raise: Host NQN is mandatory. The program will terminate if a
                    Host NQN cannot be determined.
        '''
        try:
            value = self.__get_value('Host', 'nqn', '/etc/nvme/hostnqn')
        except FileNotFoundError as ex:
            sys.exit('Error reading mandatory Host NQN (see stasadm --help): %s', ex)

        if not value.startswith('nqn.'):
            sys.exit('Error Host NQN "%s" should start with "nqn."', value)

        return value

    @property
    def hostid(self):
        ''' @brief return the host ID
            @return: Host ID
            @raise: Host ID is mandatory. The program will terminate if a
                    Host ID cannot be determined.
        '''
        try:
            value = self.__get_value('Host', 'id', '/etc/nvme/hostid')
        except FileNotFoundError as ex:
            sys.exit('Error reading mandatory Host ID (see stasadm --help): %s', ex)

        return value

    @property
    def hostsymname(self):
        ''' @brief return the host symbolic name (or None)
            @return: symbolic name or None
        '''
        try:
            value = self.__get_value('Host', 'symname')
        except FileNotFoundError as ex:
            LOG.warning('Error reading host symbolic name (will remain undefined): %s', ex)
            value = None

        return value

    def read_conf_file(self):
        ''' @brief Read the configuration file if the file exists.
        '''
        config = configparser.ConfigParser(default_section=None, allow_no_value=True, delimiters=('='),
                                           interpolation=None, strict=False)
        if os.path.isfile(self._conf_file):
            config.read(self._conf_file)
        return config

    def __get_value(self, section, option, default_file=None):
        ''' @brief A configuration file consists of sections, each led by a
                   [section] header, followed by key/value entries separated
                   by a equal sign (=). This method retrieves the value
                   associated with the key @option from the section @section.
                   If the value starts with the string "file://", then the value
                   will be retrieved from that file.

            @param section:      Configuration section
            @param option:       The key to look for
            @param default_file: A file that contains the default value

            @return: On success, the value associated with the key. On failure,
                     this method will return None is a default_file is not
                     specified, or will raise an exception if a file is not
                     found.

            @raise: This method will raise the FileNotFoundError exception if
                    the value retrieved is a file that does not exist.
        '''
        try:
            value = self._config.get(section=section, option=option)
            if not value.startswith('file://'):
                return value
            file = value[7:]
        except (configparser.NoSectionError, configparser.NoOptionError, KeyError):
            if default_file is None:
                return None
            file = default_file

        with open(file) as f:
            return f.readline().split()[0]
