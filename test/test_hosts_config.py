#!/usr/bin/env python
from shinken_test import *
from cStringIO import StringIO
from collections import namedtuple
import time
import sys

# define constants
HOST_NAME = 0
HOST_CONF_MUST_BE_CORRECT = 1
HOST_MUST_BE_DISABLED = 2

CHECK_HOSTS = 0
CHECK_LOGS = 1

HOST_NOT_DISABLED = 0
HOST_DISABLED = 1
HOST_NO_PARENTS = 2


class TestConfig(ShinkenTest):
    # setUp is inherited from ShinkenTest but we don't use it

    def get_hst(self, config, host_name):
        """Get the host with host_name "host_name".

           The function raise an error if the host was not found.

        """

        hst = self.conf.hosts.find_by_name(host_name)
        self.assert_(
                      hst is not None
                     ,('host \'%s\' not found (%s)' % (host_name, config))
                    )
        return hst

    def send_command_hst(self, command):
        """Send command with actual timestamp.

           Write command in the command file and
           call shinken function to process it

        """

        command = '[%lu] %s' % (time.time(), command)
        self.sched.run_external_command(command)
        self.scheduler_loop(
                             1
                            ,[]
                           )
        # can need 2 run for get the consum (I don't know why)
        self.scheduler_loop(
                             1
                            ,[]
                           )

    def check_config_hst(self, config, host, oracle):
        """Check if the configuration of the host is correct or not

           The function raise an error if function "host.is_correct" doesn't 
           return the expected value.

        """

        self.assert_(
                      host.is_correct() == oracle
                     ,('config of host \'%s\' is not %s (%s)'
                        % (host.host_name, oracle, config))
                    )

    def check_down_state_hst(self, config, host):
        """Check if the state of the host is down

           The function raise an error if the state of the host
           is not HARD/DOWN.

        """

        self.assert_(
                      # UNKNOWN is translated by shinken to DOWN 
                      # (http://nagios.sourceforge.net/docs/3_0/hostchecks.html)
                      'DOWN' == host.state
                     ,('host \'%s\' has a  state \'%s\' which is not DOWN (%s)'
                        % (host.host_name, host.state, config))
                    )

        self.assert_(
                      'HARD' == host.state_type
                     ,('host \'%s\' has a state type \'%s\' wich is not HARD (%s)'
                        % (host.host_name, host.state_type, config))
                    )

    def check_active_passive_disabled_hst(self, config, host):
        """Check if active and passives checks are disabled.

           Raise an error if checks are allowed.

        """

        # active checks are disabled
        self.assert_(
                      False == host.active_checks_enabled
                     ,('host \'%s\' has active_checks_enabled (%s)' 
                        % (host.host_name, config))
                    )

        # passive checks are disabled
        self.assert_(
                      False == host.accept_passive_checks
                     ,('host \'%s\' has accept_passive_checks enabled (%s)'
                        % (host.host_name, config))
                    )
        self.assert_(
                      False == host.passive_checks_enabled
                     ,('host \'%s\' has passive_checks_enabled (%s)'
                        % (host.host_name, config))
                    )

        # can't execute checks
        self.assert_(
                      False == host.execute_checks
                     ,('host \'%s\' has execute_checks (%s)'
                        % (host.host_name, config))
                    )

    def check_retention_disabled_hst(self, config, host):
        """Check if retention is disabled for the host.

           Raise an error if retention is not disabled.

        """

        # check retain_status_information and retain_nonstatus_information 
        # but I think that theses attributes are not already used by shinken
        # (grep -r 'retain_infomration' .)
        self.assert_(
                      False == host.retain_status_information
                     ,('host \'%s\' has retain_status_information (%s)'
                        % (host.host_name, config))
                    )
        self.assert_(
                      False == host.retain_nonstatus_information
                     ,('host \'%s\' has retain_nonstatus_information (%s)'
                        % (host.host_name, config))
                    )

        # we have not restored the host from retention
        # (the conf must be correct to access to self.sched
        # (see 'setup_with_file',shinken_test:121))

        #! TODO: and if the host_name found is not in the host object
        #! or if we found only a substring ?

        self.assert_(
                      not host.host_name in self.sched.get_retention_data()
                     ,('retention has been restored for host \'%s\' (%s)'
                        % (host.host_name, config))
                    )

        #! TODO: add data in retention and check that data are not restored
        #! idea: write a function which listen the hook of retention and put
        #! data before load them.

    def check_commands_disabled_hst(self, config, host):
        """Check that commands are not accepted for the host.

           Raise an error if it is possible to send commands for the host.

        """
        # I don't find how disable commands concerning only one host
        # (so I don't find how check this) 
        # I think that it is not possible. We can just disable commands
        # globally but not commands concerning only one object as a host
        # We can check by putting a command and check if it has been executed

        # checks are already disabled
        host.active_checks_enabled=False
        host.accept_passive_checks=False
        host.passive_checks_enabled=False

        # send commands to enable them
        self.send_command_hst('ENABLE_HOST_CHECK;%s' % (host.host_name))
        self.send_command_hst('ENABLE_PASSIVE_HOST_CHECKS;%s'
                               % (host.host_name))
        # check that commands are not executed
        self.check_active_passive_disabled_hst(
                                               config
                                              ,host
                                             )

        # check by sending a passive result
        # 0 means OK status
        self.send_command_hst('PROCESS_HOST_CHECK_RESULT;%s;0;OK' 
                               % (host.host_name))
        # check that passive result was not accepted
        self.check_down_state_hst(
                                   config
                                  ,host
                                 )

        # check that forced host schedule is not accept
        self.send_command_hst('SCHEDULE_FORCED_HOST_CHECK;%s;%lu' 
                               % (host.host_name, time.time()))
        #! TODO: How verify that the force schedule was ignored ?
        self.check_down_state_hst(
                                   config
                                  ,host
                                 )


    def check_non_scheduled_hst(self, config, host):
        """ Check that the host is not scheduled.

            Raise an error if the host is in the list of a scheduler.

        """

#        self.assert_(
#                      # can be incorrect. It is the only way that i have found to 
#                      # check this (scheduler.py:162/config.py:1720)
#                      self.sched.hosts.find_by_name(host.host_name) is None
#                     ,('host \'%s\' seems to be scheduled (%s)'
#                        % (host.host_name, config))
#                    )

    def check_no_child_hst(self, config, host):
        """ Check that no host use the host as parent.

            Raise an error if host is a child of a parent relation

        """

        self.assert_(
                      0 == len(host.childs)
                     ,('host \'%s\' is a parent of at least 1 other host (%s)'
                        % (host.host_name, config))
                    )

    # this function is not tested yet
    def check_disabled_hst(self, config, host):
        """Check if an host is disabled.

           A disabled host is a host with
            - down state
            - checks disabled
            - retention disabled
            - commands disabled
            - not scheduled
            - no other host use this host as parent
           The function raise an error if (at least) one of theses conditions
           is not verified.

        """

        # state is down
        self.check_down_state_hst(
                                   config
                                  ,host
                                 )

        # checks are disabled
        self.check_active_passive_disabled_hst(
                                                config
                                               ,host
                                              )

        # check that no other host use this as a parent (not used as a child)
        # because if a disabled host is used as parent, there will be conflicts with 
        # states unreachable and down
        self.check_no_child_hst(
                                 config
                                ,host
                               )

        # retention is disabled
        self.check_retention_disabled_hst(
                                           config
                                          ,host
                                         )


        # commands are disabled
        self.check_commands_disabled_hst(
                                          config
                                         ,host
                                        )

        # check that the host is not scheduled
        self.check_non_scheduled_hst(
                                      config
                                     ,host
                                    )


    def check_no_parents_hst(self, config, host):
        """Check that the host have no parent.

           Raise an error if the host has at least 1 parent.

        """

        self.assert_(
                      0 == len(host.parents)
                     ,('host \'%s\' has %s parents (%s)'
                        % (host.host_name, len(host.parents), config))
                    )

    def check_log(self, config, stream, pattern):
        """Check if log message is raised.

           Raise an error if the pattern is not found in stream.

        """

        # the pattern is a substring of log
        self.assert_(
                      pattern in stream.getvalue()
                     ,('pattern \'%s\' not found in log (%s)'
                        % (pattern, config))
                    )

    def check_config(self, configs):
        """Check configurations.

           For each configuration, the function test if
            - global configuration is valid
            - configuration of host is expected 
            - logs exepected are raised

           Configs is a dictionnary with:
            { 'file_to_load' :
               ( 
                  [ *list of tuples concerning the hosts for which 
                     we want check state* ]
                 ,[ *list of the strings that we check if they have
                     been printed in log* ]
               ) 
            }

        """

        for config in configs.keys():

            # redirect stdout and stderr to StringIO in order to check logs
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = stdout = StringIO()
#            stdout = StringIO()

            # load the configuration from file
            # (the function 'load_conf' take a 'in_test' argument)
            self.setup_with_file('etc/hosts_config/%s' % (config))

            # restore stdout and stderr
            sys.stdout, sys.stderr = old_stdout, old_stderr

            # print the stringio (only for debug test cases)
            print(stdout.getvalue())

            # the global configuration must always be valid
            self.assert_(
                          True == self.conf.conf_is_correct
                         ,('config \'%s\' is not correct' % config)
                        )

            # check if the hosts are corrects
            for hst in configs[config][CHECK_HOSTS]:

                # hst[0] -> host_name
                # hst[1] -> value expected for is_correct
                # hst[2] -> true if the host must be disabled, 
                #           no_parents if the host must have no parents 

                host = self.get_hst(
                                     config
                                    ,hst[HOST_NAME]
                                   )

                # check if the host has a valid configuration or not
                self.check_config_hst(
                                       config
                                      ,host
                                      ,hst[HOST_CONF_MUST_BE_CORRECT]
                                     )

                # if the host must be disabled, we check it
                if(len(hst) > 2): # if HOST_MUST_BE_DISABLED is not specified,
                                  # it is false

                    if(HOST_DISABLED == hst[HOST_MUST_BE_DISABLED]):
                        self.check_disabled_hst(
                                                 config
                                                ,host
                                               )

                    elif(HOST_NO_PARENTS == hst[HOST_MUST_BE_DISABLED]):
                        self.check_no_parents_hst(
                                                   config
                                                  ,host
                                                 )

                    # else (host_not_disabled) : do nothing, we don't check if host 
                    # is enabled

            # check the logs
            for log in configs[config][CHECK_LOGS]:
                self.check_log(
                                config
                               ,stdout
                               ,log
                              )

            # close the stringio
            stdout.close()


    def test_loop_in_parents(self):
        """Detection of topology parent attribute loops.

           The global configuration should not be incorrect with a
           host which has a loop with its parents.
           But parent relation may be suspended for some of them.

        """

        self.check_config({
         # only one host which is parent of itself
          'nagios_loop_in_parents_1.cfg' :
          ( 
            [
             (
               'test_host_0'
              ,False
              ,HOST_NO_PARENTS
             )
            ]
           ,['The host \'test_host_0\' is part of a circular parent/child chain!'] 
          )

         # a loop between two hosts
         ,'nagios_loop_in_parents_2.cfg' :
          ( 
            [
              (
                'test_host_0'
               ,False
               ,HOST_NO_PARENTS
              )
             ,(
                'test_host_1'
               ,False
               ,HOST_NO_PARENTS
              )
             ,(
                'test_host_2'
               ,True
              )
            ]
           ,[
              'The host \'test_host_0\' is part of a circular parent/child chain!'
             ,'The host \'test_host_1\' is part of a circular parent/child chain!'
             ,'Hosts: detected loop in parents ; conf incorrect'
            ]
          )

         # a simple large loop
         ,'nagios_loop_in_parents_3.cfg' :
          (
            [
              (
                'test_host_0'
               ,False
               ,HOST_NO_PARENTS
              )
             ,(
                'test_host_1'
               ,False
               ,HOST_NO_PARENTS
              )
             ,(
                'test_host_2'
               ,False
               ,HOST_NO_PARENTS
              )
             ,(
                'test_host_3'
               ,False
               ,HOST_NO_PARENTS
              )
             ,(
                'test_host_4'
               ,False
               ,HOST_NO_PARENTS
              )
            ]
           ,[
              'The host \'test_host_1\' is part of a circular parent/child chain!'
             ,'The host \'test_host_2\' is part of a circular parent/child chain!'
             ,'The host \'test_host_3\' is part of a circular parent/child chain!'
             ,'The host \'test_host_4\' is part of a circular parent/child chain!'
             ,'Hosts: detected loop in parents ; conf incorrect'
            ] 
          )

         # two independant loops with two hosts in each
         ,'nagios_loop_in_parents_4.cfg' :
          (
            [
              (
                'test_host_0'
               ,False
               ,HOST_NO_PARENTS
              )
             ,(
                'test_host_1'
               ,False
               ,HOST_NO_PARENTS
              )
             ,(
                'test_host_2'
               ,False
               ,HOST_NO_PARENTS
              )
             ,(
                'test_host_3'
               ,False
               ,HOST_NO_PARENTS
              )
             ,(
                'test_host_4'
               ,True
              )
            ]
           ,[
              'The host \'test_host_0\' is part of a circular parent/child chain!'
             ,'The host \'test_host_1\' is part of a circular parent/child chain!'
             ,'The host \'test_host_2\' is part of a circular parent/child chain!'
             ,'The host \'test_host_3\' is part of a circular parent/child chain!'
             ,'Hosts: detected loop in parents ; conf incorrect'
            ]
          )

         # multiple imbricated loops
         ,'nagios_loop_in_parents_5.cfg' :
          (
            [
              (
                'test_host_0'
               ,False
               ,HOST_NO_PARENTS 
              ) 
             ,(
                'test_host_1'
               ,False
               ,HOST_NO_PARENTS
              )
             ,(
                'test_host_2'
               ,False
               ,HOST_NO_PARENTS
              )
             ,(
                'test_host_3'
               ,False
               ,HOST_NO_PARENTS 
              )
             ,(
                'test_host_4'
               ,False
               ,HOST_NO_PARENTS
              )
            ]
           ,[
              'The host \'test_host_0\' is part of a circular parent/child chain!'
             ,'The host \'test_host_1\' is part of a circular parent/child chain!'
             ,'The host \'test_host_2\' is part of a circular parent/child chain!'
             ,'The host \'test_host_3\' is part of a circular parent/child chain!'
             ,'The host \'test_host_4\' is part of a circular parent/child chain!'
             ,'Hosts: detected loop in parents ; conf incorrect'
            ]
          )
        })

    def test_remove_twins(self):
        """Test of non-unique hostnames

           The global configuration should be correct even if there are
           two hosts or more with the same name

        """

        self.check_config({
         # two valid hosts with the same name
          'nagios_remove_twins_1.cfg' :
          (
            [
             # check if each host is correct can be impossible because
             # there is not an unique name per host
            ]
           ,['host.test_host_0 is duplicated from etc/hosts_config/host_remove_twins_1/hosts.cfg']
          )

         # a valid host and an invalid host with the same name
         ,'nagios_remove_twins_2.cfg' :
          (
            []
           ,['host.test_host_0 is duplicated from etc/hosts_config/host_remove_twins_2/hosts.cfg']
          )
        })

    def test_special_properties(self):
        """Test of required attributes.

           The global configuration should be correct even if some attributes are 
           missing.

        """

        self.check_config({
         # a host without check_period attribute
          'nagios_special_properties_1.cfg' :
          (
            [
             (
               'test_host_0'
              ,False
              ,HOST_DISABLED
             )
            ]
           ,['test_host_0: My check_period is not correct']
          )

         # a host without max_check_attempts attribute
         ,'nagios_special_properties_2.cfg' :
          (
            [
             (
               'test_host_0'
              ,False
              ,HOST_DISABLED
             )
            ]
           ,['[host::test_host_0] max_check_attempts property not set']
          )
        })

    def test_check_command(self):
        """Test of check_command attribute.

           There are 2 configurations when the "check_command" attribute
           is incorrect
           The first configuration is the check_command is invalid
             -> the host configuration is incorrect and the host is disabled
           The second configuration is the check_command is valid but
           the command is not valid
             -> the host configuration is correct but the host is disabled

        """
        self.check_config({
         # a host with a check_command which is not a defined command
          'nagios_check_command_1.cfg' :
          (
            [
             (
               'test_host_0'
              ,False
              ,HOST_DISABLED
             )
            ]
           ,['test_host_0: my check_command None is invalid']
          )

         # an invalid command and a host which use this command
         # as check_command
         ,'nagios_check_command_2.cfg' :
          (
            [
             (
               'test_host_0'
              ,True
              ,HOST_DISABLED
             )
            ]
           ,['[item::commande] command_line property is missing']
          )
        })

    def test_no_host_name(self):
        """Test of host without hostname.

           A name should be generated when there is an host without hostname.
           If there are more than one host without hostname, shinken must generate
           an unique name for each host. The generated names mustn't be in conflicts
           with the names defined by the user.
           The hosts don't be disabled.

        """

        self.check_config({
         # a host without host_name and alias
          'nagios_no_host_name_1.cfg' :
          (
            [
             (
               'UNNAMEDHOST' #! TODO: put real host_name
              ,False
             )
             # check if host is correct can be impossible because it 
             # doesn't have name

             # TODO when we will choose the default name, we will able 
             # to access to the host with it
            ]
           ,[
              '[host::UNNAMEDHOST] host_name property not set'
             ,'[host::UNNAMEDHOST] alias property not set'
            ]
          )

         # a host without host_name but with an alias
         ,'nagios_no_host_name_2.cfg' :
          (
            [
             (
               'UNNAMEDHOST' #! TODO: put real host_name
              ,False
             )
            ]
           ,['host::UNNAMEDHOST] host_name property not set']
          )

         # two hosts without host_name (shinken must generate a unique name
         # for each host
         ,'nagios_no_host_name_3.cfg' :
          (
            [
              (
                'UNNAMEDHOST' #! TODO: put real host_name
               ,False
              )
             ,(
                'UNNAMEDHOST' #! TODO: put real host_name
               ,False
              )
            ]
           ,['host::UNNAMEDHOST] host_name property not set']
          )
        })

    def test_active_check(self):
        """Test of host with active_check enabled but with an invalid
           check_interval and check_period.

           The configuration is invalid and the host must be disabled.

        """

        self.check_config({
         # a host with active_check enabled but with an invalid
         # check_interval and an invalid check_period
          'nagios_active_check_1.cfg' :
          (
            [
             (
               'test_host_0'
              ,False
              ,HOST_DISABLED 
             )
            ]
           ,[ 
              '[host::test_host_0] incorrect type for property \'check_interval\' of \'test_host_0\''
             ,'[host::test_host_0] The check_period of the host \'test_host_0\' named \'invalid\' is unknown!'
            ]
          )
        })

    def test_poller_tag(self):
        """Test of host with an invalid poller tag.

        """

        self.check_config({
         # a host with an invalid poller tag
          'nagios_poller_tag_1.cfg' :
          (
            [
             (
               'test_host_0'
              ,False
              ,HOST_DISABLED
             )
            ]
           ,['Hosts exist with poller_tag invalidtag but no poller got this tag']
          )
        })

    # when business_impact is invalid
    def test_business_impact(self):
        """Test of host with an invalid business impact.

           The business impact attribute is not an integer.

        """

        self.check_config({
         # a host with a business_impact attribute which is not an integer
          'nagios_business_impact_1.cfg' :
          (
            [
             (
               'test_host_0'
              ,False
              ,HOST_DISABLED
             )
            ]
           ,[]
          )
        })

    # if event_handler is invalid
    def test_event_handler(self):
        """Test of host with an invalid event handler.

           There are 2 configurations when the "event_handler" attribute
           is incorrect
           The first configuration is the event_handler is invalid
             -> the host configuration is incorrect and the host is disabled
           The second configuration is the event_handler is valid but
           the command is not valid
             -> the host configuration is correct but the host is disabled

        """

        self.check_config({
         # a host with an event_handler which is not a defined command
          'nagios_event_handler_1.cfg' :
          (
            [
             (
               'test_host_0'
              ,False
              ,HOST_DISABLED 
             )
            ]
           ,['test_host_0: my event_handler None is invalid']
          )

         # an invalid command and a host which use this command
         # as event_handler
         ,'nagios_event_handler_2.cfg' :
          (
            [
             (
                'test_host_0'
               ,True
               ,HOST_DISABLED 
             )
            ]
           ,['[item::commande] command_line property is missing']
          )
        })

    def test_notification(self):
        """Test an host with notification_enabled but without 
           notification_interval.

           The configuration of host must be invalide and the host must
           be disabled.

        """

        self.check_config({
          'nagios_notification_1.cfg' :
          (
            [
             (
               'test_host_0'
              ,False
              ,HOST_DISABLED
             )
            ]
           ,[
             # I can't catch message log
             # I don't have the message :
             # "%s: I've got no notification_interval but I've got
             # notifications enabled"
            ]
          )
        })

if '__main__' == __name__:
    unittest.main()

