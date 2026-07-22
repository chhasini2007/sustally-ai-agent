import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_regression import TestRegression

def run_single():
    suite = unittest.TestSuite()
    suite.addTest(TestRegression("test_ambiguous_company_tata"))
    runner = unittest.TextTestRunner()
    print("Running single test case...")
    runner.run(suite)
    print("Finished single test case.")

if __name__ == "__main__":
    run_single()
