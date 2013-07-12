#!/usr/bin/env python
# -*- coding: utf-8 -*-

from shinken_test import *
from cStringIO import StringIO
from collections import namedtuple
import time
import sys

class TestConfig(ShinkenTest):

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
            - logs exepected are raised

           Configs is a dictionnary with:
            { 'file_to_load' :
               ( 
                 [ *list of the strings that we check if they have
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
            self.setup_with_file('etc/hostgroups_config/%s' % (config))

            # restore stdout and stderr
            sys.stdout, sys.stderr = old_stdout, old_stderr

            # print the stringio (only to debug test cases)
            print(stdout.getvalue())

            # the global configuration must always be valid
            self.assert_( 
                          True == self.conf.conf_is_correct
                         ,('config \'%s\' is not correct' % config)
                        )
            

            # check the logs
            for log in configs[config]:
                self.check_log(
                                config
                               ,stdout
                               ,log
                              )

            # close the stringio
            stdout.close()


    def test_unknown_member(self):
        """Check that a warning is raised when a hostgroup contains an unknown host"""

        self.check_config({
         # test with a hostgroup that has in its members an unknown host_name
         'nagios_unknown_member_1.cfg' : [
                                          '[itemgroup::my_hostgroup_0] as hostgroup, got unknown member test_host_unknown'
                                         ]

        })

if '__main__' == __name__:
    unittest.main()
