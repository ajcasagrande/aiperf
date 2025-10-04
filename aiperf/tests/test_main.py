import unittest
from src.main import AIPerf

class TestAIPerf(unittest.TestCase):

    def setUp(self):
        self.aiperf = AIPerf()

    def test_initialization(self):
        self.assertIsNotNone(self.aiperf.system_controller)
        self.assertIsNotNone(self.aiperf.dataset_manager)
        self.assertIsNotNone(self.aiperf.timing_manager)
        self.assertIsNotNone(self.aiperf.worker_manager)

    def test_benchmarking_process(self):
        result = self.aiperf.run_benchmark()
        self.assertIsInstance(result, dict)
        self.assertIn('performance_metrics', result)

if __name__ == '__main__':
    unittest.main()