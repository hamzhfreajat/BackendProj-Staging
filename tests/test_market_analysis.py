import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import unittest
import statistics
from market_analysis_service import _clean_outliers

class TestMarketAnalysis(unittest.TestCase):
    def test_iqr_outlier_removal(self):
        prices = [0.5, 10.0, 12.0, 14.0, 15.0, 16.0, 100.0]
        cleaned = _clean_outliers(prices)
        self.assertNotIn(100.0, cleaned)
        self.assertNotIn(0.5, cleaned)
        self.assertEqual(len(cleaned), 5)
        
    def test_median_calculation(self):
        prices_odd = [10.0, 20.0, 100.0]
        self.assertEqual(statistics.median(prices_odd), 20.0)
        prices_even = [10.0, 20.0, 30.0, 40.0]
        self.assertEqual(statistics.median(prices_even), 25.0)

if __name__ == '__main__':
    unittest.main()
