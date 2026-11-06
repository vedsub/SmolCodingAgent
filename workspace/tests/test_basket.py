import unittest

from basket import calculate_total


class TestBasket(unittest.TestCase):

    def test_calculate_total(self):
        self.assertEqual(calculate_total(7, 3), 21)

    def test_zero_quantity(self):
        self.assertEqual(calculate_total(7, 0), 0)


if __name__ == "__main__":
    unittest.main()
