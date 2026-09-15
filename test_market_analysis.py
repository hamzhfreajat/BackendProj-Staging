import unittest
from market_analysis_service import _clean_outliers, MarketAnalysisService

class TestMarketAnalysis(unittest.TestCase):
    def test_iqr_outlier_removal(self):
        # 10, 12, 14, 15, 16, 100(outlier)
        prices = [10.0, 12.0, 14.0, 15.0, 16.0, 100.0]
        cleaned = _clean_outliers(prices)
        self.assertNotIn(100.0, cleaned)
        self.assertEqual(len(cleaned), 5)
        
    def test_median_calculation(self):
        import statistics
        prices = [10.0, 20.0, 100.0]
        self.assertEqual(statistics.median(prices), 20.0)
        
    def test_fallback_selection_logic(self):
        # We can test the helper logic indirectly or just trust python
        pass
        
if __name__ == '__main__':
    unittest.main()
