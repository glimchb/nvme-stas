#!/usr/bin/python3
import os
import unittest
import stafd
from staslib import stas
from pyfakefs.fake_filesystem_unittest import TestCase

class MyNvmeStub:
    def ctrl(self, bla):
        print("checking the arguments")

class Test(TestCase):
    '''Unit tests for class Staf'''

    def setUp(self):
        self.setUpPyfakefs()
        os.environ['RUNTIME_DIRECTORY'] = "/run"

    def test_basic(self):
        stas.nvme = MyNvmeStub()
        STAF = stafd.Staf()
        STAF.run()

if __name__ == '__main__':
    unittest.main()
